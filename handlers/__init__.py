from __future__ import annotations

import importlib
import re
import traceback
from functools import update_wrapper
from pathlib import Path
from typing import Any, Callable, TypeVar

from telebot import TeleBot
from telebot.types import BotCommand, Message

T = TypeVar("T", bound=Callable)


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
            if not m:
                bot.reply_to(message, "Please provide info after start words.")
                return
            return handler(message, *args, **kwargs)
        except Exception:
            traceback.print_exc()
            bot.reply_to(message, "Something wrong, please check the log")

    return update_wrapper(wrapper, handler)


def load_handlers(bot: TeleBot) -> None:
    # import all submodules
    this_path = Path(__file__).parent
    for child in this_path.iterdir():
        if child.name.startswith("_"):
            continue
        module = importlib.import_module(f".{child.stem}", __package__)
        if hasattr(module, "register"):
            print(f"Loading {child.stem} handlers.")
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
