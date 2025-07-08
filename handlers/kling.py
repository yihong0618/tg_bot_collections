import re
from os import environ

import requests
from expiringdict import ExpiringDict
from kling import ImageGen, VideoGen
from telebot import TeleBot
from telebot.types import InputMediaPhoto, Message

from ._utils import logger

KLING_COOKIE = environ.get("KLING_COOKIE")
pngs_link_dict = ExpiringDict(max_len=100, max_age_seconds=60 * 10)


def kling_handler(message: Message, bot: TeleBot):
    """kling: /kling <address>"""
    bot.reply_to(
        message,
        "Generating pretty kling image may take some time please wait",
    )
    m = message.text.strip()
    prompt = m.strip()
    links = None
    try:
        i = ImageGen(KLING_COOKIE)
        links = i.get_images(prompt)
        # set the dict
        try:
            pngs_link_dict[str(message.from_user.id)] = links
        except Exception as e:
            print(str(e))
    except Exception as e:
        print(str(e))
        bot.reply_to(message, "kling error maybe block the prompt")
        return
    photos_list = [InputMediaPhoto(i) for i in links]
    bot.send_media_group(
        message.chat.id,
        photos_list,
        reply_to_message_id=message.message_id,
        disable_notification=True,
    )


def kling_pro_handler(message: Message, bot: TeleBot):
    """kling: /kling <address>"""
    bot.reply_to(
        message,
        "Generating pretty kling video may take a long time about 2mins to 5mins please wait",
    )
    m = message.text.strip()
    prompt = m.strip()
    # drop all the spaces
    prompt = prompt.replace(" ", "")
    # find `图{number}` in prompt
    number = re.findall(r"图\d+", prompt)
    number = number[0] if number else None
    if number:
        number = int(number.replace("图", ""))
    v = VideoGen(KLING_COOKIE)
    video_links = None
    image_url = None
    if number and number <= 9 and pngs_link_dict.get(str(message.from_user.id)):
        if number - 1 <= len(pngs_link_dict.get(str(message.from_user.id))):
            image_url = pngs_link_dict.get(str(message.from_user.id))[number - 1]
            print(image_url)
    try:
        video_links = v.get_video(prompt, image_url=image_url)
    except Exception as e:
        print(str(e))
        bot.reply_to(message, "kling error maybe block the prompt")
        return
    if not video_links:
        bot.reply_to(message, "video not generate")
        return
    response = requests.get(video_links[0])
    if response.status_code != 200:
        bot.reply_to(message, "could not fetch the video")
    # save response to file
    with open("kling.mp4", "wb") as output_file:
        output_file.write(response.content)
    bot.send_video(
        message.chat.id,
        open("kling.mp4", "rb"),
        caption=prompt,
        reply_to_message_id=message.message_id,
    )


def kling_photo_handler(message: Message, bot: TeleBot) -> None:
    s = message.caption
    prompt = s.strip()
    # show something, make it more responsible
    # get the high quaility picture.
    max_size_photo = max(message.photo, key=lambda p: p.file_size)
    file_path = bot.get_file(max_size_photo.file_id).file_path
    downloaded_file = bot.download_file(file_path)
    bot.reply_to(
        message,
        "Generating pretty kling image using your photo may take some time please wait",
    )
    with open("kling.jpg", "wb") as temp_file:
        temp_file.write(downloaded_file)
    i = ImageGen(KLING_COOKIE)
    links = None
    try:
        links = i.get_images(prompt, "kling.jpg")
        # set the dict
        try:
            pngs_link_dict[str(message.from_user.id)] = links
        except Exception:
            logger.exception("Kling photo handler error")
    except Exception:
        logger.exception("Kling photo handler error")
        bot.reply_to(message, "kling error maybe block the prompt")
        return
    photos_list = [InputMediaPhoto(i) for i in links]
    bot.send_media_group(
        message.chat.id,
        photos_list,
        reply_to_message_id=message.message_id,
        disable_notification=True,
    )


if KLING_COOKIE:

    def register(bot: TeleBot) -> None:
        bot.register_message_handler(kling_handler, commands=["kling"], pass_bot=True)
        bot.register_message_handler(kling_handler, regexp="^kling:", pass_bot=True)
        # kling pro means video
        bot.register_message_handler(
            kling_pro_handler, commands=["kling_pro"], pass_bot=True
        )
