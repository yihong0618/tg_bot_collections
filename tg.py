import argparse

from telebot import TeleBot

from config import settings
from handlers import list_available_commands, load_handlers


def setup_logging(debug: bool):
    import logging

    logger = logging.getLogger("bot")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - [%(levelname)s] - %(filename)s:%(lineno)d - %(message)s"
        )
    )
    logger.addHandler(handler)


def main():
    # Init args
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "tg_token", help="tg token", default=settings.telegram_bot_token, nargs="?"
    )
    parser.add_argument(
        "--debug", "--verbose", "-v", action="store_true", help="Enable debug mode"
    )

    # 'disable-command' option
    # The action 'append' will allow multiple entries to be saved into a list
    # The variable name is changed to 'disable_commands'
    parser.add_argument(
        "--disable-command",
        action="append",
        dest="disable_commands",
        help="Specify a command to disable. Can be used multiple times.",
        default=[],
        choices=list_available_commands(),
    )

    options = parser.parse_args()
    print("Arg parse done.")
    setup_logging(options.debug)

    # Init bot
    bot = TeleBot(options.tg_token)
    load_handlers(bot, options.disable_commands)
    print("Bot init done.")

    # Start bot
    print("Starting tg collections bot.")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)


if __name__ == "__main__":
    main()
