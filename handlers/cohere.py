import datetime
import re
import time
from os import environ

import cohere
from expiringdict import ExpiringDict
from telebot import TeleBot
from telebot.types import Message
from telegramify_markdown import convert
from telegramify_markdown.customize import markdown_symbol

from config import settings

from ._utils import bot_reply_first, bot_reply_markdown, enrich_text_with_urls

markdown_symbol.head_level_1 = "📌"  # If you want, Customizing the head level 1 symbol
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol

COHERE_API_KEY = environ.get("COHERE_API_KEY")
COHERE_MODEL = "command-r-plus"  # command-r may cause Chinese garbled code, and non stream mode also may cause garbled code.
if COHERE_API_KEY:
    co = cohere.Client(api_key=COHERE_API_KEY)


# Global history cache
cohere_player_dict = ExpiringDict(max_len=1000, max_age_seconds=600)


def clean_text(text):
    """Clean up the garbled code in the UTF-8 encoded Chinese string.

    Args:
      text: String that needs to be cleaned.

    Returns:
      The cleaned string, if garbled code is detected, a prompt message is added at the end.
    """
    if "�" in text:
        # Use re.sub to clean up garbled code
        cleaned_text = re.sub(r"�.*?([，。！？；：]|$)", r"\1", text)
        cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()
        print(f"\n---------\nOriginal text:\n{text}\n---------")
        return cleaned_text + "\n\n~~(乱码已去除，可能存在错误，请注意)~~"
    else:
        return text


def cohere_handler(message: Message, bot: TeleBot) -> None:
    """cohere : /cohere_pro <question> Come with a telegraph link"""
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
        current_time = datetime.datetime.now(datetime.timezone.utc)
        preamble = (
            f"You are Command, a large language model trained to have polite, helpful, and inclusive conversations with people. Your responses should be accurate and graceful in user's original language."
            f"The current UTC time is {current_time.strftime('%Y-%m-%d %H:%M:%S')}, "
            f"UTC-4 (e.g. New York) is {current_time.astimezone(datetime.timezone(datetime.timedelta(hours=-4))).strftime('%Y-%m-%d %H:%M:%S')}, "
            f"UTC-7 (e.g. Los Angeles) is {current_time.astimezone(datetime.timezone(datetime.timedelta(hours=-7))).strftime('%Y-%m-%d %H:%M:%S')}, "
            f"and UTC+8 (e.g. Beijing) is {current_time.astimezone(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')}."
        )
        stream = co.chat_stream(
            model=COHERE_MODEL,
            message=m,
            temperature=0.8,
            chat_history=player_message,
            prompt_truncation="AUTO",
            connectors=[{"id": "web-search"}],
            citation_quality="accurate",
            preamble=preamble,
        )

        s = ""
        source = ""
        start = time.time()
        for event in stream:
            if event.event_type == "stream-start":
                bot_reply_markdown(reply_id, who, "Thinking...", bot)
            elif event.event_type == "search-queries-generation":
                bot_reply_markdown(reply_id, who, "Searching online...", bot)
            elif event.event_type == "search-results":
                bot_reply_markdown(reply_id, who, "Reading...", bot)
                for doc in event.documents:
                    source += f"\n{doc['title']}\n{doc['url']}\n"
            elif event.event_type == "text-generation":
                s += event.text.encode("utf-8").decode("utf-8")
                if time.time() - start > 1.4:
                    start = time.time()
                    s = clean_text(s)
                    if len(s) > 3900:
                        bot_reply_markdown(
                            reply_id,
                            who,
                            f"\nStill thinking{len(s)}...\n",
                            bot,
                            split_text=True,
                        )
                    else:
                        bot_reply_markdown(
                            reply_id,
                            who,
                            f"\nStill thinking{len(s)}...\n{s}",
                            bot,
                            split_text=True,
                        )
            elif event.event_type == "stream-end":
                break
        content = (
            s
            + "\n\n---\n"
            + source
            + f"\nLast Update{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} at UTC+8\n"
        )
        ph_s = settings.telegraph_client.create_page_md(
            title="Cohere", markdown_text=content
        )  # or edit_page with get_page so not producing massive pages
        s += f"\n\n[View]({ph_s})"

        try:
            bot_reply_markdown(
                reply_id, who, s, bot, split_text=True, disable_web_page_preview=True
            )
        except Exception:
            pass

        player_message.append(
            {
                "role": "Chatbot",
                "message": convert(s),
            }
        )

    except Exception as e:
        print(e)
        bot.reply_to(message, "answer wrong maybe up to the max token")
        player_message.clear()
        return


if COHERE_API_KEY:

    def register(bot: TeleBot) -> None:
        bot.register_message_handler(cohere_handler, commands=["cohere"], pass_bot=True)
        bot.register_message_handler(cohere_handler, regexp="^cohere:", pass_bot=True)
