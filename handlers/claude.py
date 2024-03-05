from os import environ
from pathlib import Path
import re

from anthropic import Anthropic, APITimeoutError
from telebot import TeleBot
from telebot.types import Message

ANTHROPIC_API_KEY = environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = "claude-3-sonnet-20240229"  # change model here you can use claude-3-opus-20240229 but for now its slow

client = Anthropic(api_key=ANTHROPIC_API_KEY, timeout=20)

# Global history cache
claude_player_dict = {}


#### Utils for claude ####
# Note this code copy from https://github.com/yym68686/md2tgmd/blob/main/src/md2tgmd.py
# great thanks
def find_all_index(str, pattern):
    index_list = [0]
    for match in re.finditer(pattern, str, re.MULTILINE):
        if match.group(1) != None:
            start = match.start(1)
            end = match.end(1)
            index_list += [start, end]
    index_list.append(len(str))
    return index_list


def replace_all(text, pattern, function):
    poslist = [0]
    strlist = []
    originstr = []
    poslist = find_all_index(text, pattern)
    for i in range(1, len(poslist[:-1]), 2):
        start, end = poslist[i : i + 2]
        strlist.append(function(text[start:end]))
    for i in range(0, len(poslist), 2):
        j, k = poslist[i : i + 2]
        originstr.append(text[j:k])
    if len(strlist) < len(originstr):
        strlist.append("")
    else:
        originstr.append("")
    new_list = [item for pair in zip(originstr, strlist) for item in pair]
    return "".join(new_list)


def escapeshape(text):
    return "▎*" + text.split()[1] + "*"


def escapeminus(text):
    return "\\" + text


def escapebackquote(text):
    return r"\`\`"


def escapeplus(text):
    return "\\" + text


def escape(text, flag=0):
    # In all other places characters
    # _ * [ ] ( ) ~ ` > # + - = | { } . !
    # must be escaped with the preceding character '\'.
    text = re.sub(r"\\\[", "@->@", text)
    text = re.sub(r"\\\]", "@<-@", text)
    text = re.sub(r"\\\(", "@-->@", text)
    text = re.sub(r"\\\)", "@<--@", text)
    if flag:
        text = re.sub(r"\\\\", "@@@", text)
    text = re.sub(r"\\", r"\\\\", text)
    if flag:
        text = re.sub(r"\@{3}", r"\\\\", text)
    text = re.sub(r"_", "\_", text)
    text = re.sub(r"\*{2}(.*?)\*{2}", "@@@\\1@@@", text)
    text = re.sub(r"\n{1,2}\*\s", "\n\n• ", text)
    text = re.sub(r"\*", "\*", text)
    text = re.sub(r"\@{3}(.*?)\@{3}", "*\\1*", text)
    text = re.sub(r"\!?\[(.*?)\]\((.*?)\)", "@@@\\1@@@^^^\\2^^^", text)
    text = re.sub(r"\[", "\[", text)
    text = re.sub(r"\]", "\]", text)
    text = re.sub(r"\(", "\(", text)
    text = re.sub(r"\)", "\)", text)
    text = re.sub(r"\@\-\>\@", "\[", text)
    text = re.sub(r"\@\<\-\@", "\]", text)
    text = re.sub(r"\@\-\-\>\@", "\(", text)
    text = re.sub(r"\@\<\-\-\@", "\)", text)
    text = re.sub(r"\@{3}(.*?)\@{3}\^{3}(.*?)\^{3}", "[\\1](\\2)", text)
    text = re.sub(r"~", "\~", text)
    text = re.sub(r">", "\>", text)
    text = replace_all(text, r"(^#+\s.+?$)|```[\D\d\s]+?```", escapeshape)
    text = re.sub(r"#", "\#", text)
    text = replace_all(
        text, r"(\+)|\n[\s]*-\s|```[\D\d\s]+?```|`[\D\d\s]*?`", escapeplus
    )
    text = re.sub(r"\n{1,2}(\s*)-\s", "\n\n\\1• ", text)
    text = re.sub(r"\n{1,2}(\s*\d{1,2}\.\s)", "\n\n\\1", text)
    text = replace_all(
        text, r"(-)|\n[\s]*-\s|```[\D\d\s]+?```|`[\D\d\s]*?`", escapeminus
    )
    text = re.sub(r"```([\D\d\s]+?)```", "@@@\\1@@@", text)
    text = replace_all(text, r"(``)", escapebackquote)
    text = re.sub(r"\@{3}([\D\d\s]+?)\@{3}", "```\\1```", text)
    text = re.sub(r"=", "\=", text)
    text = re.sub(r"\|", "\|", text)
    text = re.sub(r"{", "\{", text)
    text = re.sub(r"}", "\}", text)
    text = re.sub(r"\.", "\.", text)
    text = re.sub(r"!", "\!", text)
    return text


def claude_handler(message: Message, bot: TeleBot) -> None:
    """claude : /claude <question>"""
    reply_message = bot.reply_to(
        message,
        "Generating Anthropic claude answer please wait, note, will only keep the last five messages:",
    )
    m = message.text.strip()
    player_message = []
    # restart will lose all TODO
    if str(message.from_user.id) not in claude_player_dict:
        claude_player_dict[str(message.from_user.id)] = (
            player_message  # for the imuutable list
        )
    else:
        player_message = claude_player_dict[str(message.from_user.id)]

    player_message.append({"role": "user", "content": m})
    # keep the last 5, every has two ask and answer.
    if len(player_message) > 10:
        player_message = player_message[2:]

    claude_reply_text = ""
    try:
        if len(player_message) > 2:
            if player_message[-1]["role"] == player_message[-2]["role"]:
                # tricky
                player_message.pop()
        r = client.messages.create(
            max_tokens=1024, messages=player_message, model=ANTHROPIC_MODEL
        )
        if not r.content:
            claude_reply_text = "Claude did not answer."
            player_message.pop()
        else:
            claude_reply_text = r.content[0].text
            player_message.append(
                {
                    "role": r.role,
                    "content": r.content,
                }
            )

    except APITimeoutError:
        bot.reply_to(
            message,
            "claude answer:\n" + "claude answer timeout",
            parse_mode="MarkdownV2",
        )
        # pop my user
        player_message.pop()
        return

    try:
        bot.reply_to(
            message,
            "claude answer:\n" + escape(claude_reply_text),
            parse_mode="MarkdownV2",
        )
        return
    except:
        print("wrong markdown format")
        bot.reply_to(
            message,
            "claude answer:\n\n" + claude_reply_text,
        )
        return
    finally:
        bot.delete_message(reply_message.chat.id, reply_message.message_id)
        return

def claude_photo_handler(message: Message, bot: TeleBot) -> None:
    s = message.caption
    reply_message = bot.reply_to(
        message,
        "Generating claude vision answer please wait.",
    )
    prompt = s.strip()
    # get the high quaility picture.
    max_size_photo = max(message.photo, key=lambda p: p.file_size)
    file_path = bot.get_file(max_size_photo.file_id).file_path
    downloaded_file = bot.download_file(file_path)
    with open("claude_temp.jpg", "wb") as temp_file:
        temp_file.write(downloaded_file)

    try:
        r = client.messages.create(
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": Path("claude_temp.jpg"),
                            },
                        },
                    ],
                },
            ],
            model="claude-3-opus-20240229",
        )
        bot.reply_to(message, "Claude vision answer:\n" + r.content[0].text)
    except Exception as e:
        print(e)
        bot.reply_to(
            message,
            "Claude vision answer:\n" + "claude vision answer wrong",
            parse_mode="MarkdownV2",
        )
    finally:
        bot.delete_message(reply_message.chat.id, reply_message.message_id)



def register(bot: TeleBot) -> None:
    bot.register_message_handler(claude_handler, commands=["claude"], pass_bot=True)
    bot.register_message_handler(claude_handler, regexp="^claude:", pass_bot=True)
    bot.register_message_handler(
        claude_photo_handler,
        content_types=["photo"],
        func=lambda m: m.caption and m.caption.startswith(("claude:", "/claude")),
        pass_bot=True,
    )
