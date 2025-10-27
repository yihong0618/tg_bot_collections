import json
import time
import uuid
from typing import Any

import requests
from expiringdict import ExpiringDict
from telebot import TeleBot
from telebot.types import Message

from config import settings

from ._utils import (
    bot_reply_first,
    bot_reply_markdown,
    enrich_text_with_urls,
    image_to_data_uri,
    logger,
)

CHATGPT_MODEL = settings.openai_model
CHATGPT_PRO_MODEL = settings.openai_model


client = settings.openai_client


# Web search / tool-calling configuration
WEB_SEARCH_TOOL_NAME = "web_search"
OLLAMA_WEB_SEARCH_URL = "https://ollama.com/api/web_search"
WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": WEB_SEARCH_TOOL_NAME,
        "description": (
            "Use the Ollama Cloud Web Search API to fetch recent information"
            " from the public internet. Call this when you need up-to-date"
            " facts, news, or citations."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keywords or question.",
                },
                "max_results": {
                    "type": "integer",
                    "description": (
                        "Maximum number of search results to fetch; defaults"
                        " to the bot configuration if omitted."
                    ),
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["query"],
        },
    },
}
STREAMING_UPDATE_INTERVAL = 1.2
MAX_TOOL_ITERATIONS = 3


# Global history cache
chatgpt_player_dict = ExpiringDict(max_len=1000, max_age_seconds=600)
chatgpt_pro_player_dict = ExpiringDict(max_len=1000, max_age_seconds=600)


def _web_search_available() -> bool:
    return bool(settings.ollama_web_search_api_key)


def _format_web_search_results(payload: dict[str, Any]) -> str:
    results = payload.get("results") or payload.get("data") or []
    if not isinstance(results, list):
        results = []
    formatted: list[str] = []
    for idx, item in enumerate(results, start=1):
        if not isinstance(item, dict):
            continue
        title = (
            item.get("title") or item.get("name") or item.get("url") or f"Result {idx}"
        )
        url = item.get("url") or item.get("link") or item.get("source") or ""
        snippet = (
            item.get("snippet")
            or item.get("summary")
            or item.get("content")
            or item.get("description")
            or ""
        ).strip()
        snippet = snippet.replace("\n", " ")
        if len(snippet) > 400:
            snippet = snippet[:397].rstrip() + "..."
        entry = f"[{idx}] {title}"
        if url:
            entry = f"{entry}\n{url}"
        if snippet:
            entry = f"{entry}\n{snippet}"
        formatted.append(entry)
    if formatted:
        return "\n\n".join(formatted)
    return json.dumps(payload, ensure_ascii=False)


def _call_ollama_web_search(query: str, max_results: int | None = None) -> str:
    if not _web_search_available():
        return "Web search is not configured."
    payload: dict[str, Any] = {"query": query.strip()}
    limit = max_results if isinstance(max_results, int) else None
    if limit is None or limit <= 0:
        limit = settings.ollama_web_search_max_results
    if limit:
        payload["max_results"] = int(limit)
    headers = {
        "Authorization": f"Bearer {settings.ollama_web_search_api_key}",
    }
    try:
        response = requests.post(
            OLLAMA_WEB_SEARCH_URL,
            json=payload,
            headers=headers,
            timeout=settings.ollama_web_search_timeout,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        logger.exception("Ollama web search failed: %s", exc)
        return f"Web search error: {exc}"
    except ValueError:
        logger.exception("Invalid JSON payload from Ollama web search")
        return "Web search error: invalid payload."
    return _format_web_search_results(data)


def _available_tools() -> list[dict[str, Any]]:
    if not _web_search_available():
        return []
    return [WEB_SEARCH_TOOL]


def _accumulate_tool_call_deltas(
    buffer: dict[int, dict[str, Any]],
    deltas: list[Any],
) -> None:
    for delta in deltas:
        idx = getattr(delta, "index", 0) or 0
        entry = buffer.setdefault(
            idx,
            {
                "id": getattr(delta, "id", None),
                "type": getattr(delta, "type", "function") or "function",
                "function": {"name": "", "arguments": ""},
            },
        )
        if getattr(delta, "id", None):
            entry["id"] = delta.id
        if getattr(delta, "type", None):
            entry["type"] = delta.type
        func = getattr(delta, "function", None)
        if func is not None:
            if getattr(func, "name", None):
                entry["function"]["name"] = func.name
            if getattr(func, "arguments", None):
                entry["function"]["arguments"] += func.arguments


def _finalize_tool_calls(buffer: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    tool_calls: list[dict[str, Any]] = []
    for idx in sorted(buffer):
        entry = buffer[idx]
        function_name = entry.get("function", {}).get("name")
        if not function_name:
            continue
        arguments = entry.get("function", {}).get("arguments", "{}")
        tool_calls.append(
            {
                "id": entry.get("id") or str(uuid.uuid4()),
                "type": entry.get("type") or "function",
                "function": {
                    "name": function_name,
                    "arguments": arguments,
                },
            }
        )
    return tool_calls


def _execute_tool(function_name: str, arguments_json: str) -> str:
    try:
        arguments = json.loads(arguments_json or "{}")
    except json.JSONDecodeError as exc:
        logger.exception("Invalid tool arguments for %s: %s", function_name, exc)
        return f"Invalid arguments for {function_name}: {exc}"

    if function_name == WEB_SEARCH_TOOL_NAME:
        query = (arguments.get("query") or "").strip()
        if not query:
            return "Web search error: no query provided."
        max_results = arguments.get("max_results")
        if isinstance(max_results, str):
            max_results = int(max_results) if max_results.isdigit() else None
        elif not isinstance(max_results, int):
            max_results = None
        return _call_ollama_web_search(query, max_results)

    return f"Function {function_name} is not implemented."


def _append_tool_messages(
    conversation: list[dict[str, Any]], tool_calls: list[dict[str, Any]]
) -> None:
    if not tool_calls:
        return
    conversation.append(
        {
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls,
        }
    )
    for call in tool_calls:
        result = _execute_tool(
            call["function"]["name"], call["function"].get("arguments", "{}")
        )
        conversation.append(
            {
                "role": "tool",
                "tool_call_id": call["id"],
                "content": result,
            }
        )


def _stream_chatgpt_pro_response(
    conversation: list[dict[str, Any]],
    reply_id: Message,
    who: str,
    bot: TeleBot,
) -> str:
    tools = _available_tools()
    tool_loops_remaining = MAX_TOOL_ITERATIONS if tools else 0
    final_response = ""
    while True:
        request_payload: dict[str, Any] = {
            "messages": conversation,
            "model": CHATGPT_PRO_MODEL,
            "stream": True,
        }
        if tools:
            request_payload["tools"] = tools

        stream = client.chat.completions.create(**request_payload)
        buffer = ""
        pending_tool_call = False
        tool_buffer: dict[int, dict[str, Any]] = {}
        last_update = time.time()

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta is None:
                continue
            if delta.tool_calls:
                pending_tool_call = True
                _accumulate_tool_call_deltas(tool_buffer, delta.tool_calls)
                continue
            content_piece = delta.content
            if isinstance(content_piece, list):
                content_piece = "".join(
                    getattr(part, "text", "") for part in content_piece
                )
            if not content_piece:
                continue
            buffer += content_piece
            now = time.time()
            if not pending_tool_call and now - last_update > STREAMING_UPDATE_INTERVAL:
                last_update = now
                bot_reply_markdown(reply_id, who, buffer, bot, split_text=False)

        if pending_tool_call and tools:
            if tool_loops_remaining <= 0:
                logger.warning(
                    "chatgpt_pro_handler reached the maximum number of tool calls"
                )
                final_response = buffer or "Unable to finish after calling tools."
                break
            tool_calls = _finalize_tool_calls(tool_buffer)
            if any(
                call["function"]["name"] == WEB_SEARCH_TOOL_NAME for call in tool_calls
            ):
                bot_reply_markdown(
                    reply_id,
                    who,
                    "Searching the web for up-to-date information…",
                    bot,
                    split_text=False,
                    disable_web_page_preview=True,
                )
            _append_tool_messages(conversation, tool_calls)
            tool_loops_remaining -= 1
            continue

        final_response = buffer
        break

    if not final_response:
        final_response = "I could not generate a response."
    bot_reply_markdown(reply_id, who, final_response, bot, split_text=True)
    return final_response


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
        reply_text = _stream_chatgpt_pro_response(player_message, reply_id, who, bot)
        player_message.append(
            {
                "role": "assistant",
                "content": reply_text,
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
