from os import environ

from telebot import TeleBot
from telebot.types import Message
from expiringdict import ExpiringDict

from . import *

# TODO: update requirements.txt and setup tools
# pip install dify-client
from dify_client import ChatClient
from telegramify_markdown import convert
from telegramify_markdown.customize import markdown_symbol

# If you want, Customizing the head level 1 symbol
markdown_symbol.head_level_1 = "📌"
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol

DIFY_API_KEY = environ.get("DIFY_API_KEY")

if DIFY_API_KEY:
    client = ChatClient(api_key=DIFY_API_KEY)

# Global history cache
dify_player_dict = ExpiringDict(max_len=1000, max_age_seconds=300)
dify_player_c = ExpiringDict(
    max_len=1000, max_age_seconds=300
)  # History cache is supported by dify cloud conversation_id.


def dify_handler(message: Message, bot: TeleBot) -> None:
    """dify : /dify <question>"""
    m = message.text.strip()
    c = None
    player_message = []
    # restart will lose all TODO
    if str(message.from_user.id) not in dify_player_dict:
        dify_player_dict[str(message.from_user.id)] = (
            player_message  # for the imuutable list
        )
    else:
        player_message = dify_player_dict[str(message.from_user.id)]
        # get c from dify_player_c
        c = dify_player_c.get(str(message.from_user.id), None)

    if m.strip() == "clear":
        bot.reply_to(
            message,
            "just clear your dify messages history",
        )
        player_message.clear()
        c = None
        return

    if m[:4].lower() == "new ":
        m = m[4:].strip()
        player_message.clear()
        c = None

    m = enrich_text_with_urls(m)

    who = "dify"
    # show something, make it more responsible
    reply_id = bot_reply_first(message, who, bot)

    player_message.append({"role": "user", "content": m})
    # keep the last 5, every has two ask and answer.
    if len(player_message) > 10:
        player_message = player_message[2:]

    dify_reply_text = ""
    try:
        r = client.create_chat_message(
            inputs={},
            query=m,
            user=str(message.from_user.id),
            response_mode="blocking",
            conversation_id=c,
        )
        j = r.json()

        content = j.get("answer", None)
        # get c by j.get then save c to dify_player_c
        dify_player_c[str(message.from_user.id)] = j.get("conversation_id", None)
        if not content:
            dify_reply_text = f"{who} did not answer."
            player_message.pop()
        else:
            dify_reply_text = content
            player_message.append(
                {
                    "role": "assistant",
                    "content": dify_reply_text,
                }
            )

    except Exception as e:
        print(e)
        bot_reply_markdown(reply_id, who, "answer wrong", bot)
        # pop my user
        player_message.pop()
        return

    # reply back as Markdown and fallback to plain text if failed.
    bot_reply_markdown(reply_id, who, dify_reply_text, bot)


if DIFY_API_KEY:

    def register(bot: TeleBot) -> None:
        bot.register_message_handler(dify_handler, commands=["dify"], pass_bot=True)
        bot.register_message_handler(dify_handler, regexp="^dify:", pass_bot=True)
