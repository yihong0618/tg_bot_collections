from urlextract import URLExtract
from telebot import TeleBot
from telebot.types import Message

from . import *


def tweet_handler(message: Message, bot: TeleBot):
    """tweet: /t <twitter/x web link>"""
    who = "tweet"

    extractor = URLExtract()
    links = extractor.find_urls(message.text)

    only_links = len("".join(links)) == len(message.text.strip())
    if links:
        reply_id = bot_reply_first(message, who, bot)
        processed_links = [
            link.replace("twitter.com", "fxtwitter.com").replace("x.com", "fixupx.com")
            for link in links
        ]
        bot_reply_markdown(reply_id, who, "\n".join(processed_links), bot)

        if only_links:
            bot.delete_message(message.chat.id, message.message_id)


def register(bot: TeleBot) -> None:
    bot.register_message_handler(tweet_handler, commands=["t"], pass_bot=True)
    bot.register_message_handler(tweet_handler, regexp="^t:", pass_bot=True)
