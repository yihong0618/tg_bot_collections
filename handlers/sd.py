from telebot import TeleBot
from telebot.types import Message
import requests
from os import environ

from . import *


SD_API_KEY = environ.get("SD3_KEY")


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
        f"https://api.stability.ai/v2beta/stable-image/generate/sd3",
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
            with open(f"sd3.jpeg", "rb") as photo:
                bot.send_photo(
                    message.chat.id, photo, reply_to_message_id=message.message_id
                )
        else:
            bot.reply_to(message, "prompt error")
    except Exception as e:
        print(e)
        bot.reply_to(message, "sd3 error")


if SD_API_KEY:

    def register(bot: TeleBot) -> None:
        bot.register_message_handler(sd_handler, commands=["sd3"], pass_bot=True)
        bot.register_message_handler(sd_handler, regexp="^sd3:", pass_bot=True)
