import argparse

from telebot import TeleBot

from handlers import load_handlers


def main():
    # Init args
    parser = argparse.ArgumentParser()
    parser.add_argument("tg_token", help="tg token")
    options = parser.parse_args()
    print("Arg parse done.")

    # Init bot
    bot = TeleBot(options.tg_token)
    load_handlers(bot)
    print("Bot init done.")

    # Start bot
    print("Starting tg collections bot.")
    bot.infinity_polling()


if __name__ == "__main__":
    main()
