# useful md for myself and you.

from telebot import TeleBot
from telebot.types import Message
from expiringdict import ExpiringDict
from os import environ
import time

from openai import OpenAI
import google.generativeai as genai
from google.generativeai import ChatSession
from google.generativeai.types.generation_types import StopCandidateException
from telebot import TeleBot
from together import Together
from telebot.types import Message

from . import *

from telegramify_markdown.customize import markdown_symbol

chat_message_dict = ExpiringDict(max_len=100, max_age_seconds=120)
chat_user_dict = ExpiringDict(max_len=100, max_age_seconds=20)

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

model = genai.GenerativeModel(
    model_name="models/gemini-1.5-pro-latest",
    generation_config=generation_config,
    safety_settings=safety_settings,
)
convo = model.start_chat()

#### ChatGPT init ####
CHATGPT_API_KEY = environ.get("OPENAI_API_KEY")
CHATGPT_BASE_URL = environ.get("OPENAI_API_BASE") or "https://api.openai.com/v1"
QWEN_API_KEY = environ.get("TOGETHER_API_KEY")
QWEN_MODEL = "Qwen/Qwen2-72B-Instruct"
CHATGPT_PRO_MODEL = "gpt-4o-2024-05-13"


client = OpenAI(api_key=CHATGPT_API_KEY, base_url=CHATGPT_BASE_URL, timeout=300)
qwen_client = Together(api_key=QWEN_API_KEY, timeout=300)


def md_handler(message: Message, bot: TeleBot):
    """pretty md: /md <address>"""
    who = ""
    reply_id = bot_reply_first(message, who, bot)
    bot_reply_markdown(reply_id, who, message.text.strip(), bot)


def latest_handle_messages(message: Message, bot: TeleBot):
    """ignore"""
    chat_id = message.chat.id
    chat_user_id = message.from_user.id
    # if is bot command, ignore
    if message.text.startswith("/"):
        return
    # start command ignore
    elif message.text.startswith(
        (
            "md",
            "chatgpt",
            "gemini",
            "qwen",
            "map",
            "github",
            "claude",
            "llama",
            "dify",
            "tts",
            "sd",
            "map",
            "yi",
        )
    ):
        return
    # answer_it command ignore
    elif message.text.startswith("answer_it"):
        return
    # if not text, ignore
    elif not message.text:
        return
    else:
        if chat_user_dict.get(chat_user_id):
            message.text += chat_message_dict[chat_id].text
            chat_message_dict[chat_id] = message
        else:
            chat_message_dict[chat_id] = message
        chat_user_dict[chat_user_id] = True
        print(chat_message_dict[chat_id].text)


def answer_it_handler(message: Message, bot: TeleBot):
    """answer_it: /answer_it"""
    # answer the last message in the chat group
    who = "answer_it"
    # get the last message in the chat

    chat_id = message.chat.id
    latest_message = chat_message_dict.get(chat_id)
    m = latest_message.text.strip()
    m = enrich_text_with_urls(m)
    ##### Gemini #####
    who = "Gemini Pro"
    # show something, make it more responsible
    reply_id = bot_reply_first(latest_message, who, bot)

    try:
        r = convo.send_message(m, stream=True)
        s = ""
        start = time.time()
        for e in r:
            s += e.text
            if time.time() - start > 1.7:
                start = time.time()
                bot_reply_markdown(reply_id, who, s, bot, split_text=False)
        bot_reply_markdown(reply_id, who, s, bot)
        convo.history.clear()
    except Exception as e:
        print(e)
        convo.history.clear()
        bot_reply_markdown(reply_id, who, "Error", bot)

    ##### ChatGPT #####
    who = "ChatGPT Pro"
    reply_id = bot_reply_first(latest_message, who, bot)

    player_message = [{"role": "user", "content": m}]

    try:
        r = client.chat.completions.create(
            messages=player_message,
            max_tokens=4096,
            model=CHATGPT_PRO_MODEL,
            stream=True,
        )
        s = ""
        start = time.time()
        for chunk in r:
            if chunk.choices[0].delta.content is None:
                break
            s += chunk.choices[0].delta.content
            if time.time() - start > 1.2:
                start = time.time()
                bot_reply_markdown(reply_id, who, s, bot, split_text=False)
        # maybe not complete
        try:
            bot_reply_markdown(reply_id, who, s, bot)
        except:
            pass

    except Exception as e:
        print(e)
        bot_reply_markdown(reply_id, who, "answer wrong", bot)

    ##### Qwen #####
    who = "Qwen Pro"
    reply_id = bot_reply_first(latest_message, who, bot)

    player_message = [{"role": "user", "content": m}]

    try:
        r = qwen_client.chat.completions.create(
            messages=player_message,
            max_tokens=4096,
            model=QWEN_MODEL,
            stream=True,
        )
        s = ""
        start = time.time()
        for chunk in r:
            if chunk.choices[0].delta.content is None:
                break
            s += chunk.choices[0].delta.content
            if time.time() - start > 1.2:
                start = time.time()
                bot_reply_markdown(reply_id, who, s, bot, split_text=False)
        # maybe not complete
        try:
            bot_reply_markdown(reply_id, who, s, bot)
        except:
            pass

    except Exception as e:
        print(e)
        bot_reply_markdown(reply_id, who, "answer wrong", bot)


if GOOGLE_GEMINI_KEY and CHATGPT_API_KEY and QWEN_API_KEY:

    def register(bot: TeleBot) -> None:
        bot.register_message_handler(md_handler, commands=["md"], pass_bot=True)
        bot.register_message_handler(
            answer_it_handler, commands=["answer_it"], pass_bot=True
        )
        bot.register_message_handler(md_handler, regexp="^md:", pass_bot=True)
        bot.register_message_handler(latest_handle_messages, pass_bot=True)
