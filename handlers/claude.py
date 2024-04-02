from os import environ
from pathlib import Path
import time

from anthropic import Anthropic, APITimeoutError
from telebot import TeleBot
from telebot.types import Message

from . import *

from telegramify_markdown import convert
from telegramify_markdown.customize import markdown_symbol

markdown_symbol.head_level_1 = "📌"  # If you want, Customizing the head level 1 symbol
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol

ANTHROPIC_API_KEY = environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_BASE_URL = environ.get("ANTHROPIC_BASE_URL")
ANTHROPIC_MODEL = "claude-3-haiku-20240307"
ANTHROPIC_PRO_MODEL = "claude-3-opus-20240229"

client = Anthropic(base_url=ANTHROPIC_BASE_URL, api_key=ANTHROPIC_API_KEY, timeout=20)

# Global history cache
claude_player_dict = {}
claude_pro_player_dict = {}


def claude_handler(message: Message, bot: TeleBot) -> None:
    """claude : /claude <question>"""
    m = message.text.strip()
    player_message = []
    # restart will lose all TODO
    if str(message.from_user.id) not in claude_player_dict:
        claude_player_dict[str(message.from_user.id)] = (
            player_message  # for the imuutable list
        )
    else:
        player_message = claude_player_dict[str(message.from_user.id)]

    if m.strip() == "clear":
        bot.reply_to(
            message,
            "just clear you claude messages history",
        )
        player_message.clear()
        return

    # show something, make it more responsible
    reply_id = bot_reply_first(message, "Claude", bot)

    player_message.append({"role": "user", "content": m})
    # keep the last 5, every has two ask and answer.
    if len(player_message) > 10:
        player_message = player_message[2:]

    claude_reply_text = ""
    try:
        if len(player_message) > 2:
            if player_message[-1]["role"] == player_message[-2]["role"]:
                # tricky
                player_message.pop()
        r = client.messages.create(
            max_tokens=4096, messages=player_message, model=ANTHROPIC_MODEL
        )
        if not r.content:
            claude_reply_text = "Claude did not answer."
            player_message.pop()
        else:
            claude_reply_text = r.content[0].text
            player_message.append(
                {
                    "role": r.role,
                    "content": r.content,
                }
            )

    except APITimeoutError:
        bot.reply_to(
            message,
            "claude answer:\n" + "claude answer timeout",
            parse_mode="MarkdownV2",
        )
        # pop my user
        player_message.clear()
        return

    bot_reply_markdown(reply_id, "Claude", claude_reply_text, bot)


def claude_pro_handler(message: Message, bot: TeleBot) -> None:
    """claude_pro : /claude_pro <question> TODO refactor"""
    m = message.text.strip()
    player_message = []
    if str(message.from_user.id) not in claude_pro_player_dict:
        claude_pro_player_dict[str(message.from_user.id)] = (
            player_message  # for the imuutable list
        )
    else:
        player_message = claude_pro_player_dict[str(message.from_user.id)]
    q = m.strip()
    if q == "clear" or len(q) == 0:
        bot.reply_to(
            message,
            "just clear you claude opus messages history",
        )
        player_message.clear()
        return

    player_message.append({"role": "user", "content": m})
    # keep the last 5, every has two ask and answer.
    if len(player_message) > 10:
        player_message = player_message[2:]

    try:
        if len(player_message) > 2:
            if player_message[-1]["role"] == player_message[-2]["role"]:
                # tricky
                player_message.pop()
        r = client.messages.create(
            max_tokens=2048,
            messages=player_message,
            model=ANTHROPIC_PRO_MODEL,
            stream=True,
        )
        s = ""
        start = time.time()
        is_send = True
        reply_id = None
        for e in r:
            if e.type == "content_block_delta":
                s += e.delta.text
            if time.time() - start > 1.7:
                start = time.time()
                if is_send:
                    reply_id = bot.reply_to(
                        message,
                        convert(s),
                        parse_mode="MarkdownV2",
                    )
                    is_send = False
                else:
                    try:
                        # maybe the same message
                        if not reply_id:
                            continue
                        bot.edit_message_text(
                            message_id=reply_id.message_id,
                            chat_id=reply_id.chat.id,
                            text=convert(s),
                            parse_mode="MarkdownV2",
                        )
                    except Exception as e:
                        print(str(e))
        try:
            # maybe not complete
            # maybe the same message
            bot.edit_message_text(
                message_id=reply_id.message_id,
                chat_id=reply_id.chat.id,
                text=convert(s),
                parse_mode="MarkdownV2",
            )
        except Exception as e:
            player_message.clear()
            print(str(e))
            return

        player_message.append(
            {
                "role": "assistant",
                "content": convert(s),
            }
        )

    except APITimeoutError:
        bot.reply_to(
            message,
            "claude answer:\n" + "claude answer timeout",
            parse_mode="MarkdownV2",
        )
        # pop my user
        player_message.clear()
        return


def claude_photo_handler(message: Message, bot: TeleBot) -> None:
    s = message.caption
    reply_message = bot.reply_to(
        message,
        "Generating claude vision answer please wait.",
    )
    prompt = s.strip()
    # get the high quaility picture.
    max_size_photo = max(message.photo, key=lambda p: p.file_size)
    file_path = bot.get_file(max_size_photo.file_id).file_path
    downloaded_file = bot.download_file(file_path)
    with open("claude_temp.jpg", "wb") as temp_file:
        temp_file.write(downloaded_file)

    f = Path("claude_temp.jpg")
    try:
        with f:
            r = client.messages.create(
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt,
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": f,
                                },
                            },
                        ],
                    },
                ],
                model=ANTHROPIC_MODEL,
            )
            bot.reply_to(message, "Claude vision answer:\n" + r.content[0].text)
    except Exception as e:
        print(e)
        bot.reply_to(
            message,
            "Claude vision answer:\n" + "claude vision answer wrong",
            parse_mode="MarkdownV2",
        )
    finally:
        bot.delete_message(reply_message.chat.id, reply_message.message_id)


def register(bot: TeleBot) -> None:
    bot.register_message_handler(claude_handler, commands=["claude"], pass_bot=True)
    bot.register_message_handler(claude_handler, regexp="^claude:", pass_bot=True)
    bot.register_message_handler(
        claude_pro_handler, commands=["claude_pro"], pass_bot=True
    )
    bot.register_message_handler(
        claude_pro_handler, regexp="^claude_pro:", pass_bot=True
    )
    bot.register_message_handler(
        claude_photo_handler,
        content_types=["photo"],
        func=lambda m: m.caption and m.caption.startswith(("claude:", "/claude")),
        pass_bot=True,
    )
