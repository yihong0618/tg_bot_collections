# useful md for myself and you.

from telebot import TeleBot
from telebot.types import Message
from expiringdict import ExpiringDict
from os import environ
import time
import datetime

from openai import OpenAI
import google.generativeai as genai
from google.generativeai import ChatSession
from google.generativeai.types.generation_types import StopCandidateException
from telebot import TeleBot
from together import Together
from telebot.types import Message

from . import *

from telegramify_markdown.customize import markdown_symbol

#### Cohere init ####
import cohere

COHERE_API_KEY = environ.get("COHERE_API_KEY")
COHERE_MODEL = "command-r-plus"
# if you want to use cohere for answer it, set it to True
USE_CHHERE = False
if COHERE_API_KEY:
    co = cohere.Client(api_key=COHERE_API_KEY)

#### Telegraph init ####
TELEGRA_PH_TOKEN = environ.get("TELEGRA_PH_TOKEN")
ph = TelegraphAPI(TELEGRA_PH_TOKEN)
#### Telegraph done ####

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
            "cohere",
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
    full = ""
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

    full += f"{who}:\n{s}"
    chat_id_list = [reply_id.message_id]
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
            if time.time() - start > 1.5:
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

    full += f"\n---\n{who}:\n{s}"
    chat_id_list.append(reply_id.message_id)

    ##### Cohere #####
    if USE_CHHERE and COHERE_API_KEY:
        full, chat_id = cohere_answer(latest_message, bot, full, m)
        chat_id_list.append(chat_id)
    else:
        pass

    ##### Telegraph #####
    final_answer(latest_message, bot, full, chat_id_list)


def cohere_answer(latest_message: Message, bot: TeleBot, full, m):
    """cohere answer"""
    who = "Command R Plus"
    reply_id = bot_reply_first(latest_message, who, bot)

    player_message = [{"role": "User", "message": m}]

    try:
        stream = co.chat_stream(
            model=COHERE_MODEL,
            message=m,
            temperature=0.3,
            chat_history=player_message,
            prompt_truncation="AUTO",
            connectors=[{"id": "web-search"}],
            citation_quality="accurate",
            preamble=f"You are Command R+, a large language model trained to have polite, helpful, inclusive conversations with people. The current time in Tornoto is {datetime.datetime.now(datetime.timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S')}, in Los Angeles is {datetime.datetime.now(datetime.timezone.utc).astimezone().astimezone(datetime.timezone(datetime.timedelta(hours=-7))).strftime('%Y-%m-%d %H:%M:%S')}, and in China is {datetime.datetime.now(datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')}.",
        )

        s = ""
        source = ""
        start = time.time()
        for event in stream:
            if event.event_type == "stream-start":
                bot_reply_markdown(reply_id, who, "Thinking...", bot)
            elif event.event_type == "search-queries-generation":
                bot_reply_markdown(reply_id, who, "Searching online...", bot)
            elif event.event_type == "search-results":
                bot_reply_markdown(reply_id, who, "Reading...", bot)
                for doc in event.documents:
                    source += f"\n{doc['title']}\n{doc['url']}\n"
            elif event.event_type == "text-generation":
                s += event.text.encode("utf-8").decode("utf-8")
                if time.time() - start > 0.4:
                    start = time.time()
                    bot_reply_markdown(
                        reply_id,
                        who,
                        f"\nStill thinking{len(s)}...",
                        bot,
                        split_text=True,
                    )
            elif event.event_type == "stream-end":
                break
        content = (
            s
            + "\n------\n------\n"
            + source
            + f"\n------\n------\nLast Update{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        try:
            bot_reply_markdown(reply_id, who, s, bot, split_text=True)
        except:
            pass
    except Exception as e:
        print(e)
        bot_reply_markdown(reply_id, who, "Answer wrong", bot)
        player_message.clear()
        return full, reply_id.message_id
    full += f"\n---\n{who}:\n{content}"
    return full, reply_id.message_id


def final_answer(latest_message: Message, bot: TeleBot, full, answers_list):
    """final answer"""
    who = "Answer"
    reply_id = bot_reply_first(latest_message, who, bot)
    ph_s = ph.create_page_md(title="Answer it", markdown_text=full)
    bot_reply_markdown(reply_id, who, f"[View]({ph_s})", bot)
    # delete the chat message, only leave a telegra.ph link
    for i in answers_list:
        bot.delete_message(latest_message.chat.id, i)


if GOOGLE_GEMINI_KEY and CHATGPT_API_KEY:

    def register(bot: TeleBot) -> None:
        bot.register_message_handler(md_handler, commands=["md"], pass_bot=True)
        bot.register_message_handler(
            answer_it_handler, commands=["answer_it"], pass_bot=True
        )
        bot.register_message_handler(md_handler, regexp="^md:", pass_bot=True)
        bot.register_message_handler(latest_handle_messages, pass_bot=True)
