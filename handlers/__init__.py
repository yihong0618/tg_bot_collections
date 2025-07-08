import importlib
from pathlib import Path

from telebot import TeleBot
from telebot.types import BotCommand

from ._utils import logger, wrap_handler

DEFAULT_LOAD_PRIORITY = 10


def list_available_commands() -> list[str]:
    commands = []
    this_path = Path(__file__).parent
    for child in this_path.iterdir():
        if child.name.startswith("_"):
            continue
        commands.append(child.stem)
    return commands


def load_handlers(bot: TeleBot, disable_commands: list[str]) -> None:
    # import all submodules
    modules_with_priority = []
    for name in list_available_commands():
        if name in disable_commands:
            continue
        module = importlib.import_module(f".{name}", __package__)
        load_priority = getattr(module, "load_priority", DEFAULT_LOAD_PRIORITY)
        modules_with_priority.append((module, name, load_priority))

    modules_with_priority.sort(key=lambda x: x[-1])
    for module, name, priority in modules_with_priority:
        if hasattr(module, "register"):
            logger.debug(f"Loading {name} handlers with priority {priority}.")
            module.register(bot)
    logger.info("Loading handlers done.")

    all_commands: list[BotCommand] = []
    for handler in bot.message_handlers:
        help_text = getattr(handler["function"], "__doc__", "")
        # Add pre-processing and error handling to all callbacks
        handler["function"] = wrap_handler(handler["function"], bot)
        for command in handler["filters"].get("commands", []):
            all_commands.append(BotCommand(command, help_text))

    if all_commands:
        bot.set_my_commands(all_commands)
        logger.info("Setting commands done.")
