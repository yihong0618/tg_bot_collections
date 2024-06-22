from os import environ
import time

from telebot import TeleBot
from telebot.types import Message
from expiringdict import ExpiringDict

from . import *

import cohere
from telegramify_markdown import convert
from telegramify_markdown.customize import markdown_symbol

markdown_symbol.head_level_1 = "📌"  # If you want, Customizing the head level 1 symbol
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol

COHERE_API_KEY = environ.get("COHERE_API_KEY")
COHERE_MODEL = "command-r-plus"

TELEGRA_PH_TOKEN = environ.get("TELEGRA_PH_TOKEN")
if TELEGRA_PH_TOKEN:
    ph = TelegraphAPI(TELEGRA_PH_TOKEN)

if COHERE_API_KEY:
    co = cohere.Client(api_key=COHERE_API_KEY)

# Global history cache
cohere_player_dict = ExpiringDict(max_len=1000, max_age_seconds=300)


def cohere_handler_direct(message: Message, bot: TeleBot) -> None:
    """cohere : /cohere <question>"""
    m = message.text.strip()

    player_message = []
    if str(message.from_user.id) not in cohere_player_dict:
        cohere_player_dict[str(message.from_user.id)] = player_message
    else:
        player_message = cohere_player_dict[str(message.from_user.id)]

    if m.strip() == "clear":
        bot.reply_to(
            message,
            "Just cleared your Cohere messages history",
        )
        player_message.clear()
        return

    if m[:4].lower() == "new ":
        m = m[4:].strip()
        player_message.clear()

    m = enrich_text_with_urls(m)

    who = "Command R Plus"
    reply_id = bot_reply_first(message, who, bot)

    player_message.append({"role": "User", "message": m})
    # keep the last 5, every has two ask and answer.
    if len(player_message) > 10:
        player_message = player_message[2:]

    try:
        stream = co.chat_stream(
            model=COHERE_MODEL,
            message=m,
            temperature=0.8,
            chat_history=player_message,
            prompt_truncation="AUTO",
            connectors=[{"id": "web-search"}],
            citation_quality="accurate",
        )

        s = ""
        source = ""
        start = time.time()
        for event in stream:
            if event.event_type == "text-generation":
                s += event.text.encode("utf-8").decode("utf-8")
                if time.time() - start > 1.2:
                    start = time.time()
                    bot_reply_markdown(reply_id, who, s, bot, split_text=True)
            elif event.event_type == "search-results":
                for doc in event.documents:
                    source += f"\n[{doc['title']}]({doc['url']})"
            elif event.event_type == "stream-end":
                break

        s += "\n" + source + "\n"

        if not bot_reply_markdown(reply_id, who, s, bot):
            # maybe not complete
            # maybe the same message
            player_message.clear()
            return

        player_message.append(
            {
                "role": "Chatbot",
                "message": convert(s),
            }
        )

    except Exception as e:
        print(e)
        bot_reply_markdown(reply_id, who, "Answer wrong", bot)
        player_message.clear()
        return


def cohere_handler(message: Message, bot: TeleBot) -> None:
    """cohere : /cohere <question>"""
    m = message.text.strip()

    player_message = []
    if str(message.from_user.id) not in cohere_player_dict:
        cohere_player_dict[str(message.from_user.id)] = player_message
    else:
        player_message = cohere_player_dict[str(message.from_user.id)]

    if m.strip() == "clear":
        bot.reply_to(
            message,
            "Just cleared your Cohere messages history",
        )
        player_message.clear()
        return

    if m[:4].lower() == "new ":
        m = m[4:].strip()
        player_message.clear()

    m = enrich_text_with_urls(m)

    who = "Command R Plus"
    reply_id = bot_reply_first(message, who, bot)

    player_message.append({"role": "User", "message": m})
    # keep the last 5, every has two ask and answer.
    if len(player_message) > 10:
        player_message = player_message[2:]

    try:
        stream = co.chat_stream(
            model=COHERE_MODEL,
            message=m,
            temperature=0.8,
            chat_history=player_message,
            prompt_truncation="AUTO",
            connectors=[{"id": "web-search"}],
            citation_quality="accurate",
        )

        s = ""
        source = ""
        start = time.time()
        for event in stream:
            if event.event_type == "text-generation":
                s += event.text.encode("utf-8").decode("utf-8")
                if time.time() - start > 1.2:
                    start = time.time()
                    bot_reply_markdown(reply_id, who, s, bot, split_text=False)
            elif event.event_type == "search-results":
                for doc in event.documents:
                    source += f"\n{doc['title']}\n{doc['url']}\n"
            elif event.event_type == "stream-end":
                break
        content = s + "\n------\n------\n" + source
        ph_s = ph.create_page_md(title="Cohere", markdown_text=content)
        s += f"\n\n[View]({ph_s})"

        if not bot_reply_markdown(reply_id, who, s, bot):
            # maybe not complete
            # maybe the same message
            player_message.clear()
            return

        player_message.append(
            {
                "role": "Chatbot",
                "message": convert(s),
            }
        )

    except Exception as e:
        print(e)
        bot_reply_markdown(reply_id, who, "Answer wrong", bot)
        player_message.clear()
        return


if COHERE_API_KEY:
    if not TELEGRA_PH_TOKEN:

        def register(bot: TeleBot) -> None:
            bot.register_message_handler(
                cohere_handler_direct, commands=["cohere"], pass_bot=True
            )
            bot.register_message_handler(
                cohere_handler_direct, regexp="^cohere:", pass_bot=True
            )

    else:

        def register(bot: TeleBot) -> None:
            bot.register_message_handler(
                cohere_handler, commands=["cohere"], pass_bot=True
            )
            bot.register_message_handler(
                cohere_handler, regexp="^cohere:", pass_bot=True
            )
