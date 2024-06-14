from os import environ
import time

from telebot import TeleBot
from telebot.types import Message
from expiringdict import ExpiringDict

from . import *

from groq import Groq
from telegramify_markdown import convert
from telegramify_markdown.customize import markdown_symbol

markdown_symbol.head_level_1 = "📌"  # If you want, Customizing the head level 1 symbol
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol

LLAMA_API_KEY = environ.get("GROQ_API_KEY")
LLAMA_MODEL = "llama3-8b-8192"
LLAMA_PRO_MODEL = "llama3-70b-8192"

if LLAMA_API_KEY:
    client = Groq(api_key=LLAMA_API_KEY)

# Global history cache
llama_player_dict = ExpiringDict(max_len=1000, max_age_seconds=300)
llama_pro_player_dict = ExpiringDict(max_len=1000, max_age_seconds=300)


def llama_handler(message: Message, bot: TeleBot) -> None:
    """llama : /llama <question>"""
    m = message.text.strip()

    player_message = []
    # restart will lose all TODO
    if str(message.from_user.id) not in llama_player_dict:
        llama_player_dict[str(message.from_user.id)] = (
            player_message  # for the imuutable list
        )
    else:
        player_message = llama_player_dict[str(message.from_user.id)]
    if m.strip() == "clear":
        bot.reply_to(
            message,
            "just clear your llama messages history",
        )
        player_message.clear()
        return
    if m[:4].lower() == "new ":
        m = m[4:].strip()
        player_message.clear()
    m = enrich_text_with_urls(m)

    who = "llama"
    # show something, make it more responsible
    reply_id = bot_reply_first(message, who, bot)

    player_message.append({"role": "user", "content": m})
    # keep the last 5, every has two ask and answer.
    if len(player_message) > 10:
        player_message = player_message[2:]

    llama_reply_text = ""
    try:
        r = client.chat.completions.create(
            messages=player_message, max_tokens=8192, model=LLAMA_MODEL
        )
        content = r.choices[0].message.content.encode("utf8").decode()
        if not content:
            llama_reply_text = f"{who} did not answer."
            player_message.pop()
        else:
            llama_reply_text = content
            player_message.append(
                {
                    "role": "assistant",
                    "content": llama_reply_text,
                }
            )

    except Exception as e:
        print(e)
        bot_reply_markdown(reply_id, who, "answer wrong", bot)
        # pop my user
        player_message.pop()
        return

    # reply back as Markdown and fallback to plain text if failed.
    bot_reply_markdown(reply_id, who, llama_reply_text, bot)


def llama_pro_handler(message: Message, bot: TeleBot) -> None:
    """llama_pro : /llama_pro <question>"""
    m = message.text.strip()

    player_message = []
    # restart will lose all TODO
    if str(message.from_user.id) not in llama_pro_player_dict:
        llama_pro_player_dict[str(message.from_user.id)] = (
            player_message  # for the imuutable list
        )
    else:
        player_message = llama_pro_player_dict[str(message.from_user.id)]
    if m.strip() == "clear":
        bot.reply_to(
            message,
            "just clear your llama messages history",
        )
        player_message.clear()
        return
    if m[:4].lower() == "new ":
        m = m[4:].strip()
        player_message.clear()
    m = enrich_text_with_urls(m)

    who = "llama Pro"
    reply_id = bot_reply_first(message, who, bot)

    player_message.append({"role": "user", "content": m})
    # keep the last 5, every has two ask and answer.
    if len(player_message) > 10:
        player_message = player_message[2:]

    try:
        r = client.chat.completions.create(
            messages=player_message,
            max_tokens=8192,
            model=LLAMA_PRO_MODEL,
            stream=True,
        )
        s = ""
        start = time.time()
        for chunk in r:
            if chunk.choices[0].delta.content is None:
                break
            s += chunk.choices[0].delta.content
            # 0.7 is enough for llama3 here its very fast
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
        bot_reply_markdown(reply_id, who, "answer wrong", bot)
        player_message.clear()
        return


if LLAMA_API_KEY:

    def register(bot: TeleBot) -> None:
        bot.register_message_handler(llama_handler, commands=["llama"], pass_bot=True)
        bot.register_message_handler(llama_handler, regexp="^llama:", pass_bot=True)
        bot.register_message_handler(
            llama_pro_handler, commands=["llama_pro"], pass_bot=True
        )
        bot.register_message_handler(
            llama_pro_handler, regexp="^llama_pro:", pass_bot=True
        )
