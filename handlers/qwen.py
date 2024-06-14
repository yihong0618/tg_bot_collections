# qwen use https://api.together.xyz
from os import environ
import time

from telebot import TeleBot
from telebot.types import Message
from expiringdict import ExpiringDict

from . import *

from together import Together
from telegramify_markdown import convert
from telegramify_markdown.customize import markdown_symbol

markdown_symbol.head_level_1 = "📌"  # If you want, Customizing the head level 1 symbol
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol

QWEN_API_KEY = environ.get("TOGETHER_API_KEY")
QWEN_MODEL = "Qwen/Qwen2-72B-Instruct"

if QWEN_API_KEY:
    client = Together(api_key=QWEN_API_KEY)

# Global history cache
qwen_player_dict = ExpiringDict(max_len=1000, max_age_seconds=300)
qwen_pro_player_dict = ExpiringDict(max_len=1000, max_age_seconds=300)


def qwen_handler(message: Message, bot: TeleBot) -> None:
    """qwen : /qwen <question>"""
    m = message.text.strip()

    player_message = []
    # restart will lose all TODO
    if str(message.from_user.id) not in qwen_player_dict:
        qwen_player_dict[str(message.from_user.id)] = (
            player_message  # for the imuutable list
        )
    else:
        player_message = qwen_player_dict[str(message.from_user.id)]
    if m.strip() == "clear":
        bot.reply_to(
            message,
            "just clear your qwen messages history",
        )
        player_message.clear()
        return
    if m[:4].lower() == "new ":
        m = m[4:].strip()
        player_message.clear()
    m = enrich_text_with_urls(m)

    who = "qwen"
    # show something, make it more responsible
    reply_id = bot_reply_first(message, who, bot)

    player_message.append({"role": "user", "content": m})
    # keep the last 5, every has two ask and answer.
    if len(player_message) > 10:
        player_message = player_message[2:]

    qwen_reply_text = ""
    try:
        r = client.chat.completions.create(
            messages=player_message, max_tokens=8192, model=QWEN_MODEL
        )
        content = r.choices[0].message.content.encode("utf8").decode()
        if not content:
            qwen_reply_text = f"{who} did not answer."
            player_message.pop()
        else:
            qwen_reply_text = content
            player_message.append(
                {
                    "role": "assistant",
                    "content": qwen_reply_text,
                }
            )

    except Exception as e:
        print(e)
        bot_reply_markdown(reply_id, who, "answer wrong", bot)
        # pop my user
        player_message.pop()
        return

    # reply back as Markdown and fallback to plain text if failed.
    bot_reply_markdown(reply_id, who, qwen_reply_text, bot)


def qwen_pro_handler(message: Message, bot: TeleBot) -> None:
    """qwen_pro : /qwen_pro <question>"""
    m = message.text.strip()

    player_message = []
    # restart will lose all TODO
    if str(message.from_user.id) not in qwen_pro_player_dict:
        qwen_pro_player_dict[str(message.from_user.id)] = (
            player_message  # for the imuutable list
        )
    else:
        player_message = qwen_pro_player_dict[str(message.from_user.id)]
    if m.strip() == "clear":
        bot.reply_to(
            message,
            "just clear your qwen messages history",
        )
        player_message.clear()
        return
    if m[:4].lower() == "new ":
        m = m[4:].strip()
        player_message.clear()
    m = enrich_text_with_urls(m)

    who = "qwen Pro"
    reply_id = bot_reply_first(message, who, bot)

    player_message.append({"role": "user", "content": m})
    # keep the last 5, every has two ask and answer.
    if len(player_message) > 10:
        player_message = player_message[2:]

    try:
        r = client.chat.completions.create(
            messages=player_message,
            max_tokens=8192,
            model=QWEN_MODEL,
            stream=True,
        )
        s = ""
        start = time.time()
        for chunk in r:
            if chunk.choices[0].delta.content is None:
                break
            s += chunk.choices[0].delta.content
            if time.time() - start > 1.7:
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
        bot_reply_markdown(reply_id, who, "answer wrong", bot)
        player_message.clear()
        return


if QWEN_API_KEY:

    def register(bot: TeleBot) -> None:
        bot.register_message_handler(qwen_handler, commands=["qwen"], pass_bot=True)
        bot.register_message_handler(qwen_handler, regexp="^qwen:", pass_bot=True)
        bot.register_message_handler(
            qwen_pro_handler, commands=["qwen_pro"], pass_bot=True
        )
        bot.register_message_handler(
            qwen_pro_handler, regexp="^qwen_pro:", pass_bot=True
        )
