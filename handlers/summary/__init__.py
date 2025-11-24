from __future__ import annotations

import logging
import random
import zoneinfo
from datetime import datetime, timezone
from functools import partial
import shlex
import threading

import telegramify_markdown
from telebot import TeleBot
from telebot.types import Message
from wcwidth import wcswidth

from config import settings
from handlers._utils import non_llm_handler

from .messages import ChatMessage, MessageStore
from .utils import PROMPT, filter_message, parse_date, contains_non_ascii
from datetime import timedelta

from rich import print

logger = logging.getLogger("bot")
store = MessageStore("data/messages.db")

# 从环境变量获取提肛群组 ID
TIGONG_CHAT_ID = settings.tigong_chat_id


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
def handle_message(message: Message, bot: TeleBot):
    logger.debug(
        "Received message: %s, chat_id=%d, from=%s",
        message.text,
        message.chat.id,
        message.from_user.id,
    )

    # 检测中文消息并删除(仅在特定时间和群组)
    # 只在提肛群组且每天北京时间 15:00-16:00 之间删除
    if (
        TIGONG_CHAT_ID
        and message.chat.id == TIGONG_CHAT_ID
        and message.text
        and contains_non_ascii(message.text)
    ):
        beijing_tz = zoneinfo.ZoneInfo("Asia/Shanghai")
        current_time = datetime.now(tz=beijing_tz)
        current_hour = current_time.hour

        # 检查是否在北京时间 15:00-16:00 之间
        if 15 <= current_hour < 16:
            try:
                bot.delete_message(message.chat.id, message.message_id)
                bot.send_message(
                    message.chat.id,
                    f"已删除 @{message.from_user.username or message.from_user.full_name} 的中文消息",
                )
                logger.info(
                    "Deleted Chinese message from user %s in chat %d at %s",
                    message.from_user.full_name,
                    message.chat.id,
                    current_time.strftime("%H:%M:%S"),
                )
                return
            except Exception as e:
                logger.error("Failed to delete message: %s", e)

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

    # 检测100整数倍消息提醒
    if TIGONG_CHAT_ID and message.chat.id == TIGONG_CHAT_ID:
        beijing_tz = zoneinfo.ZoneInfo("Asia/Shanghai")
        today = datetime.now(tz=beijing_tz).strftime("%Y-%m-%d")
        count = store.get_today_message_count(message.chat.id, today)

        if count > 0 and count % 100 == 0:
            bot.send_message(
                message.chat.id,
                f"🎉 今日第 {count} 条消息！提肛小助手提醒：该做提肛运动啦！",
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
        limit = 30
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

    return_message = f"📊 群组消息统计信息:\n```\n{stats_text}\n```\n👤 用户消息统计信息:\n```\n{user_text}\n```\\-\\-\\-\n"

    bot.reply_to(
        message,
        return_message,
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


TIGONG_MESSAGES = [
    "💪 提肛时间到！记得做提肛运动哦~",
    "🏋️ 该做提肛运动了！坚持就是胜利！",
    "⏰ 提肛小助手提醒：现在是提肛时间！",
    "🎯 提肛运动打卡时间！加油！",
    "💯 定时提醒：做做提肛运动，健康生活每一天！",
    "🌟 提肛运动不能停！现在开始吧！",
    "✨ 提肛小助手：该运动啦！",
]


@non_llm_handler
def alert_me_command(message: Message, bot: TeleBot):
    """加入提肛提醒队列"""
    if TIGONG_CHAT_ID and message.chat.id == TIGONG_CHAT_ID:
        beijing_tz = zoneinfo.ZoneInfo("Asia/Shanghai")
        today = datetime.now(tz=beijing_tz).strftime("%Y-%m-%d")
        username = message.from_user.username or ""
        store.add_tigong_alert_user(
            message.chat.id,
            message.from_user.id,
            message.from_user.full_name,
            username,
            today,
        )
        bot.reply_to(
            message,
            "✅ 已加入今日提肛提醒队列！每次提醒都会 @ 你，记得 /confirm 打卡哦！",
        )
    else:
        bot.reply_to(message, "此命令仅在指定群组中可用。")


@non_llm_handler
def confirm_command(message: Message, bot: TeleBot):
    """确认完成今日提肛"""
    if TIGONG_CHAT_ID and message.chat.id == TIGONG_CHAT_ID:
        beijing_tz = zoneinfo.ZoneInfo("Asia/Shanghai")
        today = datetime.now(tz=beijing_tz).strftime("%Y-%m-%d")
        success = store.confirm_tigong_alert(
            message.chat.id, message.from_user.id, today
        )
        if success:
            bot.reply_to(message, "✅ 今日提肛已打卡！明天继续加油！")
        else:
            bot.reply_to(message, "你还没有加入提醒队列，请先使用 /alert_me 加入。")
    else:
        bot.reply_to(message, "此命令仅在指定群组中可用。")


@non_llm_handler
def standup_command(message: Message, bot: TeleBot):
    """手动发送提肛提醒消息"""
    if TIGONG_CHAT_ID and message.chat.id == TIGONG_CHAT_ID:
        try:
            send_random_tigong_reminder(bot)
            # 不需要reply，因为send_random_tigong_reminder已经发送消息了
        except Exception as e:
            logger.error("Error in standup_command: %s", e)
            bot.reply_to(message, "❌ 发送提醒失败，请稍后重试。")
    else:
        bot.reply_to(message, "此命令仅在指定群组中可用。")


def send_random_tigong_reminder(bot: TeleBot):
    """发送随机提肛提醒消息"""
    try:
        beijing_tz = zoneinfo.ZoneInfo("Asia/Shanghai")
        today = datetime.now(tz=beijing_tz).strftime("%Y-%m-%d")

        # 获取未确认用户列表
        unconfirmed_users = store.get_unconfirmed_users(TIGONG_CHAT_ID, today)

        message = random.choice(TIGONG_MESSAGES)

        # 如果有未确认用户，@他们
        if unconfirmed_users:
            message += "\n\n"
            mentions = []

            for user in unconfirmed_users:
                # 使用 username 或者 text mention
                username = user.get("username", "")
                if username:
                    mentions.append(f"@{username}")
                else:
                    # 如果没有 username，使用名字（但不能点击）
                    mentions.append(user["user_name"])

            message += " ".join(mentions) + " 记得打卡哦！"

        # 发送消息
        bot.send_message(TIGONG_CHAT_ID, message)

        logger.info(
            "Sent tigong reminder to chat %d with %d mentions",
            TIGONG_CHAT_ID,
            len(unconfirmed_users),
        )
    except Exception as e:
        logger.error("Failed to send tigong reminder: %s", e, exc_info=True)
        raise


def schedule_tigong_reminders(bot: TeleBot):
    """安排提肛提醒任务：每天北京时间8:00-19:00，每2小时发送一次"""

    def run_scheduler():
        import time

        beijing_tz = zoneinfo.ZoneInfo("Asia/Shanghai")
        while True:
            now = datetime.now(tz=beijing_tz)
            current_hour = now.hour

            # 检查是否在北京时间8:00-19:00之间
            if 8 <= current_hour < 19:
                # 检查是否在偶数小时的整点（8, 10, 12, 14, 16, 18）
                if current_hour % 2 == 0 and now.minute == 0 and now.second < 30:
                    send_random_tigong_reminder(bot)
                    time.sleep(30)  # 避免在同一分钟内重复发送

            # 每30秒检查一次
            time.sleep(30)

    # 在后台线程中运行调度器
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("Tigong reminder scheduler started")


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
            standup_command, commands=["standup"], pass_bot=True
        )
        bot.register_message_handler(
            alert_me_command, commands=["alert_me"], pass_bot=True
        )
        bot.register_message_handler(
            confirm_command, commands=["confirm"], pass_bot=True
        )
        bot.register_message_handler(
            handle_message, func=partial(filter_message, bot=bot, check_chinese=True), pass_bot=True
        )

        # 启动提肛提醒定时任务
        schedule_tigong_reminders(bot)
