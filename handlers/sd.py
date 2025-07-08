from os import environ

import requests
from openai import OpenAI
from telebot import TeleBot
from telebot.types import Message

from config import settings

from . import *

SD_API_KEY = environ.get("SD3_KEY")

# TODO refactor this shit to __init__
CHATGPT_API_KEY = settings.openai_api_key
CHATGPT_BASE_URL = settings.openai_base_url
CHATGPT_PRO_MODEL = settings.openai_model

client = OpenAI(api_key=CHATGPT_API_KEY, base_url=CHATGPT_BASE_URL)


def get_user_balance():
    api_host = "https://api.stability.ai"
    url = f"{api_host}/v1/user/balance"

    response = requests.get(url, headers={"Authorization": f"Bearer {SD_API_KEY}"})

    if response.status_code != 200:
        print("Non-200 response: " + str(response.text))

    # Do something with the payload...
    payload = response.json()
    return payload["credits"]


def generate_sd3_image(prompt):
    response = requests.post(
        "https://api.stability.ai/v2beta/stable-image/generate/sd3",
        headers={"authorization": f"Bearer {SD_API_KEY}", "accept": "image/*"},
        files={"none": ""},
        data={
            "prompt": prompt,
            "model": "sd3-turbo",
            "output_format": "jpeg",
        },
    )

    if response.status_code == 200:
        with open("sd3.jpeg", "wb") as file:
            file.write(response.content)
        return True
    else:
        print(str(response.json()))
        return False


def sd_handler(message: Message, bot: TeleBot):
    """pretty sd3: /sd3 <address>"""
    credits = get_user_balance()
    bot.reply_to(
        message,
        f"Generating pretty sd3-turbo image may take some time please left credits {credits} every try will cost 4 criedits wait:",
    )
    m = message.text.strip()
    prompt = m.strip()
    try:
        r = generate_sd3_image(prompt)
        if r:
            with open("sd3.jpeg", "rb") as photo:
                bot.send_photo(
                    message.chat.id, photo, reply_to_message_id=message.message_id
                )
        else:
            bot.reply_to(message, "prompt error")
    except Exception as e:
        print(e)
        bot.reply_to(message, "sd3 error")


def sd_pro_handler(message: Message, bot: TeleBot):
    """pretty sd3_pro: /sd3_pro <address>"""
    credits = get_user_balance()
    m = message.text.strip()
    prompt = m.strip()
    rewrite_prompt = (
        f"revise `{prompt}` to a DALL-E prompt only return the prompt in English."
    )
    completion = client.chat.completions.create(
        messages=[{"role": "user", "content": rewrite_prompt}],
        max_tokens=2048,
        model=CHATGPT_PRO_MODEL,
    )
    sd_prompt = completion.choices[0].message.content.encode("utf8").decode()
    # drop all the Chinese characters
    sd_prompt = "".join([i for i in sd_prompt if ord(i) < 128])
    bot.reply_to(
        message,
        f"Generating pretty sd3-turbo image may take some time please left credits {credits} every try will cost 4 criedits wait:\n the real prompt is: {sd_prompt}",
    )
    try:
        r = generate_sd3_image(sd_prompt)
        if r:
            with open("sd3.jpeg", "rb") as photo:
                bot.send_photo(
                    message.chat.id, photo, reply_to_message_id=message.message_id
                )
        else:
            bot.reply_to(message, "prompt error")
    except Exception as e:
        print(e)
        bot.reply_to(message, "sd3 error")


if SD_API_KEY and CHATGPT_API_KEY:

    def register(bot: TeleBot) -> None:
        bot.register_message_handler(sd_handler, commands=["sd3"], pass_bot=True)
        bot.register_message_handler(sd_handler, regexp="^sd3:", pass_bot=True)
        bot.register_message_handler(
            sd_pro_handler, commands=["sd3_pro"], pass_bot=True
        )
        bot.register_message_handler(sd_pro_handler, regexp="^sd3_pro:", pass_bot=True)
