# useful md for myself and you.

from telebot import TeleBot
from telebot.types import Message
from expiringdict import ExpiringDict
from os import environ
import time
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import re

from . import *

from telegramify_markdown.customize import markdown_symbol

# Define the load priority, lower numbers have higher priority
load_priority = 1000

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

#####################################################################
#### Customization ##################################################
Language = "zh-cn"  # "en" or "zh-cn".
SUMMARY = None  # "cohere" or "gemini" or None
General_clean = True  # Will Delete LLM message
Extra_clean = True  # Will Delete command message too
Link_Clean = False  # True will disable Instant View / Web Preview
Stream_Thread = 2  # How many stream LLM will stream at the same time
Complete_Thread = 3  # How many non-stream LLM will run at the same time
Stream_Timeout = (
    240  # If not complete in 4 mins, will stop wait or raise Exception timeout
)
MESSAGE_MAX_LENGTH = 4096  # Message after url enrich may too long
Hint = (
    "\n(Need answer? Type or tap /answer_it after a message)"
    if Language == "en"
    else "\n(需要回答? 在一条消息之后, 输入或点击 /answer_it )"
)
#### LLMs ####
GEMINI_USE = True

CHATGPT_USE = True
CLADUE_USE = True
QWEN_USE = False
COHERE_USE = False  # Slow, but web search
LLAMA_USE = False  # prompted for Language

CHATGPT_COMPLETE = False  # sync mode
CLADUE_COMPLETE = False  # Only display in telegra.ph
COHERE_COMPLETE = False
LLAMA_COMPLETE = False

GEMINI_USE_THREAD = False  # Maybe not work

CHATGPT_APPEND = True  # Update later to ph
CLADUE_APPEND = True
COHERE_APPEND = True
LLAMA_APPEND = True
QWEN_APPEND = True

#### Customization End ##############################################
#####################################################################

#### LLMs init ####
#### OpenAI init ####
CHATGPT_API_KEY = environ.get("OPENAI_API_KEY")
CHATGPT_BASE_URL = environ.get("OPENAI_API_BASE") or "https://api.openai.com/v1"
if (CHATGPT_USE or CHATGPT_COMPLETE or CHATGPT_APPEND) and CHATGPT_API_KEY:
    from openai import OpenAI

    CHATGPT_PRO_MODEL = "gpt-4o-2024-05-13"
    client = OpenAI(api_key=CHATGPT_API_KEY, base_url=CHATGPT_BASE_URL, timeout=300)


#### Gemini init ####
GOOGLE_GEMINI_KEY = environ.get("GOOGLE_GEMINI_KEY")
if (GEMINI_USE or GEMINI_USE_THREAD) and GOOGLE_GEMINI_KEY:
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
        model_name="gemini-1.5-flash-latest",
        generation_config=generation_config,
        safety_settings=safety_settings,
        system_instruction=f"""
You are an AI assistant added to a group chat to provide help or answer questions. You only have access to the most recent message in the chat, which will be the next message you receive after this system prompt. Your task is to provide a helpful and relevant response based on this information.

Please adhere to these guidelines when formulating your response:

1. Address the content of the message directly and proactively.
2. If the message is a question or request, provide a comprehensive answer or assistance to the best of your ability.
3. Use your general knowledge and capabilities to fill in gaps where context might be missing.
4. Keep your response concise yet informative, appropriate for a group chat setting.
5. Maintain a friendly, helpful, and confident tone throughout.
6. If the message is unclear:
   - Make reasonable assumptions to provide a useful response.
   - If necessary, offer multiple interpretations or answers to cover possible scenarios.
7. Aim to make your response as complete and helpful as possible, even with limited context.
8. You must respond in {Language}.
9. Limit your response to approximately 500 characters in the target language.

Your response should be natural and fitting for a group chat context. While you only have access to this single message, use your broad knowledge base to provide informative and helpful answers. Be confident in your responses, but if you're making assumptions, briefly acknowledge this fact.

Remember, the group administrator has approved your participation and will review responses as needed, so focus on being as helpful as possible rather than being overly cautious.
""",
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

if (COHERE_USE or COHERE_COMPLETE or COHERE_APPEND) and COHERE_API_KEY:
    import cohere

    COHERE_MODEL = "command-r-plus"
    co = cohere.Client(api_key=COHERE_API_KEY)


#### Qwen init ####
QWEN_API_KEY = environ.get("TOGETHER_API_KEY")

if (QWEN_USE or QWEN_APPEND) and QWEN_API_KEY:
    from together import Together

    QWEN_MODEL = "Qwen/Qwen2-72B-Instruct"
    qwen_client = Together(api_key=QWEN_API_KEY)

#### Claude init ####
ANTHROPIC_API_KEY = environ.get("ANTHROPIC_API_KEY")
# use openai for claude
if (CLADUE_USE or CLADUE_COMPLETE or CLADUE_APPEND) and ANTHROPIC_API_KEY:
    ANTHROPIC_BASE_URL = environ.get("ANTHROPIC_BASE_URL")
    ANTHROPIC_MODEL = "claude-3-5-sonnet-20240620"
    claude_client = OpenAI(
        api_key=ANTHROPIC_API_KEY, base_url=ANTHROPIC_BASE_URL, timeout=20
    )

#### llama init ####
LLAMA_API_KEY = environ.get("GROQ_API_KEY")
if (LLAMA_USE or LLAMA_COMPLETE or LLAMA_APPEND) and LLAMA_API_KEY:
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
    # if not text, ignore
    if message.text is None:
        return

    # if is bot command, ignore
    if message.text.startswith("/"):
        return
    # start command ignore
    elif message.text.startswith(
        (
            "md",
            "gpt",
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

    chat_id = message.chat.id
    full_answer = ""
    local_image_path = ""
    m = ""
    original_m = ""

    # get the last message in the chat
    if message.reply_to_message is not None:
        latest_message = message.reply_to_message
    else:
        latest_message = chat_message_dict.get(chat_id)

    if latest_message.photo is not None:
        max_size_photo = max(latest_message.photo, key=lambda p: p.file_size)
        image_file = bot.get_file(max_size_photo.file_id).file_path
        downloaded_file = bot.download_file(image_file)
        local_image_path = "answer_it_temp.jpg"
        with open(local_image_path, "wb") as temp_file:
            temp_file.write(downloaded_file)

        m = original_m = remove_prompt_prefix(latest_message.caption.strip())
        ph_image_url = ph.upload_image(local_image_path)
        full_answer += f"\n![Image]({ph_image_url})\n"
    else:
        m = original_m = remove_prompt_prefix(latest_message.text.strip())

    if not m:
        bot.reply_to(message, "The message was retrieved, but the prompt is empty.")
        return

    m = enrich_text_with_urls(m)

    if len(m) > MESSAGE_MAX_LENGTH:
        a = (
            "The message is too long, please shorten it or try a direct command like `gemini_pro: your question`."
            if Language == "en"
            else "消息太长，请缩短或尝试直接指令例如 `gemini_pro: 你的问题` 。"
        )
        bot.reply_to(message, a)
        return
    full_chat_id_list = []

    ##### Telegraph / APPENDS #####
    ph_executor = ThreadPoolExecutor(max_workers=1)
    ph_future = ph_executor.submit(final_answer, latest_message, bot, full_answer)

    #### Answers Thread ####
    executor = ThreadPoolExecutor(max_workers=Stream_Thread)
    if GEMINI_USE_THREAD and GOOGLE_GEMINI_KEY:
        gemini_future = executor.submit(
            gemini_answer, latest_message, bot, m, local_image_path
        )
    if CHATGPT_USE and CHATGPT_API_KEY:
        chatgpt_future = executor.submit(
            chatgpt_answer, latest_message, bot, m, local_image_path
        )
    if COHERE_USE and COHERE_API_KEY and not local_image_path:
        cohere_future = executor.submit(cohere_answer, latest_message, bot, m)
    if QWEN_USE and QWEN_API_KEY and not local_image_path:
        qwen_future = executor.submit(qwen_answer, latest_message, bot, m)
    if CLADUE_USE and ANTHROPIC_API_KEY:
        claude_future = executor.submit(
            claude_answer, latest_message, bot, m, local_image_path
        )
    if LLAMA_USE and LLAMA_API_KEY and not local_image_path:
        llama_future = executor.submit(llama_answer, latest_message, bot, m)

    #### Complete Message Thread ####
    executor2 = ThreadPoolExecutor(max_workers=Complete_Thread)
    if not CHATGPT_USE and CHATGPT_COMPLETE and CHATGPT_API_KEY:
        complete_chatgpt_future = executor2.submit(
            complete_chatgpt, m, local_image_path
        )
    if not CLADUE_USE and CLADUE_COMPLETE and ANTHROPIC_API_KEY:
        complete_claude_future = executor2.submit(complete_claude, m, local_image_path)
    if not LLAMA_USE and LLAMA_COMPLETE and LLAMA_API_KEY and not local_image_path:
        complete_llama_future = executor2.submit(complete_llama, m)
    if not COHERE_USE and COHERE_COMPLETE and COHERE_API_KEY and not local_image_path:
        complete_cohere_future = executor2.submit(complete_cohere, m)

    #### Gemini Answer Individual ####
    if GEMINI_USE and GOOGLE_GEMINI_KEY:
        g_who = "Gemini"
        g_s = ""
        g_reply_id = bot_reply_first(latest_message, g_who, bot)
        try:
            if local_image_path:
                gemini_image_file = genai.upload_file(path=local_image_path)
                g_r = convo.send_message([m, gemini_image_file], stream=True)
            else:
                g_r = convo.send_message(m, stream=True)

            g_start = time.time()
            g_overall_start = time.time()
            for e in g_r:
                g_s += e.text
                if time.time() - g_start > 1.7:
                    g_start = time.time()
                    bot_reply_markdown(g_reply_id, g_who, g_s, bot, split_text=False)
                if time.time() - g_overall_start > Stream_Timeout:
                    raise Exception("Gemini Timeout")
            bot_reply_markdown(g_reply_id, g_who, g_s, bot)
            try:
                convo.history.clear()
            except:
                print(
                    f"\n------\n{g_who} convo.history.clear() Error / Unstoppable\n------\n"
                )
                pass
        except Exception as e:
            print(f"\n------\n{g_who} function gemini outter Error:\n{e}\n------\n")
            try:
                convo.history.clear()
            except:
                print(
                    f"\n------\n{g_who} convo.history.clear() Error / Unstoppable\n------\n"
                )
                pass
            bot_reply_markdown(g_reply_id, g_who, "Error", bot)
            full_answer += f"\n---\n{g_who}:\nAnswer wrong"
        full_chat_id_list.append(g_reply_id.message_id)
        full_answer += llm_answer(g_who, g_s)
    else:
        pass

    #### Answers List ####

    if GEMINI_USE_THREAD and GOOGLE_GEMINI_KEY:
        answer_gemini, gemini_chat_id = gemini_future.result()
        full_chat_id_list.append(gemini_chat_id)
        full_answer += answer_gemini
    if CHATGPT_USE and CHATGPT_API_KEY:
        anaswer_chatgpt, chatgpt_chat_id = chatgpt_future.result()
        full_chat_id_list.append(chatgpt_chat_id)
        full_answer += anaswer_chatgpt
    if COHERE_USE and COHERE_API_KEY and not local_image_path:
        answer_cohere, cohere_chat_id = cohere_future.result()
        full_chat_id_list.append(cohere_chat_id)
        full_answer += answer_cohere
    if QWEN_USE and QWEN_API_KEY and not local_image_path:
        answer_qwen, qwen_chat_id = qwen_future.result()
        full_chat_id_list.append(qwen_chat_id)
        full_answer += answer_qwen
    if CLADUE_USE and ANTHROPIC_API_KEY:
        answer_claude, claude_chat_id = claude_future.result()
        full_chat_id_list.append(claude_chat_id)
        full_answer += answer_claude
    if LLAMA_USE and LLAMA_API_KEY and not local_image_path:
        answer_llama, llama_chat_id = llama_future.result()
        full_chat_id_list.append(llama_chat_id)
        full_answer += answer_llama

    #### Complete Messages ####
    if not CHATGPT_USE and CHATGPT_COMPLETE and CHATGPT_API_KEY:
        full_answer += complete_chatgpt_future.result()
    if not CLADUE_USE and CLADUE_COMPLETE and ANTHROPIC_API_KEY:
        full_answer += complete_claude_future.result()
    if not COHERE_USE and COHERE_COMPLETE and COHERE_API_KEY and not local_image_path:
        full_answer += complete_cohere_future.result()
    if not LLAMA_USE and LLAMA_COMPLETE and LLAMA_API_KEY and not local_image_path:
        full_answer += complete_llama_future.result()

    print(full_chat_id_list)

    if len(m) < 300:
        full_answer = f"{llm_answer('Question', original_m)}{full_answer}"
    else:
        full_answer = f"{llm_answer('Question', original_m)}{full_answer}{llm_answer('Question', m)}"

    # Append the answer to the telegra.ph page at the front
    ph_s, ph_answers = ph_future.result()
    full_answer = f"{full_answer}\n{ph_answers}"
    ph_s = re.search(r"https?://telegra\.ph/(.+)", ph_s).group(1)
    ph.edit_page_md(path=ph_s, title="Answer it", markdown_text=full_answer)

    # delete the chat message, only leave a telegra.ph link
    if General_clean:
        for i in full_chat_id_list:
            bot.delete_message(chat_id, i)

    if Extra_clean:  # delete the command message
        bot.delete_message(chat_id, message.message_id)


def update_time():
    """Return the current time in UTC+8. Good for testing completion of content."""
    return f"\nLast Update{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} at UTC+8\n"


def llm_answer(who: str, s: str) -> str:
    """Universal llm answer format for telegra.ph. Use title so 'link#title' can be used."""
    return f"\n\n---\n## {who}\n{s}"


def llm_background_ph_update(path: str, full_answer: str, m: str) -> str:
    """Update the telegra.ph page with Non Stream Answer result. Return new full answer."""
    ph_path = re.search(r"https?://telegra\.ph/(.+)", path).group(1)
    full_answer += m + update_time()
    try:
        ph.edit_page_md(path=ph_path, title="Answer it", markdown_text=full_answer)
    except Exception as e:
        print(f"\n------\nllm_background_ph_update Error:\n{e}\n------\n")
    return full_answer


def gemini_answer(latest_message: Message, bot: TeleBot, m, local_image_path):
    """gemini answer"""
    who = "Gemini Pro"
    # show something, make it more responsible
    reply_id = bot_reply_first(latest_message, who, bot)

    try:
        if local_image_path:
            gemini_image_file = genai.upload_file(path=local_image_path)
            r = convo.send_message([m, gemini_image_file], stream=True)
        else:
            r = convo.send_message(m, stream=True)
        s = ""
        start = time.time()
        overall_start = time.time()
        for e in r:
            s += e.text
            if time.time() - start > 1.7:
                start = time.time()
                bot_reply_markdown(reply_id, who, s, bot, split_text=False)
            if time.time() - overall_start > Stream_Timeout:  # Timeout
                raise Exception("Gemini Timeout")
        bot_reply_markdown(reply_id, who, s, bot)
        try:
            convo.history.clear()
        except:
            print(
                f"\n------\n{who} convo.history.clear() Error / Unstoppable\n------\n"
            )
            pass
    except Exception as e:
        print(f"\n------\n{who} function inner Error:\n{e}\n------\n")
        try:
            convo.history.clear()
        except:
            print(
                f"\n------\n{who} convo.history.clear() Error / Unstoppable\n------\n"
            )
            pass
        bot_reply_markdown(reply_id, who, "Error", bot)
        return f"\n---\n{who}:\nAnswer wrong", reply_id.message_id

    return llm_answer(who, s), reply_id.message_id


def chatgpt_answer(latest_message: Message, bot: TeleBot, m, local_image_path):
    """chatgpt answer"""
    who = "ChatGPT Pro"
    reply_id = bot_reply_first(latest_message, who, bot)

    player_message = [{"role": "user", "content": m}]
    if local_image_path:
        player_message = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": m},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_to_data_uri(local_image_path)},
                    },
                ],
            }
        ]

    try:
        r = client.chat.completions.create(
            messages=player_message,
            max_tokens=4096,
            model=CHATGPT_PRO_MODEL,
            stream=True,
        )
        s = ""
        start = time.time()
        overall_start = time.time()
        for chunk in r:
            if chunk.choices[0].delta.content is None:
                break
            s += chunk.choices[0].delta.content
            if time.time() - start > 1.5:
                start = time.time()
                bot_reply_markdown(reply_id, who, s, bot, split_text=False)
            if time.time() - overall_start > Stream_Timeout:  # Timeout
                s += "\n\nTimeout"
                break
        # maybe not complete
        try:
            bot_reply_markdown(reply_id, who, s, bot)
        except:
            pass

    except Exception as e:
        print(f"\n------\n{who} function inner Error:\n{e}\n------\n")
        return f"\n---\n{who}:\nAnswer wrong", reply_id.message_id

    return llm_answer(who, s), reply_id.message_id


def claude_answer(latest_message: Message, bot: TeleBot, m, local_image_path):
    """claude answer"""
    who = "Claude Pro"
    reply_id = bot_reply_first(latest_message, who, bot)

    player_message = [{"role": "user", "content": m}]
    if local_image_path:
        player_message = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": m},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_to_data_uri(local_image_path)},
                    },
                ],
            }
        ]

    try:
        r = claude_client.chat.completions.create(
            messages=player_message,
            max_tokens=4096,
            model=ANTHROPIC_MODEL,
            stream=True,
        )
        s = ""
        start = time.time()
        overall_start = time.time()
        for chunk in r:
            if chunk.choices[0].delta.content is None:
                break
            s += chunk.choices[0].delta.content
            if time.time() - start > 1.5:
                start = time.time()
                bot_reply_markdown(reply_id, who, s, bot, split_text=False)
            if time.time() - overall_start > Stream_Timeout:  # Timeout
                s += "\n\nTimeout"
                break
        # maybe not complete
        try:
            bot_reply_markdown(reply_id, who, s, bot)
        except:
            pass

    except Exception as e:
        print(f"\n------\n{who} function inner Error:\n{e}\n------\n")
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
        overall_start = time.time()
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
                if time.time() - overall_start > Stream_Timeout:  # Timeout
                    s += "\n\nTimeout"
                    break
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
        return f"\n---\n{who}:\nAnswer wrong", reply_id.message_id

    return llm_answer(who, content), reply_id.message_id


def qwen_answer(latest_message: Message, bot: TeleBot, m):
    """qwen answer"""
    who = "qwen Pro"
    reply_id = bot_reply_first(latest_message, who, bot)
    try:
        r = qwen_client.chat.completions.create(
            messages=[
                {
                    "content": f"You are an AI assistant added to a group chat to provide help or answer questions. You only have access to the most recent message in the chat, which will be the next message you receive after this system prompt. Your task is to provide a helpful and relevant response based on this information.\n\nPlease adhere to these guidelines when formulating your response:\n\n1. Address the content of the message directly and proactively.\n2. If the message is a question or request, provide a comprehensive answer or assistance to the best of your ability.\n3. Use your general knowledge and capabilities to fill in gaps where context might be missing.\n4. Keep your response concise yet informative, appropriate for a group chat setting.\n5. Maintain a friendly, helpful, and confident tone throughout.\n6. If the message is unclear:\n   - Make reasonable assumptions to provide a useful response.\n   - If necessary, offer multiple interpretations or answers to cover possible scenarios.\n7. Aim to make your response as complete and helpful as possible, even with limited context.\n8. You must respond in {Language}.\n\nYour response should be natural and fitting for a group chat context. While you only have access to this single message, use your broad knowledge base to provide informative and helpful answers. Be confident in your responses, but if you're making assumptions, briefly acknowledge this fact.\n\nRemember, the group administrator has approved your participation and will review responses as needed, so focus on being as helpful as possible rather than being overly cautious.",
                    "role": "system",
                },
                {"role": "user", "content": m},
            ],
            max_tokens=8192,
            model=QWEN_MODEL,
            stream=True,
        )
        s = ""
        start = time.time()
        overall_start = time.time()
        for chunk in r:
            if chunk.choices[0].delta.content is None:
                break
            s += chunk.choices[0].delta.content
            if time.time() - start > 1.5:
                start = time.time()
                bot_reply_markdown(reply_id, who, s, bot, split_text=False)
            if time.time() - overall_start > Stream_Timeout:  # Timeout
                s += "\n\nTimeout"
                break
        # maybe not complete
        try:
            bot_reply_markdown(reply_id, who, s, bot)
        except:
            pass

    except Exception as e:
        print(f"\n------\n{who} function inner Error:\n{e}\n------\n")
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
        overall_start = time.time()
        for chunk in r:
            if chunk.choices[0].delta.content is None:
                break
            s += chunk.choices[0].delta.content
            if time.time() - start > 1.5:
                start = time.time()
                bot_reply_markdown(reply_id, who, s, bot, split_text=False)
            if time.time() - overall_start > Stream_Timeout:  # Timeout
                raise Exception("Llama Timeout")
        # maybe not complete
        try:
            bot_reply_markdown(reply_id, who, s, bot)
        except:
            pass

    except Exception as e:
        print(f"\n------\n{who} function inner Error:\n{e}\n------\n")
        return f"\n---\n{who}:\nAnswer wrong", reply_id.message_id

    return llm_answer(who, s), reply_id.message_id


# TODO: Perplexity looks good. `pplx_answer`


def final_answer(latest_message: Message, bot: TeleBot, full_answer: str):
    """final answer"""
    who = "Answer it"
    reply_id = bot_reply_first(latest_message, who, bot)

    # If disappeared means the answer is not complete in telegra.ph
    full_answer += update_time()

    # greate new telegra.ph page
    ph_s = ph.create_page_md(title="Answer it", markdown_text=full_answer)
    m = f"**[{('🔗Full Answer' if Language == 'en' else '🔗全文')}]({ph_s})**{Hint}"
    bot_reply_markdown(reply_id, who, m, bot)

    #### Background LLM ####
    # Run background llm, no show to telegram, just append the ph page, Good for slow llm
    # Make a thread to run the background llm.
    # But `append_xxx` with threadpool may cause ph update skip.
    answer_lock = Lock()

    def append_answers(result, llm_name):
        nonlocal full_answer, m
        with answer_lock:
            full_answer = llm_background_ph_update(ph_s, full_answer, result)

    with ThreadPoolExecutor(max_workers=Complete_Thread) as executor:
        futures = []

        api_calls = [
            (CHATGPT_APPEND, CHATGPT_API_KEY, complete_chatgpt, "ChatGPT"),
            (CLADUE_APPEND, ANTHROPIC_API_KEY, complete_claude, "Claude"),
            (COHERE_APPEND, COHERE_API_KEY, complete_cohere, "Cohere"),
            (LLAMA_APPEND, LLAMA_API_KEY, complete_llama, "LLaMA"),
            (QWEN_APPEND, QWEN_API_KEY, complete_qwen, "Qwen"),
        ]

        for condition, api_key, func, name in api_calls:
            if condition and api_key:
                futures.append(executor.submit(func, latest_message.text))

        for future in as_completed(futures):
            try:
                result = future.result(timeout=Stream_Timeout)
                api_name = api_calls[futures.index(future)][3]
                append_answers(result, api_name)
            except Exception as e:
                print(f"An API call failed: {e}")

    m += "✔️"
    bot_reply_markdown(reply_id, who, m, bot)

    if SUMMARY is not None:
        s = llm_summary(bot, full_answer, ph_s, reply_id)
        bot_reply_markdown(reply_id, who, s, bot, disable_web_page_preview=True)

    return ph_s, full_answer


def append_message_to_ph_front(m: str, path: str) -> bool:
    """We append the message to the ph page."""
    ph_path = re.search(r"https?://telegra\.ph/(.+)", path).group(1)
    try:
        content = ph._md_to_dom(m)  # convert to ph dom
        latest_ph = ph.get_page(
            ph_path
        )  # after chatgpt done, we read the latest telegraph
        if "content" in latest_ph and isinstance(latest_ph["content"], list):
            new_content = content + latest_ph["content"]
        else:
            new_content = content
        time.sleep(1)
        ph.edit_page(ph_path, title="Answer it", content=new_content)
        return True
    except Exception as e:
        print(f"\n---\nappend_message_to_ph_front Error:\n{e}\n---\n")
        return False


def append_chatgpt(m: str, ph_path: str) -> bool:
    """we run chatgpt by complete_chatgpt and we append it to the ph page. Return True if success, False if fail like timeout."""
    try:
        chatgpt_a = complete_chatgpt(m)  # call chatgpt
        print(f"\n---\nchatgpt_a:\n{chatgpt_a}\n---\n")
        content = ph._md_to_dom(chatgpt_a)  # convert to ph dom
        latest_ph = ph.get_page(
            ph_path
        )  # after chatgpt done, we read the latest telegraph
        new_content = latest_ph + content  # merge the content
        ph.edit_page(
            ph_path, title="Answer it", content=new_content
        )  # update the telegraph TODO: update too fast may cause skip
        return True
    except:
        return False


def llm_summary(bot, full_answer, ph_s, reply_id) -> str:
    """llm summary return the summary of the full answer."""
    if SUMMARY == "gemini":
        s = summary_gemini(bot, full_answer, ph_s, reply_id)
    elif SUMMARY == "cohere":
        s = summary_cohere(bot, full_answer, ph_s, reply_id)
    else:
        print(f"\n---\nSummary Fail\n---\n")
        s = f"**[Full Answer]({ph_s})**\n~~Summary Answer Wrong~~\n"
    return s


def complete_chatgpt(m: str, local_image_path: str) -> str:
    """we run chatgpt get the full answer"""
    who = "ChatGPT Pro"
    player_message = [{"role": "user", "content": m}]
    if local_image_path:
        player_message = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": m},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_to_data_uri(local_image_path)},
                    },
                ],
            }
        ]
    try:
        r = client.chat.completions.create(
            messages=player_message,
            max_tokens=4096,
            model=CHATGPT_PRO_MODEL,
        )
        s = r.choices[0].message.content.encode("utf-8").decode()
        content = llm_answer(who, s)
    except Exception as e:
        print(f"\n------\ncomplete_chatgpt Error:\n{e}\n------\n")
        content = llm_answer(who, "Non Stream Answer wrong")
    return content


def complete_claude(m: str, local_image_path: str) -> str:
    """we run claude get the full answer"""
    who = "Claude Pro"

    player_message = [{"role": "user", "content": m}]
    if local_image_path:
        player_message = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": m},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_to_data_uri(local_image_path)},
                    },
                ],
            }
        ]
    try:
        r = claude_client.chat.completions.create(
            messages=player_message,
            max_tokens=4096,
            model=ANTHROPIC_MODEL,
        )
        s = r.choices[0].message.content.encode("utf-8").decode()
        content = llm_answer(who, s)
    except Exception as e:
        print(f"\n------\ncomplete_claude Error:\n{e}\n------\n")
        content = llm_answer(who, "Non Stream Answer wrong")
    return content


def complete_cohere(m: str) -> str:
    """we run cohere get the full answer"""
    who = "Command R Plus"
    try:
        overall_start = time.time()
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
            if time.time() - overall_start > Stream_Timeout:  # Timeout
                s += "\n\nTimeout"
                break
        content = llm_answer(who, f"{s}\n\n---\n{source}")

    except Exception as e:
        print(f"\n------\ncomplete_cohere Error:\n{e}\n------\n")
        content = llm_answer(who, "Non Stream Answer wrong")
    return content


def complete_llama(m: str) -> str:
    """we run llama get the full answer"""
    who = "llama"
    try:
        overall_start = time.time()
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
            if time.time() - overall_start > Stream_Timeout:  # Timeout
                raise Exception("Llama complete Running Timeout")

    except Exception as e:
        print(f"\n------\ncomplete_llama Error:\n{e}\n------\n")
        s = "Non Stream Answer wrong"
    return llm_answer(who, s)


def complete_qwen(m: str) -> str:
    """we run qwen get the full answer"""
    who = "qwen Pro"
    try:
        overall_start = time.time()
        r = qwen_client.chat.completions.create(
            messages=[
                {
                    "content": f"You are an AI assistant added to a group chat to provide help or answer questions. You only have access to the most recent message in the chat, which will be the next message you receive after this system prompt. Your task is to provide a helpful and relevant response based on this information.\n\nPlease adhere to these guidelines when formulating your response:\n\n1. Address the content of the message directly and proactively.\n2. If the message is a question or request, provide a comprehensive answer or assistance to the best of your ability.\n3. Use your general knowledge and capabilities to fill in gaps where context might be missing.\n4. Keep your response concise yet informative, appropriate for a group chat setting.\n5. Maintain a friendly, helpful, and confident tone throughout.\n6. If the message is unclear:\n   - Make reasonable assumptions to provide a useful response.\n   - If necessary, offer multiple interpretations or answers to cover possible scenarios.\n7. Aim to make your response as complete and helpful as possible, even with limited context.\n8. You must respond in {Language}.\n\nYour response should be natural and fitting for a group chat context. While you only have access to this single message, use your broad knowledge base to provide informative and helpful answers. Be confident in your responses, but if you're making assumptions, briefly acknowledge this fact.\n\nRemember, the group administrator has approved your participation and will review responses as needed, so focus on being as helpful as possible rather than being overly cautious.",
                    "role": "system",
                },
                {"role": "user", "content": m},
            ],
            max_tokens=8192,
            model=QWEN_MODEL,
            stream=True,
        )
        s = ""
        for chunk in r:
            if chunk.choices[0].delta.content is None:
                break
            s += chunk.choices[0].delta.content
            if time.time() - overall_start > Stream_Timeout:  # Timeout
                raise Exception("Qwen complete Running Timeout")
    except Exception as e:
        print(f"\n------\ncomplete_qwen Error:\n{e}\n------\n")
        s = "Non Stream Answer wrong"
    return llm_answer(who, s)


def summary_cohere(bot: TeleBot, full_answer: str, ph_s: str, reply_id: int) -> str:
    """Receive the full text, and the final_answer's chat_id, update with a summary."""
    who = "Answer it"

    # inherit
    if Language == "zh-cn":
        s = f"**[全文]({ph_s})**{Hint}\n"
    elif Language == "en":
        s = f"**[Full Answer]({ph_s})**{Hint}\n"

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
        overall_start = time.time()
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
            if time.time() - overall_start > Stream_Timeout:
                s += "\n\nTimeout"
                break

        try:
            bot_reply_markdown(reply_id, who, s, bot)
        except:
            pass
        return s

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
        s = f"**[🔗全文]({ph_s})**{Hint}\n"
    elif Language == "en":
        s = f"**[🔗Full Answer]({ph_s})**{Hint}\n"

    try:
        r = convo_summary.send_message(full_answer, stream=True)
        start = time.time()
        overall_start = time.time()
        for e in r:
            s += e.text
            if time.time() - start > 0.4:
                start = time.time()
                bot_reply_markdown(reply_id, who, s, bot, split_text=False)
            if time.time() - overall_start > Stream_Timeout:
                raise Exception("Gemini Summary Timeout")
        bot_reply_markdown(reply_id, who, s, bot)
        convo_summary.history.clear()
        return s
    except Exception as e:
        if Language == "zh-cn":
            bot_reply_markdown(reply_id, who, f"[全文]({ph_s}){Hint}", bot)
        elif Language == "en":
            bot_reply_markdown(reply_id, who, f"[Full Answer]({ph_s}){Hint}", bot)
        try:
            convo.history.clear()
        except:
            print(
                f"\n------\n{who} convo.history.clear() Error / Unstoppable\n------\n"
            )
            pass
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
