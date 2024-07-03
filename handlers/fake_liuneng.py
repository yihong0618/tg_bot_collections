import random
from PIL import Image, ImageDraw, ImageFont
from os import listdir
from telebot import TeleBot
from telebot.types import Message
import re

from . import *


def split_lines(text, max_length=18):
    def split_line(line):
        punctuation = r"[,.!?;，。！？；]"
        parts = re.split(f"({punctuation})", line)

        result = []
        current = ""

        for part in parts:
            if len(current) + len(part) <= max_length:
                current += part
            else:
                if current:
                    result.append(current.strip())

                while len(part) > max_length:
                    result.append(part[:max_length])
                    part = part[max_length:]

                current = part

        if current:
            result.append(current.strip())

        return result

    lines = text.split("\n")
    final_result = []
    for line in lines:
        final_result.extend(split_line(line))

    return final_result


def extract_prompt(message: str, bot_name: str) -> str:
    """
    This function filters messages for prompts.

    Returns:
      str: If it is not a prompt, return None. Otherwise, return the trimmed prefix of the actual prompt.
    """
    # remove '@bot_name' as it is considered part of the command when in a group chat.
    message = re.sub(re.escape(f"@{bot_name}"), "", message).strip()
    # add a whitespace after the first colon as we separate the prompt from the command by the first whitespace.
    message = re.sub(":", ": ", message, count=1).strip()
    try:
        left, message = message.split(maxsplit=1)
    except ValueError:
        return ""
    if ":" not in left:
        # the replacement happens in the right part, restore it.
        message = message.replace(": ", ":", 1)
    return message.strip()


class ImageRenderer:
    def __init__(self):
        self.canvas_width = 512
        self.quotes = [
            "我敬佩两种人\n年轻时陪男人过苦日子的女人\n富裕时陪女人过好日子的男人",
            "人生就像一杯茶\n不会苦一辈子\n但总会苦一阵子",
            "不要总拿自己跟别人比\n你羡慕别人瘦\n别人还羡慕你肠胃好\n你羡慕别人有钱\n别人还羡慕没人找你借钱",
            "彪悍的人生不需要解释\n只要你按时达到目的地\n很少有人在乎你开的是奔驰还是拖拉机",
            "如果你不够优秀\n人脉是不值钱的\n它不是追求来的\n而是吸引来的\n只有等价的交换\n才能得到合理的帮助\n虽然听起来很冷\n但这是事实",
            "喜欢在你背后说三道四\n捏造故事的人\n无非就三个原因\n没达到你的层次\n你有的东西他没有\n模仿你的生活方式未遂",
            "做一个特别简单的人\n好相处就处\n不好相处就不处\n不要一厢情愿去迎合别人\n你努力合群的样子并不漂亮\n不必对每个人好\n他们又不给你打钱",
        ]

    def render_image(self, image_path, text):
        image = Image.open(image_path)
        scale_factor = self.canvas_width / image.width
        scaled_height = int(image.height * scale_factor)
        line_height = 50
        font_size = 20
        image_line_height = int(line_height / scale_factor)
        lines = split_lines(text)
        canvas_height = scaled_height
        if len(lines) > 1:
            canvas_height += (len(lines) - 1) * line_height

        canvas = Image.new("RGB", (self.canvas_width, canvas_height))
        canvas.paste(image.resize((self.canvas_width, scaled_height)))

        draw = ImageDraw.Draw(canvas)
        # font = ImageFont.load_default()
        font = ImageFont.truetype("wqy-microhei.ttc", font_size)

        for i, line in enumerate(lines):
            if i > 0:
                bottom_strip = image.crop(
                    (0, image.height - image_line_height, image.width, image.height)
                )
                canvas.paste(
                    bottom_strip.resize((self.canvas_width, line_height)),
                    (0, scaled_height + (i - 1) * line_height),
                )

            y = scaled_height + i * line_height - (line_height - font_size) // 2
            draw.text(
                (self.canvas_width // 2, y),
                line,
                fill="white",
                font=font,
                anchor="mm",
                stroke_width=2,
                stroke_fill="black",
            )

        return canvas

    def save_image(self, image, filename="fake.jpg"):
        image.save(filename)

    def get_random_quote(self):
        return random.choice(self.quotes)


def fake_handler(message: Message, bot: TeleBot) -> None:
    """ignore"""
    who = "LiuNeng"
    bot.reply_to(message, f"Generating {who}'s fake image")
    m = message.text.strip()
    prompt = m.strip()
    prompt = extract_prompt(message.text, bot.get_me().username)
    # Usage
    renderer = ImageRenderer()
    heros_list = listdir("handlers/heros")
    image_path = f"handlers/heros/{random.choice(heros_list)}"
    if prompt:
        text = prompt
    else:
        text = renderer.get_random_quote()
    rendered_image = renderer.render_image(image_path, text)
    renderer.save_image(rendered_image)
    with open("fake.jpg", "rb") as f:
        bot.send_photo(
            message.chat.id,
            f,
            reply_to_message_id=message.message_id,
            caption="Generated image",
        )


def fake_photo_handler(message: Message, bot: TeleBot) -> None:
    """ignore"""
    s = message.caption
    s = s.replace("/fake", "").strip()
    s = s.replace("fake:", "").strip()
    prompt = s.strip()
    bot.reply_to(message, f"Generating LiuNeng's fake image")
    # get the high quaility picture.
    max_size_photo = max(message.photo, key=lambda p: p.file_size)
    file_path = bot.get_file(max_size_photo.file_id).file_path
    downloaded_file = bot.download_file(file_path)
    downloaded_file = bot.download_file(file_path)
    with open("fake.jpg", "wb") as temp_file:
        temp_file.write(downloaded_file)
    renderer = ImageRenderer()
    rendered_image = renderer.render_image("fake.jpg", prompt)
    renderer.save_image(rendered_image)
    with open("fake.jpg", "rb") as f:
        bot.send_photo(
            message.chat.id,
            f,
            reply_to_message_id=message.message_id,
            caption="Generated image",
        )


def register(bot: TeleBot) -> None:
    bot.register_message_handler(fake_handler, commands=["fake"], pass_bot=True)
    bot.register_message_handler(fake_handler, regexp="^fake:", pass_bot=True)
    bot.register_message_handler(
        fake_photo_handler,
        content_types=["photo"],
        func=lambda m: m.caption and m.caption.startswith(("fake:", "/fake")),
        pass_bot=True,
    )
