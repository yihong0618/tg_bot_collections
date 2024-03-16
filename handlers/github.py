import subprocess

from telebot import TeleBot
from telebot.types import Message


def github_poster_handler(message: Message, bot: TeleBot):
    """github poster: /github <github_user_name> [<start>-<end>]"""
    m = message.text.strip()
    message_list = m.split(",")
    name = message_list[0].strip()
    cmd_list = ["github_poster", "github", "--github_user_name", name, "--me", name]
    if len(message_list) > 1:
        years = message_list[1]
        cmd_list.append("--year")
        cmd_list.append(years.strip())
    r = subprocess.check_output(cmd_list).decode("utf-8")
    try:
        if "done" in r:
            # TODO windows path
            r = subprocess.check_output(
                ["cairosvg", "OUT_FOLDER/github.svg", "-o", f"github_{name}.png"]
            ).decode("utf-8")
            with open(f"github_{name}.png", "rb") as photo:
                bot.send_photo(
                    message.chat.id, photo, reply_to_message_id=message.message_id
                )
    except:
        bot.reply_to(message, "github poster error")


def register(bot: TeleBot) -> None:
    bot.register_message_handler(
        github_poster_handler, commands=["github"], pass_bot=True
    )
    bot.register_message_handler(
        github_poster_handler, regexp="^github:", pass_bot=True
    )
