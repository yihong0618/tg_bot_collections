import json
import time
from typing import Any

from anthropic import Anthropic
from expiringdict import ExpiringDict
from openai import OpenAI
from telebot import TeleBot
from telebot.types import Message

from config import settings

from ._utils import bot_reply_first, bot_reply_markdown, enrich_text_with_urls, logger

MINIMAX_MODEL = settings.minimax_model
OPENAI_BASE_URL = "https://api.minimax.io/v1"
ANTHROPIC_BASE_URL = "https://api.minimax.io/anthropic"


def _create_client() -> OpenAI | Anthropic | None:
    if not settings.minimax_api_key:
        return None
    if settings.minimax_api_type == "anthropic":
        return Anthropic(
            api_key=settings.minimax_api_key,
            base_url=settings.minimax_base_url or ANTHROPIC_BASE_URL,
        )
    return OpenAI(
        api_key=settings.minimax_api_key,
        base_url=settings.minimax_base_url or OPENAI_BASE_URL,
    )


client = _create_client()

# Global history cache
minimax_player_dict = ExpiringDict(max_len=1000, max_age_seconds=600)
minimax_pro_player_dict = ExpiringDict(max_len=1000, max_age_seconds=600)


def _anthropic_text(content: list[Any]) -> str:
    return "".join(
        block.text for block in content if getattr(block, "type", None) == "text"
    )


def _complete(messages: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    if client is None:
        raise RuntimeError("MiniMax API key is not configured")
    if settings.minimax_api_type == "anthropic":
        response = client.messages.create(
            messages=messages,
            max_tokens=4096,
            model=MINIMAX_MODEL,
        )
        return _anthropic_text(response.content), {
            "role": response.role,
            "content": response.content,
        }

    response = client.chat.completions.create(
        messages=messages,
        max_tokens=4096,
        model=MINIMAX_MODEL,
    )
    message = response.choices[0].message
    return message.content or "", message.model_dump(exclude_none=True)


def _stream(
    messages: list[dict[str, Any]], reply_id: Message, who: str, bot: TeleBot
) -> tuple[str, dict[str, Any]]:
    if client is None:
        raise RuntimeError("MiniMax API key is not configured")

    text = ""
    last_update = time.time()
    if settings.minimax_api_type == "anthropic":
        blocks: dict[int, dict[str, Any]] = {}
        tool_inputs: dict[int, str] = {}
        # Preserve thinking deltas even with older SDKs that do not accumulate
        # thinking blocks in their high-level messages.stream helper.
        with client.messages.create(
            messages=messages,
            max_tokens=8192,
            model=MINIMAX_MODEL,
            stream=True,
        ) as stream:
            for event in stream:
                if event.type == "content_block_start":
                    blocks[event.index] = event.content_block.model_dump(
                        exclude_none=True
                    )
                elif event.type == "content_block_delta":
                    block = blocks[event.index]
                    delta = event.delta
                    if delta.type == "input_json_delta":
                        tool_inputs[event.index] = (
                            tool_inputs.get(event.index, "") + delta.partial_json
                        )
                    elif delta.type in (
                        "text_delta",
                        "thinking_delta",
                        "signature_delta",
                    ):
                        field = delta.type.removesuffix("_delta")
                        block[field] = block.get(field, "") + getattr(delta, field)
                        if field == "text":
                            text += delta.text
                            if time.time() - last_update > 1.7:
                                last_update = time.time()
                                bot_reply_markdown(
                                    reply_id, who, text, bot, split_text=False
                                )
                elif event.type == "content_block_stop" and event.index in tool_inputs:
                    blocks[event.index]["input"] = json.loads(tool_inputs[event.index])
        return text, {
            "role": "assistant",
            "content": [blocks[i] for i in sorted(blocks)],
        }

    response = client.chat.completions.create(
        messages=messages,
        max_tokens=8192,
        model=MINIMAX_MODEL,
        stream=True,
    )
    reasoning = ""
    tool_calls: dict[int, dict[str, Any]] = {}
    for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        reasoning += getattr(delta, "reasoning_content", None) or ""
        for call in delta.tool_calls or []:
            tool = tool_calls.setdefault(
                call.index,
                {
                    "id": "",
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                },
            )
            if call.id:
                tool["id"] = call.id
            if call.type:
                tool["type"] = call.type
            if call.function:
                tool["function"]["name"] += call.function.name or ""
                tool["function"]["arguments"] += call.function.arguments or ""
        if not delta.content:
            continue
        text += delta.content
        if time.time() - last_update > 1.7:
            last_update = time.time()
            bot_reply_markdown(reply_id, who, text, bot, split_text=False)
    assistant_message: dict[str, Any] = {"role": "assistant", "content": text}
    if reasoning:
        assistant_message["reasoning_content"] = reasoning
    if tool_calls:
        assistant_message["tool_calls"] = [tool_calls[i] for i in sorted(tool_calls)]
    return text, assistant_message


def minimax_handler(message: Message, bot: TeleBot) -> None:
    """minimax : /minimax <question>"""
    prompt = message.text.strip()
    user_id = str(message.from_user.id)
    messages = minimax_player_dict.setdefault(user_id, [])

    if prompt == "clear":
        bot.reply_to(message, "just clear your minimax messages history")
        messages.clear()
        return
    if prompt[:4].lower() == "new ":
        prompt = prompt[4:].strip()
        messages.clear()
    prompt = enrich_text_with_urls(prompt)

    who = "MiniMax"
    reply_id = bot_reply_first(message, who, bot)
    messages.append({"role": "user", "content": prompt})
    if len(messages) > 10:
        del messages[:2]

    try:
        text, assistant_message = _complete(messages)
        if not text:
            messages.pop()
            text = f"{who} did not answer."
        else:
            messages.append(assistant_message)
    except Exception:
        logger.exception("MiniMax handler error")
        bot.reply_to(message, "answer wrong maybe up to the max token")
        messages.pop()
        return

    bot_reply_markdown(reply_id, who, text, bot)


def minimax_pro_handler(message: Message, bot: TeleBot) -> None:
    """minimax_pro : /minimax_pro <question>"""
    prompt = message.text.strip()
    user_id = str(message.from_user.id)
    messages = minimax_pro_player_dict.setdefault(user_id, [])

    if prompt == "clear":
        bot.reply_to(message, "just clear your minimax messages history")
        messages.clear()
        return
    if prompt[:4].lower() == "new ":
        prompt = prompt[4:].strip()
        messages.clear()
    prompt = enrich_text_with_urls(prompt)

    who = "MiniMax Pro"
    reply_id = bot_reply_first(message, who, bot)
    messages.append({"role": "user", "content": prompt})
    if len(messages) > 10:
        del messages[:2]

    try:
        text, assistant_message = _stream(messages, reply_id, who, bot)
        if not text:
            messages.pop()
            bot_reply_markdown(reply_id, who, f"{who} did not answer.", bot)
            return
        if not bot_reply_markdown(reply_id, who, text, bot):
            messages.clear()
            return
        messages.append(assistant_message)
    except Exception:
        logger.exception("MiniMax Pro handler error")
        bot.reply_to(message, "answer wrong maybe up to the max token")
        messages.clear()


if client is not None:

    def register(bot: TeleBot) -> None:
        bot.register_message_handler(
            minimax_handler, commands=["minimax"], pass_bot=True
        )
        bot.register_message_handler(minimax_handler, regexp="^minimax:", pass_bot=True)
        bot.register_message_handler(
            minimax_pro_handler, commands=["minimax_pro"], pass_bot=True
        )
        bot.register_message_handler(
            minimax_pro_handler, regexp="^minimax_pro:", pass_bot=True
        )
