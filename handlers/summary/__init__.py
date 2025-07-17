from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import partial
import shlex

import telegramify_markdown
from telebot import TeleBot
from telebot.types import Message
from wcwidth import wcswidth

from config import settings
from handlers._utils import non_llm_handler

from .messages import ChatMessage, MessageStore
from .utils import PROMPT, filter_message, parse_date

logger = logging.getLogger("bot")
store = MessageStore("data/messages.db")


def get_display_width(text: str) -> int:
    """获取字符串的显示宽度，考虑中文字符"""
    width = wcswidth(text)
    return width if width is not None else len(text)


def pad_to_width(text: str, target_width: int) -> str:
    """根据显示宽度填充字符串到指定宽度"""
    current_width = get_display_width(text)
    padding = target_width - current_width
    return text + " " * max(0, padding)


@non_llm_handler
def handle_message(message: Message):
    logger.debug(
        "Received message: %s, chat_id=%d, from=%s",
        message.text,
        message.chat.id,
        message.from_user.id,
    )
    # 这里可以添加处理消息的逻辑
    store.add_message(
        ChatMessage(
            chat_id=message.chat.id,
            message_id=message.id,
            content=message.text or "",
            user_id=message.from_user.id,
            user_name=message.from_user.full_name,
            timestamp=datetime.fromtimestamp(message.date, tz=timezone.utc),
        )
    )


@non_llm_handler
def summary_command(message: Message, bot: TeleBot):
    """生成消息摘要。示例：/summary today; /summary 2d"""
    text_parts = message.text.split(maxsplit=1)
    if len(text_parts) < 2:
        date = "today"
    else:
        date = text_parts[1].strip()
    since, now = parse_date(date, settings.timezone)
    messages = store.get_messages_since(message.chat.id, since)
    messages_text = "\n".join(
        f"{msg.timestamp.isoformat()} - @{msg.user_name}: {msg.content}"
        for msg in messages
    )
    if not messages_text:
        bot.reply_to(message, "没有找到指定时间范围内的历史消息。")
        return
    new_message = bot.reply_to(message, "正在生成摘要，请稍候...")
    response = settings.openai_client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "user", "content": PROMPT.format(messages=messages_text)},
        ],
    )
    reply_text = f"""*👇 前情提要 👇 \\({since.strftime("%Y/%m/%d %H:%M")} \\- {now.strftime("%Y/%m/%d %H:%M")}\\)*

{telegramify_markdown.markdownify(response.choices[0].message.content)}
"""
    logger.debug("Generated summary:\n%s", reply_text)
    bot.edit_message_text(
        chat_id=new_message.chat.id,
        message_id=new_message.message_id,
        text=reply_text,
        parse_mode="MarkdownV2",
    )


@non_llm_handler
def stats_command(message: Message, bot: TeleBot):
    """获取群组消息统计信息"""
    stats = store.get_stats(message.chat.id)
    if not stats:
        bot.reply_to(message, "没有找到任何统计信息。")
        return

    # 计算数字部分的最大宽度
    max_count_width = max(len(str(entry.message_count)) for entry in stats)
    stats_text = "\n".join(
        f"{entry.message_count:>{max_count_width}} messages - {entry.date}"
        for entry in stats
    )

    text_args = shlex.split(message.text)
    if len(text_args) > 1 and text_args[1].isdigit():
        limit = int(text_args[1])
    else:
        limit = 10
    user_stats = store.get_user_stats(message.chat.id, limit=limit)
    if user_stats:
        # 计算用户消息数量的最大宽度
        max_user_count_width = max(
            len(str(entry.message_count)) for entry in user_stats
        )
        user_text = "\n".join(
            f"{entry.message_count:>{max_user_count_width}} messages - {entry.user_name}"
            for entry in user_stats
        )
    else:
        user_text = ""

    bot.reply_to(
        message,
        (
            f"📊 群组消息统计信息:\n```\n{stats_text}\n```\n👤 用户消息统计信息:\n```\n{user_text}\n```"
        ),
        parse_mode="MarkdownV2",
    )


@non_llm_handler
def search_command(message: Message, bot: TeleBot):
    """搜索群组消息（示例：/search 关键词 [N]）"""
    text_parts = shlex.split(message.text)
    if len(text_parts) < 2:
        bot.reply_to(message, "请提供要搜索的关键词。")
        return
    keyword = text_parts[1].strip()
    if len(text_parts) > 2 and text_parts[2].isdigit():
        limit = int(text_parts[2])
    else:
        limit = 10
    messages = store.search_messages(message.chat.id, keyword, limit=limit)
    if not messages:
        bot.reply_to(message, "没有找到匹配的消息。")
        return
    chat_id = str(message.chat.id)
    if chat_id.startswith("-100"):
        chat_id = chat_id[4:]
    items = []
    for msg in messages:
        link = f"https://t.me/c/{chat_id}/{msg.message_id}"
        items.append(f"{link}\n```\n{msg.user_name}: {msg.content}\n```")
    message_text = telegramify_markdown.markdownify("\n".join(items))
    bot.reply_to(
        message,
        f"🔍 *搜索结果\\(只显示前 {limit} 个\\):*\n{message_text}",
        parse_mode="MarkdownV2",
    )


load_priority = 5
if settings.openai_api_key:

    def register(bot: TeleBot):
        """注册命令处理器"""
        bot.register_message_handler(
            summary_command, commands=["summary"], pass_bot=True
        )
        bot.register_message_handler(stats_command, commands=["stats"], pass_bot=True)
        bot.register_message_handler(search_command, commands=["search"], pass_bot=True)
        bot.register_message_handler(
            handle_message, func=partial(filter_message, bot=bot)
        )
