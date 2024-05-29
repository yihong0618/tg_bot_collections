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

    def generate_tts_wav(prompt):
        texts = [
            prompt,
        ]
        wavs = chat.infer(texts, use_decoder=True)
        output_filename = "tts.wav"
        audio_data = np.array(
            wavs[0], dtype=np.float32
        )  # Ensure the data type is correct
        sample_rate = 24000
        # Normalize the audio data to 16-bit PCM range
        audio_data = (audio_data * 32767).astype(np.int16)

        # Open a .wav file to write into
        with wave.open(output_filename, "w") as wf:
            wf.setnchannels(1)  # Mono channel
            wf.setsampwidth(2)  # 2 bytes per sample
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data.tobytes())

        print(f"Audio has been saved to {output_filename}")

    def tts_handler(message: Message, bot: TeleBot):
        """pretty tts: /tts <address>"""
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

    def register(bot: TeleBot) -> None:
        bot.register_message_handler(tts_handler, commands=["tts"], pass_bot=True)
        bot.register_message_handler(tts_handler, regexp="^tts:", pass_bot=True)
