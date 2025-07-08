import json
import re
import time

# TODO: update requirements.txt and setup tools
# pip install dify-client
from dify_client import ChatClient
from telebot import TeleBot
from telebot.types import Message
from telegramify_markdown.customize import markdown_symbol

from ._utils import bot_reply_first, bot_reply_markdown, enrich_text_with_urls

# If you want, Customizing the head level 1 symbol
markdown_symbol.head_level_1 = "📌"
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol


def dify_handler(message: Message, bot: TeleBot) -> None:
    """dify : /dify API_Key <question>"""
    m = message.text.strip()

    if re.match(r"^app-\w+$", m, re.IGNORECASE):
        bot.reply_to(
            message,
            "Thanks!\nFor conversation, please make a space between your API_Key and your question.",
        )
        return
    if re.match(r"^app-[a-zA-Z0-9]+ .*$", m, re.IGNORECASE):
        Dify_API_KEY = m.split(" ", 1)[0]
        m = m.split(" ", 1)[1]
    else:
        bot.reply_to(message, "Please provide a valid API key.")
        return
    client = ChatClient(api_key=Dify_API_KEY)
    # Init client with API key

    m = enrich_text_with_urls(m)

    who = "dify"
    # show something, make it more responsible
    reply_id = bot_reply_first(message, who, bot)

    try:
        r = client.create_chat_message(
            inputs={},
            query=m,
            user=str(message.from_user.id),
            response_mode="streaming",
        )
        s = ""
        start = time.time()
        overall_start = time.time()
        for chunk in r.iter_lines(decode_unicode=True):
            chunk = chunk.split("data:", 1)[-1]
            if chunk.strip():
                chunk = json.loads(chunk.strip())
                answer_chunk = chunk.get("answer", "")
                s += answer_chunk
            if time.time() - start > 1.5:
                start = time.time()
                bot_reply_markdown(reply_id, who, s, bot, split_text=False)
            if time.time() - overall_start > 120:  # Timeout
                s += "\n\nTimeout"
                break
        # maybe not complete
        try:
            bot_reply_markdown(reply_id, who, s, bot)
        except:
            pass

    except Exception as e:
        print(e)
        bot.reply_to(message, "answer wrong maybe up to the max token")
        # pop my user
        return

    # reply back as Markdown and fallback to plain text if failed.
    bot_reply_markdown(reply_id, who, s, bot)


if True:

    def register(bot: TeleBot) -> None:
        bot.register_message_handler(dify_handler, commands=["dify"], pass_bot=True)
        bot.register_message_handler(dify_handler, regexp="^dify:", pass_bot=True)
