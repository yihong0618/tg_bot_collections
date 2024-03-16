import gc
import shutil
import random
from tempfile import SpooledTemporaryFile

import numpy as np
import PIL
from matplotlib import figure
from PIL import Image
from prettymapp.geo import get_aoi
from prettymapp.osm import get_osm_geometries
from prettymapp.plotting import Plot as PrettyPlot
from prettymapp.settings import STYLES
from telebot import TeleBot
from telebot.types import Message

MAX_IN_MEMORY = 10 * 1024 * 1024  # 10MiB
PIL.Image.MAX_IMAGE_PIXELS = 933120000


class Plot(PrettyPlot):
    # memory leak fix for Plot. thanks @higuoxing https://github.com/higuoxing
    # refer to: https://www.mail-archive.com/matplotlib-users@lists.sourceforge.net/msg11809.html
    def __post_init__(self):
        (
            self.xmin,
            self.ymin,
            self.xmax,
            self.ymax,
        ) = self.aoi_bounds
        # take from aoi geometry bounds, otherwise problematic if unequal geometry distribution over plot.
        self.xmid = (self.xmin + self.xmax) / 2
        self.ymid = (self.ymin + self.ymax) / 2
        self.xdif = self.xmax - self.xmin
        self.ydif = self.ymax - self.ymin

        self.bg_buffer_x = (self.bg_buffer / 100) * self.xdif
        self.bg_buffer_y = (self.bg_buffer / 100) * self.ydif

        # self.fig, self.ax = subplots(
        #     1, 1, figsize=(12, 12), constrained_layout=True, dpi=1200
        # )
        self.fig = figure.Figure(figsize=(12, 12), constrained_layout=True, dpi=1200)
        self.ax = self.fig.subplots(1, 1)
        self.ax.set_aspect(1 / np.cos(self.ymid * np.pi / 180))

        self.ax.axis("off")
        self.ax.set_xlim(self.xmin - self.bg_buffer_x, self.xmax + self.bg_buffer_x)
        self.ax.set_ylim(self.ymin - self.bg_buffer_y, self.ymax + self.bg_buffer_y)


def sizeof_image(image):
    with SpooledTemporaryFile(max_size=MAX_IN_MEMORY) as f:
        image.save(f, format="JPEG", quality=95)
        return f.tell()


def compress_image(input_image, output_image, target_size):
    quality = 95
    factor = 1.0
    with Image.open(input_image) as img:
        while sizeof_image(img) > target_size:
            factor -= 0.05
            width, height = img.size
            img = img.resize(
                (int(width * factor), int(height * factor)),
                PIL.Image.Resampling.LANCZOS,
            )
        img.save(output_image, format="JPEG", quality=quality)
    output_image.seek(0)


def draw_pretty_map(location, style, output_file):
    aoi = get_aoi(address=location, radius=1100, rectangular=True)
    df = get_osm_geometries(aoi=aoi)
    fig = Plot(df=df, aoi_bounds=aoi.bounds, draw_settings=STYLES[style]).plot_all()
    with SpooledTemporaryFile(max_size=MAX_IN_MEMORY) as buffer:
        fig.savefig(buffer, format="jpeg")
        buffer.seek(0)
        compress_image(
            buffer,
            output_file,
            10 * 1024 * 1024,  # telegram tog need png less than 10MB
        )


def map_handler(message: Message, bot: TeleBot):
    """pretty map: /map <address>"""
    bot.reply_to(message, "Generating pretty map may take some time please wait:")
    m = message.text.strip()
    location = m.strip()
    styles_list = list(STYLES.keys())
    style = random.choice(styles_list)
    with SpooledTemporaryFile(max_size=MAX_IN_MEMORY) as out_image:
        try:
            draw_pretty_map(location, style, out_image)
            # tg can only send image less than 10MB
            with open("map_out.jpg", "wb") as f:  # for debug
                shutil.copyfileobj(out_image, f)
            out_image.seek(0)
            bot.send_photo(
                message.chat.id, out_image, reply_to_message_id=message.message_id
            )
        finally:
            gc.collect()


def map_location_handler(message: Message, bot: TeleBot):
    # TODO refactor the function
    location = "{0}, {1}".format(message.location.latitude, message.location.longitude)
    styles_list = list(STYLES.keys())
    style = random.choice(styles_list)
    try:
        with SpooledTemporaryFile(max_size=MAX_IN_MEMORY) as out_image:
            draw_pretty_map(location, style, out_image)
            # tg can only send image less than 10MB
            with open("map_out.jpg", "wb") as f:  # for debug
                shutil.copyfileobj(out_image, f)
            out_image.seek(0)
            bot.send_photo(
                message.chat.id, out_image, reply_to_message_id=message.message_id
            )

    finally:
        gc.collect()


def register(bot: TeleBot) -> None:
    bot.register_message_handler(map_handler, commands=["map"], pass_bot=True)
    bot.register_message_handler(map_handler, regexp="^map:", pass_bot=True)
    bot.register_message_handler(
        map_location_handler, content_types=["location", "venue"], pass_bot=True
    )
