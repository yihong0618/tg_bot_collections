from __future__ import annotations

import base64
import logging
import re
from functools import update_wrapper
from mimetypes import guess_type
from typing import Any, Callable, TypeVar

import requests
import telegramify_markdown
from expiringdict import ExpiringDict
from telebot import TeleBot
from telebot.types import Message
from telebot.util import smart_split
from telegramify_markdown.customize import get_runtime_config
from urlextract import URLExtract

get_runtime_config().markdown_symbol.head_level_1 = (
    "📌"  # If you want, Customizing the head level 1 symbol
)
get_runtime_config().markdown_symbol.link = (
    "🔗"  # If you want, Customizing the link symbol
)

T = TypeVar("T", bound=Callable)
logger = logging.getLogger("bot")


BOT_MESSAGE_LENGTH = 4000

REPLY_MESSAGE_CACHE = ExpiringDict(max_len=1000, max_age_seconds=600)


def bot_reply_first(message: Message, who: str, bot: TeleBot) -> Message:
    """Create the first reply message which make user feel the bot is working."""
    return bot.reply_to(
        message, f"*{who}* is _thinking_ \.\.\.", parse_mode="MarkdownV2"
    )


def bot_reply_markdown(
    reply_id: Message,
    who: str,
    text: str,
    bot: TeleBot,
    split_text: bool = True,
    disable_web_page_preview: bool = False,
) -> bool:
    """
    reply the Markdown by take care of the message length.
    it will fallback to plain text in case of any failure
    """
    try:
        cache_key = f"{reply_id.chat.id}_{reply_id.message_id}"
        if cache_key in REPLY_MESSAGE_CACHE and REPLY_MESSAGE_CACHE[cache_key] == text:
            logger.info(f"Skipping duplicate message for {cache_key}")
            return True
        REPLY_MESSAGE_CACHE[cache_key] = text
        if len(text.encode("utf-8")) <= BOT_MESSAGE_LENGTH or not split_text:
            bot.edit_message_text(
                f"*{who}*:\n{telegramify_markdown.convert(text)}",
                chat_id=reply_id.chat.id,
                message_id=reply_id.message_id,
                parse_mode="MarkdownV2",
                disable_web_page_preview=disable_web_page_preview,
            )
            return True

        # Need a split of message
        msgs = smart_split(text, BOT_MESSAGE_LENGTH)
        bot.edit_message_text(
            f"*{who}* \[1/{len(msgs)}\]:\n{telegramify_markdown.convert(msgs[0])}",
            chat_id=reply_id.chat.id,
            message_id=reply_id.message_id,
            parse_mode="MarkdownV2",
            disable_web_page_preview=disable_web_page_preview,
        )
        for i in range(1, len(msgs)):
            bot.reply_to(
                reply_id.reply_to_message,
                f"*{who}* \[{i + 1}/{len(msgs)}\\]:\n{telegramify_markdown.convert(msgs[i])}",
                parse_mode="MarkdownV2",
            )

        return True
    except Exception:
        logger.exception("Error in bot_reply_markdown")
        # logger.info(f"wrong markdown format: {text}")
        bot.edit_message_text(
            f"*{who}*:\n{text}",
            chat_id=reply_id.chat.id,
            message_id=reply_id.message_id,
            disable_web_page_preview=disable_web_page_preview,
        )
        return False


def extract_prompt(message: str, bot_name: str) -> str:
    """
    This function filters messages for prompts.

    Returns:
      str: If it is not a prompt, return None. Otherwise, return the trimmed prefix of the actual prompt.
    """
    # remove '@bot_name' as it is considered part of the command when in a group chat.
    message = re.sub(re.escape(f"@{bot_name}"), "", message).strip()
    # add a whitespace after the first colon as we separate the prompt from the command by the first whitespace.
    message = re.sub(":", ": ", message, count=1).strip()
    try:
        left, message = message.split(maxsplit=1)
    except ValueError:
        return ""
    if ":" not in left:
        # the replacement happens in the right part, restore it.
        message = message.replace(": ", ":", 1)
    return message.strip()


def remove_prompt_prefix(message: str) -> str:
    """
    Remove "/cmd" or "/cmd@bot_name" or "cmd:"
    """
    message += " "
    # Explanation of the regex pattern:
    # ^                        - Match the start of the string
    # (                        - Start of the group
    #   /                      - Literal forward slash
    #   [a-zA-Z]               - Any letter (start of the command)
    #   [a-zA-Z0-9_]*          - Any number of letters, digits, or underscores
    #   (@\w+)?                - Optionally match @ followed by one or more word characters (for bot name)
    #   \s                     - A single whitespace character (space or newline)
    # |                        - OR
    #   [a-zA-Z]               - Any letter (start of the command)
    #   [a-zA-Z0-9_]*          - Any number of letters, digits, or underscores
    #   :\s                    - Colon followed by a single whitespace character
    # )                        - End of the group
    pattern = r"^(/[a-zA-Z][a-zA-Z0-9_]*(@\w+)?\s|[a-zA-Z][a-zA-Z0-9_]*:\s)"

    return re.sub(pattern, "", message).strip()


def non_llm_handler(handler: T) -> T:
    handler.__is_llm_handler__ = False
    return handler


def wrap_handler(handler: T, bot: TeleBot) -> T:
    def wrapper(message: Message, *args: Any, **kwargs: Any) -> None:
        try:
            if getattr(handler, "__is_llm_handler__", True):
                m = ""

                if message.text is not None:
                    m = message.text = extract_prompt(
                        message.text, bot.get_me().username
                    )
                elif message.caption is not None:
                    m = message.caption = extract_prompt(
                        message.caption, bot.get_me().username
                    )
                elif message.location and message.location.latitude is not None:
                    # for location map handler just return
                    return handler(message, *args, **kwargs)
                if not m:
                    bot.reply_to(message, "Please provide info after start words.")
                    return
            return handler(message, *args, **kwargs)
        except Exception as e:
            logger.exception("Error in handler %s: %s", handler.__name__, e)
            # handle more here
            if str(e).find("RECITATION") > 0:
                bot.reply_to(message, "Your prompt `RECITATION` please check the log")
            else:
                bot.reply_to(message, "Something wrong, please check the log")

    return update_wrapper(wrapper, handler)


def extract_url_from_text(text: str) -> list[str]:
    extractor = URLExtract()
    urls = extractor.find_urls(text)
    return urls


def get_text_from_jina_reader(url: str):
    try:
        r = requests.get(f"https://r.jina.ai/{url}")
        return r.text
    except Exception as e:
        logger.exception("Error fetching text from Jina reader: %s", e)
        return None


def enrich_text_with_urls(text: str) -> str:
    urls = extract_url_from_text(text)
    for u in urls:
        try:
            url_text = get_text_from_jina_reader(u)
            url_text = f"\n```markdown\n{url_text}\n```\n"
            text = text.replace(u, url_text)
        except Exception:
            # just ignore the error
            pass

    return text


def image_to_data_uri(file_path):
    content_type = guess_type(file_path)[0]
    with open(file_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
        return f"data:{content_type};base64,{encoded_image}"
