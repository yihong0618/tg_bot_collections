import logging
import os
import time
from typing import Any

from expiringdict import ExpiringDict
from telebot import TeleBot
from telebot.types import Message

from config import settings

from ._utils import bot_reply_first, bot_reply_markdown, enrich_text_with_urls, logger

LITELLM_MODEL = settings.litellm_model


def _load_litellm() -> Any:
    # litellm is an optional extra: `pip install litellm`.
    try:
        import litellm
    except ImportError:
        return None
    if not os.getenv("LITELLM_LOG"):
        # LiteLLM logs every call at INFO and prints a help banner on errors.
        litellm.suppress_debug_info = True
        logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    return litellm


litellm = _load_litellm()

# Global history cache
litellm_player_dict = ExpiringDict(max_len=1000, max_age_seconds=600)
litellm_pro_player_dict = ExpiringDict(max_len=1000, max_age_seconds=600)


def _request_kwargs() -> dict[str, Any]:
    if litellm is None or not LITELLM_MODEL:
        raise RuntimeError("LiteLLM is not installed or LITELLM_MODEL is not set")
    kwargs: dict[str, Any] = {
        "model": LITELLM_MODEL,
        # Drop params a provider does not accept instead of failing the call.
        "drop_params": True,
    }
    # Blank credentials are left out so LiteLLM reads the provider's own env vars
    # (ANTHROPIC_API_KEY, AWS credentials for bedrock/, ...).
    if settings.litellm_api_key:
        kwargs["api_key"] = settings.litellm_api_key
    if settings.litellm_api_base:
        kwargs["api_base"] = settings.litellm_api_base
    return kwargs


def _assistant_message(
    text: str,
    reasoning: str | None = None,
    thinking_blocks: list[dict[str, Any]] | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Keep reasoning and tool calls so the next turn sends them back."""
    message: dict[str, Any] = {"role": "assistant", "content": text}
    if reasoning:
        message["reasoning_content"] = reasoning
    if thinking_blocks:
        message["thinking_blocks"] = thinking_blocks
    if tool_calls:
        message["tool_calls"] = tool_calls
    return message


def _as_dict(value: Any) -> dict[str, Any]:
    return (
        value.model_dump(exclude_none=True) if hasattr(value, "model_dump") else value
    )


def _complete(messages: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    response = litellm.completion(
        messages=messages,
        max_tokens=4096,
        **_request_kwargs(),
    )
    message = response.choices[0].message
    text = message.content or ""
    return text, _assistant_message(
        text,
        getattr(message, "reasoning_content", None),
        [_as_dict(block) for block in getattr(message, "thinking_blocks", None) or []],
        [_as_dict(call) for call in message.tool_calls or []],
    )


def _stream(
    messages: list[dict[str, Any]], reply_id: Message, who: str, bot: TeleBot
) -> tuple[str, dict[str, Any]]:
    response = litellm.completion(
        messages=messages,
        max_tokens=8192,
        stream=True,
        **_request_kwargs(),
    )
    text = ""
    reasoning = ""
    thinking_blocks: list[dict[str, Any]] = []
    tool_calls: dict[int, dict[str, Any]] = {}
    last_update = time.time()
    for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        reasoning += getattr(delta, "reasoning_content", None) or ""
        thinking_blocks.extend(
            _as_dict(block) for block in getattr(delta, "thinking_blocks", None) or []
        )
        for call in delta.tool_calls or []:
            tool = tool_calls.setdefault(
                call.index or 0,
                {
                    "id": "",
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                },
            )
            if call.id:
                tool["id"] = call.id
            if call.function:
                tool["function"]["name"] += call.function.name or ""
                tool["function"]["arguments"] += call.function.arguments or ""
        if not delta.content:
            continue
        text += delta.content
        if time.time() - last_update > 1.7:
            last_update = time.time()
            bot_reply_markdown(reply_id, who, text, bot, split_text=False)
    return text, _assistant_message(
        text,
        reasoning,
        thinking_blocks,
        [tool_calls[i] for i in sorted(tool_calls)],
    )


def litellm_handler(message: Message, bot: TeleBot) -> None:
    """litellm : /litellm <question>"""
    prompt = message.text.strip()
    user_id = str(message.from_user.id)
    messages = litellm_player_dict.setdefault(user_id, [])

    if prompt == "clear":
        bot.reply_to(message, "just clear your litellm messages history")
        messages.clear()
        return
    if prompt[:4].lower() == "new ":
        prompt = prompt[4:].strip()
        messages.clear()
    prompt = enrich_text_with_urls(prompt)

    who = f"LiteLLM ({LITELLM_MODEL})"
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
        logger.exception("LiteLLM handler error")
        bot.reply_to(message, "answer wrong maybe up to the max token")
        messages.pop()
        return

    bot_reply_markdown(reply_id, who, text, bot)


def litellm_pro_handler(message: Message, bot: TeleBot) -> None:
    """litellm_pro : /litellm_pro <question>"""
    prompt = message.text.strip()
    user_id = str(message.from_user.id)
    messages = litellm_pro_player_dict.setdefault(user_id, [])

    if prompt == "clear":
        bot.reply_to(message, "just clear your litellm messages history")
        messages.clear()
        return
    if prompt[:4].lower() == "new ":
        prompt = prompt[4:].strip()
        messages.clear()
    prompt = enrich_text_with_urls(prompt)

    who = f"LiteLLM Pro ({LITELLM_MODEL})"
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
        logger.exception("LiteLLM Pro handler error")
        bot.reply_to(message, "answer wrong maybe up to the max token")
        messages.clear()


if litellm is not None and LITELLM_MODEL:

    def register(bot: TeleBot) -> None:
        bot.register_message_handler(
            litellm_handler, commands=["litellm"], pass_bot=True
        )
        bot.register_message_handler(litellm_handler, regexp="^litellm:", pass_bot=True)
        bot.register_message_handler(
            litellm_pro_handler, commands=["litellm_pro"], pass_bot=True
        )
        bot.register_message_handler(
            litellm_pro_handler, regexp="^litellm_pro:", pass_bot=True
        )
