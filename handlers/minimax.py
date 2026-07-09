import time

from expiringdict import ExpiringDict
from openai import OpenAI
from telebot import TeleBot
from telebot.types import Message
from telegramify_markdown import markdownify

from config import settings

from ._utils import bot_reply_first, bot_reply_markdown, enrich_text_with_urls, logger

MINIMAX_MODEL = settings.minimax_model

if settings.minimax_api_key:
    client = OpenAI(
        api_key=settings.minimax_api_key,
        base_url=settings.minimax_base_url,
    )

# Global history cache
minimax_player_dict = ExpiringDict(max_len=1000, max_age_seconds=600)
minimax_pro_player_dict = ExpiringDict(max_len=1000, max_age_seconds=600)


def minimax_handler(message: Message, bot: TeleBot) -> None:
    """minimax : /minimax <question>"""
    m = message.text.strip()

    player_message = []
    if str(message.from_user.id) not in minimax_player_dict:
        minimax_player_dict[str(message.from_user.id)] = player_message
    else:
        player_message = minimax_player_dict[str(message.from_user.id)]
    if m.strip() == "clear":
        bot.reply_to(
            message,
            "just clear your minimax messages history",
        )
        player_message.clear()
        return
    if m[:4].lower() == "new ":
        m = m[4:].strip()
        player_message.clear()
    m = enrich_text_with_urls(m)

    who = "MiniMax"
    reply_id = bot_reply_first(message, who, bot)

    player_message.append({"role": "user", "content": m})
    if len(player_message) > 10:
        player_message = player_message[2:]

    minimax_reply_text = ""
    try:
        r = client.chat.completions.create(
            messages=player_message, max_tokens=4096, model=MINIMAX_MODEL
        )
        content = r.choices[0].message.content.encode("utf8").decode()
        if not content:
            minimax_reply_text = f"{who} did not answer."
            player_message.pop()
        else:
            minimax_reply_text = content
            player_message.append(
                {
                    "role": "assistant",
                    "content": minimax_reply_text,
                }
            )

    except Exception:
        logger.exception("MiniMax handler error")
        bot.reply_to(message, "answer wrong maybe up to the max token")
        player_message.pop()
        return

    bot_reply_markdown(reply_id, who, minimax_reply_text, bot)


def minimax_pro_handler(message: Message, bot: TeleBot) -> None:
    """minimax_pro : /minimax_pro <question>"""
    m = message.text.strip()

    player_message = []
    if str(message.from_user.id) not in minimax_pro_player_dict:
        minimax_pro_player_dict[str(message.from_user.id)] = player_message
    else:
        player_message = minimax_pro_player_dict[str(message.from_user.id)]
    if m.strip() == "clear":
        bot.reply_to(
            message,
            "just clear your minimax messages history",
        )
        player_message.clear()
        return
    if m[:4].lower() == "new ":
        m = m[4:].strip()
        player_message.clear()
    m = enrich_text_with_urls(m)

    who = "MiniMax Pro"
    reply_id = bot_reply_first(message, who, bot)

    player_message.append({"role": "user", "content": m})
    if len(player_message) > 10:
        player_message = player_message[2:]

    try:
        r = client.chat.completions.create(
            messages=player_message,
            max_tokens=8192,
            model=MINIMAX_MODEL,
            stream=True,
        )
        s = ""
        start = time.time()
        for chunk in r:
            if chunk.choices[0].delta.content is None:
                break
            s += chunk.choices[0].delta.content
            if time.time() - start > 1.7:
                start = time.time()
                bot_reply_markdown(reply_id, who, s, bot, split_text=False)

        if not bot_reply_markdown(reply_id, who, s, bot):
            player_message.clear()
            return

        player_message.append(
            {
                "role": "assistant",
                "content": markdownify(s),
            }
        )

    except Exception:
        logger.exception("MiniMax Pro handler error")
        bot.reply_to(message, "answer wrong maybe up to the max token")
        player_message.clear()
        return


if settings.minimax_api_key:

    def register(bot: TeleBot) -> None:
        bot.register_message_handler(minimax_handler, commands=["minimax"], pass_bot=True)
        bot.register_message_handler(minimax_handler, regexp="^minimax:", pass_bot=True)
        bot.register_message_handler(
            minimax_pro_handler, commands=["minimax_pro"], pass_bot=True
        )
        bot.register_message_handler(
            minimax_pro_handler, regexp="^minimax_pro:", pass_bot=True
        )
