import re
import zoneinfo
from datetime import datetime, timedelta
from urllib.parse import unquote

from telebot import TeleBot
from telebot.types import Message

PROMPT = """\
请将下面的聊天记录进行总结，包含讨论了哪些话题，有哪些亮点发言和主要观点。
引用用户名请加粗。直接返回内容即可，不要包含引导词和标题。
--- Messages Start ---
{messages}
--- Messages End ---
"""


def contains_non_ascii(text: str) -> bool:
    # 首先检查原始文本
    if not text.isascii():
        return True
    # 然后检查 URL decode 后的文本（处理 %XX 编码的中文）
    try:
        decoded = unquote(text)
        if not decoded.isascii():
            return True
    except Exception:
        pass
    return False


def filter_message(message: Message, bot: TeleBot) -> bool:
    """过滤消息，排除非文本消息和命令消息"""
    if not message.text:
        return False
    if not message.from_user:
        return False
    if message.from_user.id == bot.get_me().id:
        return False
    if message.text.startswith("/"):
        return False
    return True
date_regex = re.compile(r"^(\d+)([dhm])$")


def parse_date(date_str: str, locale: str) -> tuple[datetime, datetime]:
    date_str = date_str.strip().lower()
    now = datetime.now(tz=zoneinfo.ZoneInfo(locale))
    if date_str == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0), now
    elif m := date_regex.match(date_str):
        number = int(m.group(1))
        unit = m.group(2)
        match unit:
            case "d":
                return now - timedelta(days=number), now
            case "h":
                return now - timedelta(hours=number), now
            case "m":
                return now - timedelta(minutes=number), now
    raise ValueError(f"Unsupported date format: {date_str}")
