from os import environ
import re
import time

import google.generativeai as genai
from google.generativeai import ChatSession
from google.generativeai.types.generation_types import StopCandidateException
from telebot import TeleBot
from telebot.types import Message
from expiringdict import ExpiringDict

from telegramify_markdown.customize import markdown_symbol

from . import *

markdown_symbol.head_level_1 = "📌"  # If you want, Customizing the head level 1 symbol
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol

GOOGLE_GEMINI_KEY = environ.get("GOOGLE_GEMINI_KEY")

genai.configure(api_key=GOOGLE_GEMINI_KEY)
generation_config = {
    "temperature": 0.7,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 8192,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

# Global history cache
gemini_player_dict = ExpiringDict(max_len=1000, max_age_seconds=300)
gemini_pro_player_dict = ExpiringDict(max_len=1000, max_age_seconds=300)
gemini_file_player_dict = ExpiringDict(max_len=100, max_age_seconds=300)


def make_new_gemini_convo(is_pro=False) -> ChatSession:
    model_name = "gemini-1.5-flash-latest"
    if is_pro:
        model_name = "models/gemini-1.5-pro-latest"

    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config=generation_config,
        safety_settings=safety_settings,
    )
    convo = model.start_chat()
    return convo


def remove_gemini_player(player_id: str, is_pro: bool) -> None:
    if is_pro:
        if player_id in gemini_pro_player_dict:
            del gemini_pro_player_dict[player_id]
        if player_id in gemini_file_player_dict:
            del gemini_file_player_dict[player_id]
    else:
        if player_id in gemini_player_dict:
            del gemini_player_dict[player_id]


def get_gemini_player(player_id: str, is_pro: bool) -> ChatSession:
    player = None
    if is_pro:
        if player_id not in gemini_pro_player_dict:
            gemini_pro_player_dict[player_id] = make_new_gemini_convo(is_pro)
        player = gemini_pro_player_dict[player_id]
    else:
        if player_id not in gemini_player_dict:
            gemini_player_dict[player_id] = make_new_gemini_convo()
        player = gemini_player_dict[player_id]

    return player


def gemini_handler(message: Message, bot: TeleBot) -> None:
    """Gemini : /gemini <question>"""
    m = message.text.strip()
    player_id = str(message.from_user.id)
    is_pro = False
    if m.strip() == "clear":
        bot.reply_to(message, "just clear you gemini messages history")
        remove_gemini_player(player_id, is_pro)
        return
    if m[:4].lower() == "new ":
        m = m[4:].strip()
        remove_gemini_player(player_id, is_pro)

    # restart will lose all TODO
    player = get_gemini_player(player_id, is_pro)
    m = enrich_text_with_urls(m)

    who = "Gemini"
    # show something, make it more responsible
    reply_id = bot_reply_first(message, who, bot)

    # keep the last 5, every has two ask and answer.
    if len(player.history) > 10:
        player.history = player.history[2:]

    try:
        player.send_message(m)
        gemini_reply_text = player.last.text.strip()
        # Gemini is often using ':' in **Title** which not work in Telegram Markdown
        gemini_reply_text = gemini_reply_text.replace(":**", "\:**")
        gemini_reply_text = gemini_reply_text.replace("：**", "**\: ")
    except StopCandidateException as e:
        match = re.search(r'content\s*{\s*parts\s*{\s*text:\s*"([^"]+)"', str(e))
        if match:
            gemini_reply_text = match.group(1)
            gemini_reply_text = re.sub(r"\\n", "\n", gemini_reply_text)
        else:
            print("No meaningful text was extracted from the exception.")
            bot_reply_markdown(reply_id, who, "answer wrong", bot)
            return

    # By default markdown
    bot_reply_markdown(reply_id, who, gemini_reply_text, bot)


def gemini_pro_handler(message: Message, bot: TeleBot) -> None:
    """Gemini : /gemini_pro <question>"""
    m = message.text.strip()
    player_id = str(message.from_user.id)
    is_pro = True
    if m.strip() == "clear":
        bot.reply_to(message, "just clear you gemini messages history")
        remove_gemini_player(player_id, is_pro)
        return
    if m[:4].lower() == "new ":
        m = m[4:].strip()
        remove_gemini_player(player_id, is_pro)

    # restart will lose all TODO
    player = get_gemini_player(player_id, is_pro)
    m = enrich_text_with_urls(m)

    who = "Gemini Pro"
    # show something, make it more responsible
    reply_id = bot_reply_first(message, who, bot)

    # keep the last 5, every has two ask and answer.
    if len(player.history) > 10:
        player.history = player.history[2:]

    try:
        if path := gemini_file_player_dict.get(player_id):
            m = [m, path]
        r = player.send_message(m, stream=True)
        s = ""
        start = time.time()
        for e in r:
            s += e.text
            if time.time() - start > 1.7:
                start = time.time()
                bot_reply_markdown(reply_id, who, s, bot, split_text=False)

        if not bot_reply_markdown(reply_id, who, s, bot):
            # maybe not complete
            # maybe the same message
            player.history.clear()
            return
    except Exception as e:
        print(e)
        bot_reply_markdown(reply_id, who, "answer wrong", bot)
        player.history.clear()
        return


def gemini_photo_handler(message: Message, bot: TeleBot) -> None:
    s = message.caption
    prompt = s.strip()
    who = "Gemini Vision"
    # show something, make it more responsible
    reply_id = bot_reply_first(message, who, bot)
    # get the high quaility picture.
    max_size_photo = max(message.photo, key=lambda p: p.file_size)
    file_path = bot.get_file(max_size_photo.file_id).file_path
    downloaded_file = bot.download_file(file_path)
    with open("gemini_temp.jpg", "wb") as temp_file:
        temp_file.write(downloaded_file)

    model = genai.GenerativeModel("gemini-pro-vision")
    with open("gemini_temp.jpg", "rb") as image_file:
        image_data = image_file.read()
    contents = {
        "parts": [{"mime_type": "image/jpeg", "data": image_data}, {"text": prompt}]
    }
    try:
        r = model.generate_content(contents=contents, stream=True)
        s = ""
        start = time.time()
        for e in r:
            s += e.text
            if time.time() - start > 1.7:
                start = time.time()
                bot_reply_markdown(reply_id, who, s, bot, split_text=False)

        bot_reply_markdown(reply_id, who, s, bot)
    except Exception as e:
        print(e)
        bot_reply_markdown(reply_id, who, "answer wrong", bot)


def gemini_audio_handler(message: Message, bot: TeleBot) -> None:
    s = message.caption
    prompt = s.strip()
    who = "Gemini File Audio"
    player_id = str(message.from_user.id)
    # restart will lose all TODO
    player = get_gemini_player(player_id, is_pro=True)
    file_path = None
    # for file handler like {user_id: [player, file_path], user_id2: [player, file_path]}
    reply_id = bot_reply_first(message, who, bot)
    file_path = bot.get_file(message.audio.file_id).file_path
    downloaded_file = bot.download_file(file_path)
    path = f"{player_id}_gemini.mp3"
    with open(path, "wb") as temp_file:
        temp_file.write(downloaded_file)
    gemini_mp3_file = genai.upload_file(path=path)
    r = player.send_message([prompt, gemini_mp3_file], stream=True)
    # need set it for the conversation
    gemini_file_player_dict[player_id] = gemini_mp3_file
    try:
        s = ""
        start = time.time()
        for e in r:
            s += e.text
            if time.time() - start > 1.7:
                start = time.time()
                bot_reply_markdown(reply_id, who, s, bot, split_text=False)

        if not bot_reply_markdown(reply_id, who, s, bot):
            # maybe not complete
            # maybe the same message
            player.history.clear()
            return
    except Exception as e:
        print(e)
        bot_reply_markdown(reply_id, who, "answer wrong", bot)
        player.history.clear()
        return


if GOOGLE_GEMINI_KEY:

    def register(bot: TeleBot) -> None:
        bot.register_message_handler(gemini_handler, commands=["gemini"], pass_bot=True)
        bot.register_message_handler(gemini_handler, regexp="^gemini:", pass_bot=True)
        bot.register_message_handler(
            gemini_pro_handler, commands=["gemini_pro"], pass_bot=True
        )
        bot.register_message_handler(
            gemini_pro_handler, regexp="^gemini_pro:", pass_bot=True
        )
        bot.register_message_handler(
            gemini_photo_handler,
            content_types=["photo"],
            func=lambda m: m.caption and m.caption.startswith(("gemini:", "/gemini")),
            pass_bot=True,
        )
        bot.register_message_handler(
            gemini_audio_handler,
            content_types=["audio"],
            func=lambda m: m.caption and m.caption.startswith(("gemini:", "/gemini")),
            pass_bot=True,
        )
