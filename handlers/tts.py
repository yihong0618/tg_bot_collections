import glob
import threading
import subprocess
from os import environ, remove

from telebot import TeleBot
from telebot.types import Message

from . import *

import wave
import numpy as np
from ChatTTS import Chat


def check_ffmpeg():
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


HAS_FFMPEG = check_ffmpeg()
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

    def generate_tts_wav(prompt, output_filename, seed=None):
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
        else:
            wavs = chat.infer(texts, use_decoder=True)

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
                generate_tts_wav(prompt, "tts.wav")
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
        # split the prompt by 100 characters
        prompt_split = [prompt[i : i + 50] for i in range(0, len(prompt), 50)]
        if not HAS_FFMPEG:
            if len(prompt) > 150:
                bot.reply_to(message, "prompt too long must length < 150")
                return
        try:
            with lock:
                if len(prompt_split) > 1:
                    bot.reply_to(
                        message,
                        "Will split the text and use the same to generate the audio and use ffmpeg to combin them pleas wait more time",
                    )
                    for k, v in enumerate(prompt_split):
                        generate_tts_wav(v, f"{k}.wav", seed)
                        with open("input.txt", "a") as f:
                            f.write(f"file {k}.wav\n")
                    output_file = "tts_pro.wav"
                    # Run the FFmpeg command
                    try:
                        # make sure remove it
                        try:
                            remove("tts_pro.wav")
                        except:
                            pass
                        subprocess.run(
                            [
                                "ffmpeg",
                                "-f",
                                "concat",
                                "-safe",
                                "0",
                                "-i",
                                "input.txt",
                                "-c",
                                "copy",
                                "tts_pro.wav",
                            ],
                            check=True,
                        )
                    except Exception as e:
                        print(f"Error combining audio files, {e}")
                        bot.reply_to(message, "tts error please check the log")
                        remove("input.txt")
                        return
                    print(f"Combined audio saved as {output_file}")
                    with open(f"tts_pro.wav", "rb") as audio:
                        bot.send_audio(
                            message.chat.id,
                            audio,
                            reply_to_message_id=message.message_id,
                        )
                    remove("input.txt")
                    for file in glob.glob("*.wav"):
                        try:
                            remove(file)
                        except OSError as e:
                            print(e)
                else:
                    generate_tts_wav(prompt, "tts_pro.wav", seed)
                    with open(f"tts_pro.wav", "rb") as audio:
                        bot.send_audio(
                            message.chat.id,
                            audio,
                            reply_to_message_id=message.message_id,
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
