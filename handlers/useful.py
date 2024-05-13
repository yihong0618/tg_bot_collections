# useful md for myself and you.

from telebot import TeleBot
from telebot.types import Message


from . import *


def md_handler(message: Message, bot: TeleBot):
    """pretty md: /md <address>"""
    who = "Markdown"
    reply_id = bot_reply_first(message, who, bot)
    bot_reply_markdown(reply_id, who, message.text.strip(), bot)


def register(bot: TeleBot) -> None:
    bot.register_message_handler(md_handler, commands=["md"], pass_bot=True)
    bot.register_message_handler(md_handler, regexp="^md:", pass_bot=True)
