import re
import zoneinfo
from datetime import datetime, timedelta

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
    return not text.isascii()


def filter_message(message: Message, bot: TeleBot, check_chinese: bool = False) -> bool:
    """过滤消息，排除非文本消息和命令消息
    
    Args:
        message: 消息对象
        bot: Bot 实例
        check_chinese: 是否允许检查中文消息（即不过滤命令）
    """
    if not message.text:
        return False
    if not message.from_user:
        return False
    if message.from_user.id == bot.get_me().id:
        return False
    # 如果需要检查中文，则不过滤命令消息（让 handle_message 处理）
    if not check_chinese and message.text.startswith("/"):
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
