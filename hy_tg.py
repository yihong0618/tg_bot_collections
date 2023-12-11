import argparse
import random
import os
import gc
import subprocess
from telebot import TeleBot  # type: ignore
from telebot.types import Message  # type: ignore

from prettymapp.geo import get_aoi
from prettymapp.osm import get_osm_geometries
from prettymapp.plotting import Plot
from prettymapp.settings import STYLES

from matplotlib import figure

from PIL import Image
import numpy as np
import PIL
import io

PIL.Image.MAX_IMAGE_PIXELS = 933120000
file_in = "map.jpg"
file_out = "map_out.jpg"


# monkey patch for Plot thanks @higuoxing https://github.com/higuoxing
def __post_init__(self):
    (
        self.xmin,
        self.ymin,
        self.xmax,
        self.ymax,
    ) = self.aoi_bounds
    # take from aoi geometry bounds, otherwise probelematic if unequal geometry distribution over plot.
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


Plot.__post_init__ = __post_init__


def sizeof_image(image):
    with io.BytesIO() as buff:
        image.save(buff, format="JPEG", quality=95)
        return buff.tell()


def compress_image(input_path, output_path, target_size):
    quality = 95
    factor = 1.0
    with Image.open(input_path) as img:
        target_bytes = 10 * 1024 * 1024

        while sizeof_image(img) > target_bytes:
            factor -= 0.05
            width, height = img.size
            img = img.resize(
                (int(width * factor), int(height * factor)),
                PIL.Image.Resampling.LANCZOS,
            )
            if sizeof_image(img) <= target_bytes:
                img.save(output_path, format="JPEG", quality=quality)
                return


def draw_pretty_map(location, file_name, style):
    aoi = get_aoi(address=location, radius=1100, rectangular=True)
    df = get_osm_geometries(aoi=aoi)
    fig = Plot(df=df, aoi_bounds=aoi.bounds, draw_settings=STYLES[style]).plot_all()
    fig.savefig(file_name)
    compress_image(file_in, file_out, 9)  # telegram tog need png less than 10MB


def main():
    # Init args
    parser = argparse.ArgumentParser()
    parser.add_argument("tg_token", help="tg token")
    options = parser.parse_args()
    print("Arg parse done.")

    # Init bot
    bot = TeleBot(options.tg_token)
    bot_name = bot.get_me().username
    bot.delete_my_commands(scope=None, language_code=None)
    print("Bot init done.")

    @bot.message_handler(regexp="^github:")
    def github_poster_handler(message: Message):
        reply_message = bot.reply_to(message, "Generating poster please wait:")
        m = message.text.strip()[7:]
        message_list = m.split(",")
        name = message_list[0].strip()
        cmd_list = ["github_poster", "github", "--github_user_name", name, "--me", name]
        if len(message_list) > 1:
            years = message_list[1]
            cmd_list.append("--year")
            cmd_list.append(years.strip())
        r = subprocess.check_output(cmd_list).decode("utf-8")
        if r.find("done") > 0:
            try:
                # TODO windows path
                r = subprocess.check_output(
                    ["cairosvg", "OUT_FOLDER/github.svg", "-o", f"github_{name}.png"]
                ).decode("utf-8")
                with open(f"github_{name}.png", "rb") as photo:
                    bot.send_photo(
                        message.chat.id, photo, reply_to_message_id=message.message_id
                    )
            except Exception as e:
                print(e)
                bot.reply_to(message, "Something wrong please check")
        bot.delete_message(reply_message.chat.id, reply_message.message_id)

    @bot.message_handler(regexp="^map:")
    def map_handler(message: Message):
        reply_message = bot.reply_to(
            message, "Generating pretty map may take some time please wait:"
        )
        m = message.text.strip()[4:]
        location = m.strip()
        styles_list = list(STYLES.keys())
        style = random.choice(styles_list)
        try:
            # TODO why this memory leak?
            draw_pretty_map(location, file_in, style)
            # tg can only send image less than 10MB
            with open(file_out, "rb") as photo:
                bot.send_photo(
                    message.chat.id, photo, reply_to_message_id=message.message_id
                )

        except Exception as e:
            bot.reply_to(message, "Something wrong please check")
            print(str(e))
        bot.delete_message(reply_message.chat.id, reply_message.message_id)
        # we need this, fuck it
        gc.collect()

    # Start bot
    print("Starting tg collections bot.")
    bot.infinity_polling()


if __name__ == "__main__":
    main()
