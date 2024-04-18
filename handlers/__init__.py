from __future__ import annotations

import base64
import importlib
import re
import traceback
from functools import update_wrapper
from pathlib import Path
from typing import Any, Callable, TypeVar

import requests
from telebot import TeleBot
from telebot.types import BotCommand, Message
from telebot.util import smart_split
import telegramify_markdown
from telegramify_markdown.customize import markdown_symbol
from urlextract import URLExtract

markdown_symbol.head_level_1 = "📌"  # If you want, Customizing the head level 1 symbol
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol

T = TypeVar("T", bound=Callable)

BOT_MESSAGE_LENGTH = 4000


def bot_reply_first(message: Message, who: str, bot: TeleBot) -> Message:
    """Create the first reply message which make user feel the bot is working."""
    return bot.reply_to(
        message, f"*{who}* is _thinking_ \.\.\.", parse_mode="MarkdownV2"
    )


def bot_reply_markdown(
    reply_id: Message, who: str, text: str, bot: TeleBot, split_text: bool = True
) -> bool:
    """
    reply the Markdown by take care of the message length.
    it will fallback to plain text in case of any failure
    """
    try:
        if len(text.encode("utf-8")) <= BOT_MESSAGE_LENGTH or not split_text:
            bot.edit_message_text(
                f"*{who}*:\n{telegramify_markdown.convert(text)}",
                chat_id=reply_id.chat.id,
                message_id=reply_id.message_id,
                parse_mode="MarkdownV2",
            )
            return True

        # Need a split of message
        msgs = smart_split(text, BOT_MESSAGE_LENGTH)
        bot.edit_message_text(
            f"*{who}* \[1/{len(msgs)}\]:\n{telegramify_markdown.convert(msgs[0])}",
            chat_id=reply_id.chat.id,
            message_id=reply_id.message_id,
            parse_mode="MarkdownV2",
        )
        for i in range(1, len(msgs)):
            bot.reply_to(
                reply_id.reply_to_message,
                f"*{who}* \[{i+1}/{len(msgs)}\]:\n{telegramify_markdown.convert(msgs[i])}",
                parse_mode="MarkdownV2",
            )

        return True
    except Exception as e:
        print(traceback.format_exc())
        # print(f"wrong markdown format: {text}")
        bot.edit_message_text(
            f"*{who}*:\n{text}",
            chat_id=reply_id.chat.id,
            message_id=reply_id.message_id,
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


def wrap_handler(handler: T, bot: TeleBot) -> T:
    def wrapper(message: Message, *args: Any, **kwargs: Any) -> None:
        try:
            m = ""
            if message.text is not None:
                m = message.text = extract_prompt(message.text, bot.get_me().username)
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
            traceback.print_exc()
            # handle more here
            if str(e).find("RECITATION") > 0:
                bot.reply_to(message, "Your prompt `RECITATION` please check the log")
            else:
                bot.reply_to(message, "Something wrong, please check the log")

    return update_wrapper(wrapper, handler)


def load_handlers(bot: TeleBot, disable_commands: list[str]) -> None:
    # import all submodules
    for name in list_available_commands():
        if name in disable_commands:
            continue
        module = importlib.import_module(f".{name}", __package__)
        if hasattr(module, "register"):
            print(f"Loading {name} handlers.")
            module.register(bot)
    print("Loading handlers done.")

    all_commands: list[BotCommand] = []
    for handler in bot.message_handlers:
        help_text = getattr(handler["function"], "__doc__", "")
        # Add pre-processing and error handling to all callbacks
        handler["function"] = wrap_handler(handler["function"], bot)
        for command in handler["filters"].get("commands", []):
            all_commands.append(BotCommand(command, help_text))

    if all_commands:
        bot.set_my_commands(all_commands)
        print("Setting commands done.")


def list_available_commands() -> list[str]:
    commands = []
    this_path = Path(__file__).parent
    for child in this_path.iterdir():
        if child.name.startswith("_"):
            continue
        commands.append(child.stem)
    return commands


def extract_url_from_text(text: str) -> list[str]:
    extractor = URLExtract()
    urls = extractor.find_urls(text)
    return urls


def get_text_from_jina_reader(url: str):
    try:
        r = requests.get(f"https://r.jina.ai/{url}")
        return r.text
    except Exception as e:
        print(e)
        return None


def enrich_text_with_urls(text: str) -> str:
    urls = extract_url_from_text(text)
    for u in urls:
        try:
            url_text = get_text_from_jina_reader(u)
            url_text = f"\n```markdown\n{url_text}\n```\n"
            text = text.replace(u, url_text)
        except Exception as e:
            # just ignore the error
            pass

    return text


def image_to_data_uri(file_path):
    with open(file_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
        return f"data:image/png;base64,{encoded_image}"


# `import *` will give you these
__all__ = [
    "bot_reply_first",
    "bot_reply_markdown",
    "enrich_text_with_urls",
    "image_to_data_uri",
]
