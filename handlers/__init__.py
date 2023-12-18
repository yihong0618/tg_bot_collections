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
