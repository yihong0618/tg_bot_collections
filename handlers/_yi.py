import time
from os import environ

import requests
from expiringdict import ExpiringDict
from openai import OpenAI
from telebot import TeleBot
from telebot.types import Message
from telegramify_markdown import convert

from . import *

YI_BASE_URL = environ.get("YI_BASE_URL")
YI_API_KEY = environ.get("YI_API_KEY")
YI_MODEL = "yi-34b-chat-200k"
YI_PRO_MODEL = "yi-large"

client = OpenAI(
    # defaults to os.environ.get("OPENAI_API_KEY")
    api_key=YI_API_KEY,
    base_url=YI_BASE_URL,
)

# Global history cache
yi_player_dict = ExpiringDict(max_len=1000, max_age_seconds=600)
yi_pro_player_dict = ExpiringDict(max_len=1000, max_age_seconds=600)


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
    if m[:4].lower() == "new ":
        m = m[4:].strip()
        player_message.clear()
    m = enrich_text_with_urls(m)

    who = "Yi"
    # show something, make it more responsible
    reply_id = bot_reply_first(message, who, bot)

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
            yi_reply_text = f"{who} did not answer."
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
        bot.reply_to(message, "answer wrong maybe up to the max token")
        # pop my user
        player_message.pop()
        return

    # reply back as Markdown and fallback to plain text if failed.
    bot_reply_markdown(reply_id, who, yi_reply_text, bot)


def yi_pro_handler(message: Message, bot: TeleBot) -> None:
    """yi_pro : /yi_pro <question>"""
    m = message.text.strip()

    player_message = []
    # restart will lose all TODO
    if str(message.from_user.id) not in yi_pro_player_dict:
        yi_pro_player_dict[str(message.from_user.id)] = (
            player_message  # for the imuutable list
        )
    else:
        player_message = yi_pro_player_dict[str(message.from_user.id)]
    if m.strip() == "clear":
        bot.reply_to(
            message,
            "just clear your yi messages history",
        )
        player_message.clear()
        return
    if m[:4].lower() == "new ":
        m = m[4:].strip()
        player_message.clear()
    m = enrich_text_with_urls(m)

    who = "yi Pro"
    reply_id = bot_reply_first(message, who, bot)

    player_message.append({"role": "user", "content": m})
    # keep the last 5, every has two ask and answer.
    if len(player_message) > 10:
        player_message = player_message[2:]

    try:
        r = client.chat.completions.create(
            messages=player_message,
            max_tokens=8192,
            model=YI_PRO_MODEL,
            stream=True,
        )
        s = ""
        start = time.time()
        for chunk in r:
            if chunk.choices[0].delta.content is None:
                break
            s += chunk.choices[0].delta.content
            # 0.7 is enough for yi3 here its very fast
            if time.time() - start > 0.7:
                start = time.time()
                bot_reply_markdown(reply_id, who, s, bot, split_text=False)

        if not bot_reply_markdown(reply_id, who, s, bot):
            # maybe not complete
            # maybe the same message
            player_message.clear()
            return

        player_message.append(
            {
                "role": "assistant",
                "content": convert(s),
            }
        )

    except Exception as e:
        print(e)
        bot.reply_to(message, "answer wrong maybe up to the max token")
        player_message.clear()
        return


def yi_photo_handler(message: Message, bot: TeleBot) -> None:
    s = message.caption
    prompt = s.strip()
    who = "Yi Vision"
    # show something, make it more responsible
    reply_id = bot_reply_first(message, who, bot)
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
                        "image_url": {"url": image_to_data_uri("yi_temp.jpg")},
                    },
                ],
            }
        ],
        "max_tokens": 2048,
    }

    response = requests.post(
        "https://api.lingyiwanwu.com/v1/chat/completions",
        headers=headers,
        json=payload,
    ).json()
    try:
        text = response["choices"][0]["message"]["content"].encode("utf8").decode()
        bot_reply_markdown(reply_id, who, text, bot)
    except Exception as e:
        print(e)
        bot.reply_to(message, "answer wrong maybe up to the max token")


if YI_API_KEY and YI_BASE_URL:

    def register(bot: TeleBot) -> None:
        bot.register_message_handler(yi_handler, commands=["yi"], pass_bot=True)
        bot.register_message_handler(yi_handler, regexp="^yi:", pass_bot=True)
        bot.register_message_handler(yi_handler, commands=["yi_pro"], pass_bot=True)
        bot.register_message_handler(yi_handler, regexp="^yi_pro:", pass_bot=True)
        bot.register_message_handler(
            yi_photo_handler,
            content_types=["photo"],
            func=lambda m: m.caption and m.caption.startswith(("yi:", "/yi")),
            pass_bot=True,
        )
