import argparse
import gc
import random
import shutil
import subprocess
import traceback
from tempfile import SpooledTemporaryFile

import numpy as np
import PIL
from matplotlib import figure
from PIL import Image
from prettymapp.geo import get_aoi
from prettymapp.osm import get_osm_geometries
from prettymapp.plotting import Plot as PrettyPlot
from prettymapp.settings import STYLES
from telebot import TeleBot  # type: ignore
from telebot.types import Message  # type: ignore

PIL.Image.MAX_IMAGE_PIXELS = 933120000
MAX_IN_MEMORY = 10 * 1024 * 1024  # 10MiB


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


def sizeof_image(image):
    with SpooledTemporaryFile(max_size=MAX_IN_MEMORY) as f:
        image.save(f, format="JPEG", quality=95)
        return f.tell()


def compress_image(input_image, target_size):
    quality = 95
    factor = 1.0
    output = SpooledTemporaryFile(max_size=MAX_IN_MEMORY)
    with Image.open(input_image) as img:
        while sizeof_image(img) > target_size:
            factor -= 0.05
            width, height = img.size
            img = img.resize(
                (int(width * factor), int(height * factor)),
                PIL.Image.Resampling.LANCZOS,
            )
        img.save(output, format="JPEG", quality=quality)
    output.seek(0)
    return output


def draw_pretty_map(location, style):
    aoi = get_aoi(address=location, radius=1100, rectangular=True)
    df = get_osm_geometries(aoi=aoi)
    fig = Plot(df=df, aoi_bounds=aoi.bounds, draw_settings=STYLES[style]).plot_all()
    with SpooledTemporaryFile(max_size=MAX_IN_MEMORY) as buffer:
        fig.savefig(buffer, format="jpeg")
        buffer.seek(0)
        return compress_image(
            buffer,
            10 * 1024 * 1024,  # telegram tog need png less than 10MB
        )


def main():
    # Init args
    parser = argparse.ArgumentParser()
    parser.add_argument("tg_token", help="tg token")
    options = parser.parse_args()
    print("Arg parse done.")

    # Init bot
    bot = TeleBot(options.tg_token)
    bot.set_my_commands(
        [
            {
                "command": "github",
                "description": "github poster: /github <github_user_name> [<start>-<end>]",
            },
            {
                "command": "map",
                "description": "pretty map: /map <address>",
            },
        ]
    )
    print("Bot init done.")

    @bot.message_handler(commands=["github"])
    @bot.message_handler(regexp="^github:")
    def github_poster_handler(message: Message):
        reply_message = bot.reply_to(message, "Generating poster please wait:")
        m = message.text.strip().split(maxsplit=1)[1].strip()
        message_list = m.split(",")
        name = message_list[0].strip()
        cmd_list = ["github_poster", "github", "--github_user_name", name, "--me", name]
        if len(message_list) > 1:
            years = message_list[1]
            cmd_list.append("--year")
            cmd_list.append(years.strip())
        r = subprocess.check_output(cmd_list).decode("utf-8")
        if "done" in r:
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

    @bot.message_handler(commands=["map"])
    @bot.message_handler(regexp="^map:")
    def map_handler(message: Message):
        reply_message = bot.reply_to(
            message, "Generating pretty map may take some time please wait:"
        )
        m = message.text.strip().split(maxsplit=1)[1].strip()
        location = m.strip()
        styles_list = list(STYLES.keys())
        style = random.choice(styles_list)
        try:
            # TODO why this memory leak?
            out_image = draw_pretty_map(location, style)
            # tg can only send image less than 10MB
            with open("map_out.jpg", "wb") as f:
                shutil.copyfileobj(out_image, f)
            out_image.seek(0)
            bot.send_photo(
                message.chat.id, out_image, reply_to_message_id=message.message_id
            )
            out_image.close()

        except Exception:
            traceback.print_exc()
            bot.reply_to(message, "Something wrong please check")
        bot.delete_message(reply_message.chat.id, reply_message.message_id)
        # we need this, fuck it
        gc.collect()

    # Start bot
    print("Starting tg collections bot.")
    bot.infinity_polling()


if __name__ == "__main__":
    main()
