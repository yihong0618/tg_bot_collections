# useful md for myself and you.

from telebot import TeleBot
from telebot.types import Message
from expiringdict import ExpiringDict
from os import environ
import time
import datetime
from concurrent.futures import ThreadPoolExecutor
import re

from . import *

from telegramify_markdown.customize import markdown_symbol

# If you want, Customizing the head level 1 symbol
markdown_symbol.head_level_1 = "📌"
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol
chat_message_dict = ExpiringDict(max_len=100, max_age_seconds=120)
chat_user_dict = ExpiringDict(max_len=100, max_age_seconds=20)

#### Telegra.ph init ####
# Will auto generate a token if not provided, restart will lose all TODO
TELEGRA_PH_TOKEN = environ.get("TELEGRA_PH_TOKEN")
# Edit "Store_Token = False" in "__init__.py" to True to store it
ph = TelegraphAPI(TELEGRA_PH_TOKEN)


#### Customization ####
Language = "zh-cn"  # "en" or "zh-cn".
SUMMARY = "gemini"  # "cohere" or "gemini" or None
General_clean = True  # Will Delete LLM message
Extra_clean = True  # Will Delete command message too

#### LLMs ####
GEMINI_USE = True
CHATGPT_USE = True
COHERE_USE = False  # Slow, but web search
QWEN_USE = True
CLADUE_USE = False  # Untested
LLAMA_USE = False  # prompted for Language

COHERE_USE_BACKGROUND = True  # Only display in telegra.ph
LLAMA_USE_BACKGROUND = True

#### LLMs init ####
#### OpenAI init ####
CHATGPT_API_KEY = environ.get("OPENAI_API_KEY")
CHATGPT_BASE_URL = environ.get("OPENAI_API_BASE") or "https://api.openai.com/v1"
if CHATGPT_USE and CHATGPT_API_KEY:
    from openai import OpenAI

    CHATGPT_PRO_MODEL = "gpt-4o-2024-05-13"
    client = OpenAI(api_key=CHATGPT_API_KEY, base_url=CHATGPT_BASE_URL, timeout=300)


#### Gemini init ####
GOOGLE_GEMINI_KEY = environ.get("GOOGLE_GEMINI_KEY")
if GEMINI_USE and GOOGLE_GEMINI_KEY:
    import google.generativeai as genai
    from google.generativeai import ChatSession
    from google.generativeai.types.generation_types import StopCandidateException

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
        model_name="gemini-1.5-pro-latest",
        generation_config=generation_config,
        safety_settings=safety_settings,
    )
    model_flash = genai.GenerativeModel(
        model_name="gemini-1.5-flash-latest",
        generation_config=generation_config,
        safety_settings=safety_settings,
        system_instruction=f"""
The user asked a question, and multiple AI have given answers to the same question.
Your task is to summarize the responses from them in a concise and clear manner.
The summary should:
In one to three short sentences, as less as possible.
Your must use language of {Language} to respond.
Start with "Summary:" or"总结:"
""",
    )
    convo = model.start_chat()
    convo_summary = model_flash.start_chat()


#### Cohere init ####
COHERE_API_KEY = environ.get("COHERE_API_KEY")

if (COHERE_USE or COHERE_USE_BACKGROUND) and COHERE_API_KEY:
    import cohere

    COHERE_MODEL = "command-r-plus"
    co = cohere.Client(api_key=COHERE_API_KEY)


#### Qwen init ####
QWEN_API_KEY = environ.get("TOGETHER_API_KEY")

if QWEN_USE and QWEN_API_KEY:
    from together import Together

    QWEN_MODEL = "Qwen/Qwen2-72B-Instruct"
    qwen_client = Together(api_key=QWEN_API_KEY)

#### Claude init ####
ANTHROPIC_API_KEY = environ.get("ANTHROPIC_API_KEY")
# use openai for claude
if CLADUE_USE and ANTHROPIC_API_KEY:
    ANTHROPIC_BASE_URL = environ.get("ANTHROPIC_BASE_URL")
    ANTHROPIC_MODEL = "claude-3-5-sonnet-20240620"
    claude_client = OpenAI(
        api_key=ANTHROPIC_API_KEY, base_url=ANTHROPIC_BASE_URL, timeout=20
    )

#### llama init ####
LLAMA_API_KEY = environ.get("GROQ_API_KEY")
if (LLAMA_USE or LLAMA_USE_BACKGROUND) and LLAMA_API_KEY:
    from groq import Groq

    llama_client = Groq(api_key=LLAMA_API_KEY)
    LLAMA_MODEL = "llama3-70b-8192"


#### init end ####


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
    if message.text and message.text.startswith("/"):
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


def answer_it_handler(message: Message, bot: TeleBot) -> None:
    """answer_it: /answer_it"""
    # answer the last message in the chat group
    who = "answer_it"
    # get the last message in the chat

    chat_id = message.chat.id
    latest_message = chat_message_dict.get(chat_id)
    m = latest_message.text.strip()
    m = enrich_text_with_urls(m)
    full_answer = f"Question:\n{m}\n" if len(m) < 300 else ""
    if Extra_clean:  # delete the command message
        bot.delete_message(chat_id, message.message_id)

    #### Answers Thread ####
    executor = ThreadPoolExecutor(max_workers=5)
    if GEMINI_USE and GOOGLE_GEMINI_KEY:
        gemini_future = executor.submit(gemini_answer, latest_message, bot, m)
    if CHATGPT_USE and CHATGPT_API_KEY:
        chatgpt_future = executor.submit(chatgpt_answer, latest_message, bot, m)
    if COHERE_USE and COHERE_API_KEY:
        cohere_future = executor.submit(cohere_answer, latest_message, bot, m)
    if QWEN_USE and QWEN_API_KEY:
        qwen_future = executor.submit(qwen_answer, latest_message, bot, m)
    if CLADUE_USE and ANTHROPIC_API_KEY:
        claude_future = executor.submit(claude_answer, latest_message, bot, m)
    if LLAMA_USE and LLAMA_API_KEY:
        llama_future = executor.submit(llama_answer, latest_message, bot, m)

    #### Answers List ####
    full_chat_id_list = []
    if GEMINI_USE and GOOGLE_GEMINI_KEY:
        answer_gemini, gemini_chat_id = gemini_future.result()
        full_chat_id_list.append(gemini_chat_id)
        full_answer += answer_gemini
    if CHATGPT_USE and CHATGPT_API_KEY:
        anaswer_chatgpt, chatgpt_chat_id = chatgpt_future.result()
        full_chat_id_list.append(chatgpt_chat_id)
        full_answer += anaswer_chatgpt
    if COHERE_USE and COHERE_API_KEY:
        answer_cohere, cohere_chat_id = cohere_future.result()
        full_chat_id_list.append(cohere_chat_id)
        full_answer += answer_cohere
    if QWEN_USE and QWEN_API_KEY:
        answer_qwen, qwen_chat_id = qwen_future.result()
        full_chat_id_list.append(qwen_chat_id)
        full_answer += answer_qwen
    if CLADUE_USE and ANTHROPIC_API_KEY:
        answer_claude, claude_chat_id = claude_future.result()
        full_chat_id_list.append(claude_chat_id)
        full_answer += answer_claude
    if LLAMA_USE and LLAMA_API_KEY:
        answer_llama, llama_chat_id = llama_future.result()
        full_chat_id_list.append(llama_chat_id)
        full_answer += answer_llama

    print(full_chat_id_list)

    if len(m) > 300:
        full_answer += llm_answer("Question", m)

    ##### Telegraph #####
    final_answer(latest_message, bot, full_answer, full_chat_id_list)


def update_time():
    """Return the current time in UTC+8. Good for testing completion of content."""
    return f"\nLast Update{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} at UTC+8\n"


def llm_answer(who: str, s: str) -> str:
    """Universal llm answer format for telegra.ph. Use title so 'link#title' can be used."""
    return f"\n\n---\n## {who}\n{s}"


def llm_background(path: str, full_answer: str, m: str) -> str:
    """Update the telegra.ph page with background answer result. Return new full answer."""
    ph_path = re.search(r"https?://telegra\.ph/(.+)", path).group(1)
    full_answer += m + update_time()
    try:
        ph.edit_page_md(path=ph_path, title="Answer it", markdown_text=full_answer)
    except Exception as e:
        print(f"\n------\nllm_background Error:\n{e}\n------\n")
    return full_answer


def gemini_answer(latest_message: Message, bot: TeleBot, m):
    """gemini answer"""
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
        print(f"\n------\n{who} function inner Error:\n{e}\n------\n")
        convo.history.clear()
        bot_reply_markdown(reply_id, who, "Error", bot)
        return f"\n---\n{who}:\nAnswer wrong", reply_id.message_id

    return llm_answer(who, s), reply_id.message_id


def chatgpt_answer(latest_message: Message, bot: TeleBot, m):
    """chatgpt answer"""
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
        print(f"\n------\n{who} function inner Error:\n{e}\n------\n")
        bot_reply_markdown(reply_id, who, "answer wrong", bot)
        return f"\n---\n{who}:\nAnswer wrong", reply_id.message_id

    return llm_answer(who, s), reply_id.message_id


def claude_answer(latest_message: Message, bot: TeleBot, m):
    """claude answer"""
    who = "Claude Pro"
    reply_id = bot_reply_first(latest_message, who, bot)

    try:
        r = claude_client.chat.completions.create(
            messages=[{"role": "user", "content": m}],
            max_tokens=4096,
            model=ANTHROPIC_MODEL,
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
        print(f"\n------\n{who} function inner Error:\n{e}\n------\n")
        bot_reply_markdown(reply_id, who, "answer wrong", bot)
        return f"\n---\n{who}:\nAnswer wrong", reply_id.message_id

    answer = f"\n---\n{who}:\n{s}"
    return llm_answer(who, s), reply_id.message_id


def cohere_answer(latest_message: Message, bot: TeleBot, m):
    """cohere answer"""
    who = "Command R Plus"
    reply_id = bot_reply_first(latest_message, who, bot)

    try:
        current_time = datetime.datetime.now(datetime.timezone.utc)
        preamble = (
            f"You are Command R Plus, a large language model trained to have polite, helpful, inclusive conversations with people. People are looking for information that may need you to search online. Make an accurate and fast response. If there are no search results, then provide responses based on your general knowledge(It's fine if it's not accurate, it might still inspire the user."
            f"The current UTC time is {current_time.strftime('%Y-%m-%d %H:%M:%S')}, "
            f"UTC-4 (e.g. New York) is {current_time.astimezone(datetime.timezone(datetime.timedelta(hours=-4))).strftime('%Y-%m-%d %H:%M:%S')}, "
            f"UTC-7 (e.g. Los Angeles) is {current_time.astimezone(datetime.timezone(datetime.timedelta(hours=-7))).strftime('%Y-%m-%d %H:%M:%S')}, "
            f"and UTC+8 (e.g. Beijing) is {current_time.astimezone(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')}."
        )

        stream = co.chat_stream(
            model=COHERE_MODEL,
            message=m,
            temperature=0.8,
            chat_history=[],  # One time, so no need for chat history
            prompt_truncation="AUTO",
            connectors=[{"id": "web-search"}],
            citation_quality="accurate",
            preamble=preamble,
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
                s += event.text.encode("utf-8").decode("utf-8", "ignore")
                if time.time() - start > 0.8:
                    start = time.time()
                    bot_reply_markdown(
                        reply_id,
                        who,
                        f"\nStill thinking{len(s)}...\n{s}",
                        bot,
                        split_text=True,
                    )
            elif event.event_type == "stream-end":
                break
        content = (
            s
            + "\n---\n---\n"
            + source
            + f"\nLast Update{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} at UTC+8\n"
        )
        # maybe not complete
        try:
            bot_reply_markdown(reply_id, who, s, bot, split_text=True)
        except:
            pass
    except Exception as e:
        print(f"\n------\n{who} function inner Error:\n{e}\n------\n")
        bot_reply_markdown(reply_id, who, "Answer wrong", bot)
        return f"\n---\n{who}:\nAnswer wrong", reply_id.message_id

    return llm_answer(who, content), reply_id.message_id


def qwen_answer(latest_message: Message, bot: TeleBot, m):
    """qwen answer"""
    who = "qwen Pro"
    reply_id = bot_reply_first(latest_message, who, bot)
    try:
        r = qwen_client.chat.completions.create(
            messages=[{"role": "user", "content": m}],
            max_tokens=8192,
            model=QWEN_MODEL,
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
        print(f"\n------\n{who} function inner Error:\n{e}\n------\n")
        bot_reply_markdown(reply_id, who, "answer wrong", bot)
        return f"\n---\n{who}:\nAnswer wrong", reply_id.message_id

    return llm_answer(who, s), reply_id.message_id


def llama_answer(latest_message: Message, bot: TeleBot, m):
    """llama answer"""
    who = "llama"
    reply_id = bot_reply_first(latest_message, who, bot)
    try:
        r = llama_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": f"You must use language of {Language} to respond.",
                },
                {"role": "user", "content": m},
            ],
            max_tokens=8192,
            model=LLAMA_MODEL,
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
        print(f"\n------\n{who} function inner Error:\n{e}\n------\n")
        bot_reply_markdown(reply_id, who, "answer wrong", bot)
        return f"\n---\n{who}:\nAnswer wrong", reply_id.message_id

    return llm_answer(who, s), reply_id.message_id


# TODO: Perplexity looks good. `pplx_answer`


def final_answer(latest_message: Message, bot: TeleBot, full_answer: str, answers_list):
    """final answer"""
    who = "Answer it"
    reply_id = bot_reply_first(latest_message, who, bot)

    # If disappeared means the answer is not complete in telegra.ph
    full_answer += update_time()

    # greate new telegra.ph page
    ph_s = ph.create_page_md(title="Answer it", markdown_text=full_answer)
    bot_reply_markdown(reply_id, who, f"**[Full Answer]({ph_s})**", bot)

    # delete the chat message, only leave a telegra.ph link
    if General_clean:
        for i in answers_list:
            bot.delete_message(latest_message.chat.id, i)

    #### Summary ####
    if SUMMARY == None:
        pass
    elif COHERE_USE and COHERE_API_KEY and SUMMARY == "cohere":
        summary_cohere(bot, full_answer, ph_s, reply_id)
    elif GEMINI_USE and GOOGLE_GEMINI_KEY and SUMMARY == "gemini":
        summary_gemini(bot, full_answer, ph_s, reply_id)
    else:
        pass

    #### Background LLM ####
    # Run background llm, no show to telegram, just update the page, Good for slow llm
    if LLAMA_USE_BACKGROUND and LLAMA_API_KEY:
        llama_b_m = background_llama(latest_message.text)
        print(llama_b_m)
        full_answer = llm_background(ph_s, full_answer, llama_b_m)
    if COHERE_USE_BACKGROUND and COHERE_API_KEY:
        cohere_b_m = background_cohere(latest_message.text)
        print(cohere_b_m)
        full_answer = llm_background(ph_s, full_answer, cohere_b_m)


def background_cohere(m: str) -> str:
    """we run cohere get the full answer in background"""
    who = "Command R Plus"
    try:
        stream = co.chat_stream(
            model=COHERE_MODEL,
            message=m,
            temperature=0.8,
            chat_history=[],  # One time, so no need for chat history
            prompt_truncation="AUTO",
            connectors=[{"id": "web-search"}],
            citation_quality="accurate",
            preamble="",
        )
        s = ""
        source = ""
        for event in stream:
            if event.event_type == "search-results":
                for doc in event.documents:
                    source += f"\n{doc['title']}\n{doc['url']}\n"
            elif event.event_type == "text-generation":
                s += event.text.encode("utf-8").decode("utf-8", "ignore")
            elif event.event_type == "stream-end":
                break
        content = llm_answer(who, f"{s}\n\n---\n{source}")

    except Exception as e:
        print(f"\n------\nbackground_cohere Error:\n{e}\n------\n")
        content = llm_answer(who, "Background Answer wrong")
    return content


def background_llama(m: str) -> str:
    """we run llama get the full answer in background"""
    who = "llama"
    try:
        r = llama_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": f"You must use language of {Language} to respond.",
                },
                {"role": "user", "content": m},
            ],
            max_tokens=8192,
            model=LLAMA_MODEL,
            stream=True,
        )
        s = ""
        for chunk in r:
            if chunk.choices[0].delta.content is None:
                break
            s += chunk.choices[0].delta.content

    except Exception as e:
        print(f"\n------\nbackground_llama Error:\n{e}\n------\n")
        s = "Background Answer wrong"
    return llm_answer(who, s)


def summary_cohere(bot: TeleBot, full_answer: str, ph_s: str, reply_id: int) -> None:
    """Receive the full text, and the final_answer's chat_id, update with a summary."""
    who = "Answer it"

    # inherit
    if Language == "zh-cn":
        s = f"**[全文]({ph_s})** | "
    elif Language == "en":
        s = f"**[Full Answer]({ph_s})** | "

    # filter
    length = len(full_answer)  # max 128,000 tokens...
    if length > 50000:
        full_answer = full_answer[:50000]

    try:
        preamble = """
        You are Command R Plus, a large language model trained to have polite, helpful, inclusive conversations with people. The user asked a question, and multiple AI have given answers to the same question, but they have different styles, and rarely they have opposite opinions or other issues, but that is normal. Your task is to summarize the responses from them in a concise and clear manner. The summary should:

Be written in bullet points.
Contain between two to ten sentences.
Highlight key points and main conclusions.
Note any significant differences in responses.
Provide a brief indication if users should refer to the full responses for more details.
For the first LLM's content, if it is mostly in any language other than English, respond in that language for all your output.
Start with "Summary:" or "总结:"
"""
        stream = co.chat_stream(
            model=COHERE_MODEL,
            message=full_answer,
            temperature=0.4,
            chat_history=[],
            prompt_truncation="OFF",
            connectors=[],
            preamble=preamble,
        )

        start = time.time()
        for event in stream:
            if event.event_type == "stream-start":
                bot_reply_markdown(reply_id, who, f"{s}Summarizing...", bot)
            elif event.event_type == "text-generation":
                s += event.text.encode("utf-8").decode("utf-8", "ignore")
                if time.time() - start > 0.4:
                    start = time.time()
                    bot_reply_markdown(reply_id, who, s, bot)
            elif event.event_type == "stream-end":
                break

        try:
            bot_reply_markdown(reply_id, who, s, bot)
        except:
            pass

    except Exception as e:
        if Language == "zh-cn":
            bot_reply_markdown(reply_id, who, f"[全文]({ph_s})", bot)
        elif Language == "en":
            bot_reply_markdown(reply_id, who, f"[Full Answer]({ph_s})", bot)
        print(f"\n------\nsummary_cohere function inner Error:\n{e}\n------\n")


def summary_gemini(bot: TeleBot, full_answer: str, ph_s: str, reply_id: int) -> None:
    """Receive the full text, and the final_answer's chat_id, update with a summary."""
    who = "Answer it"

    # inherit
    if Language == "zh-cn":
        s = f"**[全文]({ph_s})** | "
    elif Language == "en":
        s = f"**[Full Answer]({ph_s})** | "

    try:
        r = convo_summary.send_message(full_answer, stream=True)
        start = time.time()
        for e in r:
            s += e.text
            if time.time() - start > 0.4:
                start = time.time()
                bot_reply_markdown(reply_id, who, s, bot, split_text=False)
        bot_reply_markdown(reply_id, who, s, bot)
        convo_summary.history.clear()
    except Exception as e:
        if Language == "zh-cn":
            bot_reply_markdown(reply_id, who, f"[全文]({ph_s})", bot)
        elif Language == "en":
            bot_reply_markdown(reply_id, who, f"[Full Answer]({ph_s})", bot)
        print(f"\n------\nsummary_gemini function inner Error:\n{e}\n------\n")
        bot_reply_markdown(reply_id, who, f"{s}Error", bot)


if GOOGLE_GEMINI_KEY and CHATGPT_API_KEY:

    def register(bot: TeleBot) -> None:
        bot.register_message_handler(md_handler, commands=["md"], pass_bot=True)
        bot.register_message_handler(
            answer_it_handler, commands=["answer_it"], pass_bot=True
        )
        bot.register_message_handler(md_handler, regexp="^md:", pass_bot=True)
        bot.register_message_handler(latest_handle_messages, pass_bot=True)
