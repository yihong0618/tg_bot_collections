import threading
from os import environ

from telebot import TeleBot
from telebot.types import Message

from . import *

import wave
import numpy as np
from ChatTTS import Chat

USE_CHATTTS = environ.get("USE_CHATTTS")
if USE_CHATTTS:
    chat = Chat()
    chat.load_models()
    lock = threading.Lock()  # Initialize a lock

    def save_data_to_wav(filename, data):
        sample_rate = 24000
        # Open a .wav file to write into
        with wave.open(filename, "w") as wf:
            wf.setnchannels(1)  # Mono channel
            wf.setsampwidth(2)  # 2 bytes per sample
            wf.setframerate(sample_rate)
            wf.writeframes(data.tobytes())

    def generate_tts_wav(prompt, seed=None):
        texts = [
            prompt,
        ]
        if seed:
            r = chat.sample_random_speaker(seed)
            params_infer_code = {
                "spk_emb": r,  # add sampled speaker
                "temperature": 0.3,  # using custom temperature
                "top_P": 0.7,  # top P decode
                "top_K": 20,  # top K decode
            }
            wavs = chat.infer(
                texts, use_decoder=True, params_infer_code=params_infer_code
            )
            output_filename = "tts_pro.wav"
        else:
            wavs = chat.infer(texts, use_decoder=True)
            output_filename = "tts.wav"

        audio_data = np.array(
            wavs[0], dtype=np.float32
        )  # Ensure the data type is correct
        # Normalize the audio data to 16-bit PCM range
        audio_data = (audio_data * 32767).astype(np.int16)
        save_data_to_wav(output_filename, audio_data)

        if seed:
            print(f"Audio has been saved to {output_filename} with seed {seed}")
        else:
            print(f"Audio has been saved to {output_filename}")

    def tts_handler(message: Message, bot: TeleBot):
        """pretty tts: /tts <prompt>"""
        bot.reply_to(
            message, f"Generating ChatTTS may take some time please wait some time."
        )
        m = message.text.strip()
        prompt = m.strip()
        if len(prompt) > 150:
            bot.reply_to(message, "prompt too long must length < 150")
            return
        try:
            with lock:
                generate_tts_wav(prompt)
            with open(f"tts.wav", "rb") as audio:
                bot.send_audio(
                    message.chat.id, audio, reply_to_message_id=message.message_id
                )
        except Exception as e:
            print(e)
            bot.reply_to(message, "tts error")

    def tts_pro_handler(message: Message, bot: TeleBot):
        """pretty tts_pro: /tts_pro <seed>,<prompt>"""
        m = message.text.strip()
        prompt = m.strip()
        seed = prompt.split(",")[0]
        bot.reply_to(
            message,
            f"Generating ChatTTS with seed: {seed} may take some time please wait some time.",
        )
        if not seed.isdigit():
            bot.reply_to(message, "first argument must be a number")
            return
        prompt = prompt[len(str(seed)) + 1 :]
        if len(prompt) > 150:
            bot.reply_to(message, "prompt too long must length < 150")
            return
        try:
            with lock:
                generate_tts_wav(prompt, seed)
            with open(f"tts_pro.wav", "rb") as audio:
                bot.send_audio(
                    message.chat.id, audio, reply_to_message_id=message.message_id
                )
        except Exception as e:
            print(e)
            bot.reply_to(message, "tts error")

    def register(bot: TeleBot) -> None:
        bot.register_message_handler(tts_handler, commands=["tts"], pass_bot=True)
        bot.register_message_handler(tts_handler, regexp="^tts:", pass_bot=True)
        bot.register_message_handler(
            tts_pro_handler, commands=["tts_pro"], pass_bot=True
        )
        bot.register_message_handler(tts_pro_handler, regexp="^tts_pro:", pass_bot=True)
