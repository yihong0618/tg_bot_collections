import base64
from os import environ
from pathlib import Path

from openai import OpenAI
import requests
from telebot import TeleBot
from telebot.types import Message

from . import *

YI_BASE_URL = environ.get("YI_BASE_URL")
YI_API_KEY = environ.get("YI_API_KEY")
YI_MODEL = "yi-34b-chat-0205"  # also support yi-34b-chat-200k

client = OpenAI(
    # defaults to os.environ.get("OPENAI_API_KEY")
    api_key=YI_API_KEY,
    base_url=YI_BASE_URL,
)

# Global history cache
yi_player_dict = {}


def yi_handler(message: Message, bot: TeleBot) -> None:
    """yi : /yi <question>"""
    m = message.text.strip()

    player_message = []
    # restart will lose all TODO
    if str(message.from_user.id) not in yi_player_dict:
        yi_player_dict[str(message.from_user.id)] = (
            player_message  # for the imuutable list
        )
    else:
        player_message = yi_player_dict[str(message.from_user.id)]
    if m.strip() == "clear":
        bot.reply_to(
            message,
            "just clear your yi messages history",
        )
        player_message.clear()
        return

    # show something, make it more responsible
    reply_id = bot_reply_first(message, "Yi", bot)

    player_message.append({"role": "user", "content": m})
    # keep the last 5, every has two ask and answer.
    if len(player_message) > 10:
        player_message = player_message[2:]

    yi_reply_text = ""
    try:
        if len(player_message) > 2:
            if player_message[-1]["role"] == player_message[-2]["role"]:
                # tricky
                player_message.pop()
        r = client.chat.completions.create(messages=player_message, model=YI_MODEL)

        content = r.choices[0].message.content.encode("utf8").decode()
        if not content:
            yi_reply_text = "yi did not answer."
            player_message.pop()
        else:
            yi_reply_text = content
            player_message.append(
                {
                    "role": "assistant",
                    "content": yi_reply_text,
                }
            )

    except Exception as e:
        print(e)
        bot.reply_to(
            message,
            "yi answer:\n" + "yi answer timeout",
            parse_mode="MarkdownV2",
        )
        # pop my user
        player_message.pop()
        return

    # reply back as Markdown and fallback to plain text if failed.
    bot_reply_markdown(reply_id, "Yi", yi_reply_text, bot)


def _image_to_data_uri(file_path):
    with open(file_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
        return f"data:image/png;base64,{encoded_image}"


def yi_photo_handler(message: Message, bot: TeleBot) -> None:
    s = message.caption
    bot.reply_to(
        message,
        "Generating yi vision answer please wait.",
    )
    prompt = s.strip()
    # get the high quaility picture.
    max_size_photo = max(message.photo, key=lambda p: p.file_size)
    file_path = bot.get_file(max_size_photo.file_id).file_path
    downloaded_file = bot.download_file(file_path)
    with open("yi_temp.jpg", "wb") as temp_file:
        temp_file.write(downloaded_file)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {client.api_key}",
    }

    payload = {
        "model": "yi-vl-plus",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": _image_to_data_uri("yi_temp.jpg")},
                    },
                ],
            }
        ],
        "max_tokens": 2048,
    }

    response = requests.post(
        f"https://api.lingyiwanwu.com/v1/chat/completions",
        headers=headers,
        json=payload,
    ).json()
    try:
        text = response["choices"][0]["message"]["content"].encode("utf8").decode()
        bot.reply_to(message, "yi vision answer:\n" + text)
    except Exception as e:
        print(e)
        bot.reply_to(
            message,
            "yi vision answer:\n" + "yi vision answer wrong",
            parse_mode="MarkdownV2",
        )


def register(bot: TeleBot) -> None:
    bot.register_message_handler(yi_handler, commands=["yi"], pass_bot=True)
    bot.register_message_handler(yi_handler, regexp="^yi:", pass_bot=True)
    bot.register_message_handler(
        yi_photo_handler,
        content_types=["photo"],
        func=lambda m: m.caption and m.caption.startswith(("yi:", "/yi")),
        pass_bot=True,
    )
