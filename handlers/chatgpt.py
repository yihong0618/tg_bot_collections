import time

from expiringdict import ExpiringDict
from telebot import TeleBot
from telebot.types import Message
from telegramify_markdown import convert
from telegramify_markdown.customize import markdown_symbol

from config import settings

from ._utils import (
    bot_reply_first,
    bot_reply_markdown,
    enrich_text_with_urls,
    image_to_data_uri,
    logger,
)

markdown_symbol.head_level_1 = "📌"  # If you want, Customizing the head level 1 symbol
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol

CHATGPT_MODEL = settings.openai_model
CHATGPT_PRO_MODEL = settings.openai_model


client = settings.openai_client


# Global history cache
chatgpt_player_dict = ExpiringDict(max_len=1000, max_age_seconds=600)
chatgpt_pro_player_dict = ExpiringDict(max_len=1000, max_age_seconds=600)


def chatgpt_handler(message: Message, bot: TeleBot) -> None:
    """gpt : /gpt <question>"""
    logger.debug(message)
    m = message.text.strip()

    player_message = []
    # restart will lose all TODO
    if str(message.from_user.id) not in chatgpt_player_dict:
        chatgpt_player_dict[str(message.from_user.id)] = (
            player_message  # for the imuutable list
        )
    else:
        player_message = chatgpt_player_dict[str(message.from_user.id)]
    if m.strip() == "clear":
        bot.reply_to(
            message,
            "just clear your chatgpt messages history",
        )
        player_message.clear()
        return
    if m[:4].lower() == "new ":
        m = m[4:].strip()
        player_message.clear()
    m = enrich_text_with_urls(m)

    who = "ChatGPT"
    # show something, make it more responsible
    reply_id = bot_reply_first(message, who, bot)

    player_message.append({"role": "user", "content": m})
    # keep the last 5, every has two ask and answer.
    if len(player_message) > 10:
        player_message = player_message[2:]

    chatgpt_reply_text = ""
    try:
        r = client.chat.completions.create(
            messages=player_message, max_tokens=1024, model=CHATGPT_MODEL
        )
        content = r.choices[0].message.content.encode("utf8").decode()
        if not content:
            chatgpt_reply_text = f"{who} did not answer."
            player_message.pop()
        else:
            chatgpt_reply_text = content
            player_message.append(
                {
                    "role": "assistant",
                    "content": chatgpt_reply_text,
                }
            )

    except Exception:
        logger.exception("ChatGPT handler error")
        bot.reply_to(message, "answer wrong maybe up to the max token")
        # pop my user
        player_message.pop()
        return

    # reply back as Markdown and fallback to plain text if failed.
    bot_reply_markdown(reply_id, who, chatgpt_reply_text, bot)


def chatgpt_pro_handler(message: Message, bot: TeleBot) -> None:
    """gpt_pro : /gpt_pro <question>"""
    m = message.text.strip()

    player_message = []
    # restart will lose all TODO
    if str(message.from_user.id) not in chatgpt_pro_player_dict:
        chatgpt_pro_player_dict[str(message.from_user.id)] = (
            player_message  # for the imuutable list
        )
    else:
        player_message = chatgpt_pro_player_dict[str(message.from_user.id)]
    if m.strip() == "clear":
        bot.reply_to(
            message,
            "just clear your chatgpt messages history",
        )
        player_message.clear()
        return
    if m[:4].lower() == "new ":
        m = m[4:].strip()
        player_message.clear()
    m = enrich_text_with_urls(m)

    who = "ChatGPT Pro"
    reply_id = bot_reply_first(message, who, bot)

    player_message.append({"role": "user", "content": m})
    # keep the last 3, every has two ask and answer.
    # save me some money
    if len(player_message) > 6:
        player_message = player_message[2:]

    try:
        r = client.chat.completions.create(
            messages=player_message,
            model=CHATGPT_PRO_MODEL,
            stream=True,
        )
        s = ""
        start = time.time()
        for chunk in r:
            logger.debug(chunk)
            if chunk.choices:
                if chunk.choices[0].delta.content is None:
                    break
                s += chunk.choices[0].delta.content
                if time.time() - start > 1.2:
                    start = time.time()
                    bot_reply_markdown(reply_id, who, s, bot, split_text=False)
        # maybe not complete
        try:
            bot_reply_markdown(reply_id, who, s, bot, split_text=True)
        except Exception:
            pass

        player_message.append(
            {
                "role": "assistant",
                "content": convert(s),
            }
        )

    except Exception:
        logger.exception("ChatGPT handler error")
        # bot.reply_to(message, "answer wrong maybe up to the max token")
        player_message.clear()
        return


def chatgpt_photo_handler(message: Message, bot: TeleBot) -> None:
    s = message.caption
    prompt = s.strip()
    who = "ChatGPT Vision"
    # show something, make it more responsible
    reply_id = bot_reply_first(message, who, bot)
    # get the high quaility picture.
    max_size_photo = max(message.photo, key=lambda p: p.file_size)
    file_path = bot.get_file(max_size_photo.file_id).file_path
    downloaded_file = bot.download_file(file_path)
    with open("chatgpt_temp.jpg", "wb") as temp_file:
        temp_file.write(downloaded_file)

    try:
        r = client.chat.completions.create(
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_to_data_uri("chatgpt_temp.jpg")},
                        },
                    ],
                }
            ],
            model=CHATGPT_PRO_MODEL,
            stream=True,
        )
        s = ""
        start = time.time()
        for chunk in r:
            if chunk.choices[0].delta.content is None:
                break
            s += chunk.choices[0].delta.content
            if time.time() - start > 2.0:
                start = time.time()
                bot_reply_markdown(reply_id, who, s, bot, split_text=False)
        # maybe not complete
        try:
            bot_reply_markdown(reply_id, who, s, bot)
        except Exception:
            pass

    except Exception:
        logger.exception("ChatGPT handler error")
        bot.reply_to(message, "answer wrong maybe up to the max token")


if settings.openai_api_key:

    def register(bot: TeleBot) -> None:
        bot.register_message_handler(chatgpt_handler, commands=["gpt"], pass_bot=True)
        bot.register_message_handler(chatgpt_handler, regexp="^gpt:", pass_bot=True)
        bot.register_message_handler(
            chatgpt_pro_handler, commands=["gpt_pro"], pass_bot=True
        )
        bot.register_message_handler(
            chatgpt_pro_handler, regexp="^gpt_pro:", pass_bot=True
        )
        bot.register_message_handler(
            chatgpt_photo_handler,
            content_types=["photo"],
            func=lambda m: m.caption
            and m.caption.startswith(("gpt:", "/gpt", "gpt_pro:", "/gpt_pro")),
            pass_bot=True,
        )
