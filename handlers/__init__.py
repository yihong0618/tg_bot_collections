from __future__ import annotations

import base64
import importlib
import logging
import re
from functools import update_wrapper
from mimetypes import guess_type
from pathlib import Path
from typing import Any, Callable, TypeVar

import requests
import telegramify_markdown
from expiringdict import ExpiringDict
from telebot import TeleBot
from telebot.types import BotCommand, Message
from telebot.util import smart_split
from telegramify_markdown.customize import markdown_symbol
from urlextract import URLExtract

markdown_symbol.head_level_1 = "📌"  # If you want, Customizing the head level 1 symbol
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol

T = TypeVar("T", bound=Callable)
logger = logging.getLogger("bot")

DEFAULT_LOAD_PRIORITY = 10

BOT_MESSAGE_LENGTH = 4000

REPLY_MESSAGE_CACHE = ExpiringDict(max_len=1000, max_age_seconds=600)


def bot_reply_first(message: Message, who: str, bot: TeleBot) -> Message:
    """Create the first reply message which make user feel the bot is working."""
    return bot.reply_to(
        message, f"*{who}* is _thinking_ \.\.\.", parse_mode="MarkdownV2"
    )


def bot_reply_markdown(
    reply_id: Message,
    who: str,
    text: str,
    bot: TeleBot,
    split_text: bool = True,
    disable_web_page_preview: bool = False,
) -> bool:
    """
    reply the Markdown by take care of the message length.
    it will fallback to plain text in case of any failure
    """
    try:
        cache_key = f"{reply_id.chat.id}_{reply_id.message_id}"
        if cache_key in REPLY_MESSAGE_CACHE and REPLY_MESSAGE_CACHE[cache_key] == text:
            logger.info(f"Skipping duplicate message for {cache_key}")
            return True
        REPLY_MESSAGE_CACHE[cache_key] = text
        if len(text.encode("utf-8")) <= BOT_MESSAGE_LENGTH or not split_text:
            bot.edit_message_text(
                f"*{who}*:\n{telegramify_markdown.convert(text)}",
                chat_id=reply_id.chat.id,
                message_id=reply_id.message_id,
                parse_mode="MarkdownV2",
                disable_web_page_preview=disable_web_page_preview,
            )
            return True

        # Need a split of message
        msgs = smart_split(text, BOT_MESSAGE_LENGTH)
        bot.edit_message_text(
            f"*{who}* \[1/{len(msgs)}\]:\n{telegramify_markdown.convert(msgs[0])}",
            chat_id=reply_id.chat.id,
            message_id=reply_id.message_id,
            parse_mode="MarkdownV2",
            disable_web_page_preview=disable_web_page_preview,
        )
        for i in range(1, len(msgs)):
            bot.reply_to(
                reply_id.reply_to_message,
                f"*{who}* \[{i + 1}/{len(msgs)}\\]:\n{telegramify_markdown.convert(msgs[i])}",
                parse_mode="MarkdownV2",
            )

        return True
    except Exception:
        logger.exception("Error in bot_reply_markdown")
        # logger.info(f"wrong markdown format: {text}")
        bot.edit_message_text(
            f"*{who}*:\n{text}",
            chat_id=reply_id.chat.id,
            message_id=reply_id.message_id,
            disable_web_page_preview=disable_web_page_preview,
        )
        return False


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


def remove_prompt_prefix(message: str) -> str:
    """
    Remove "/cmd" or "/cmd@bot_name" or "cmd:"
    """
    message += " "
    # Explanation of the regex pattern:
    # ^                        - Match the start of the string
    # (                        - Start of the group
    #   /                      - Literal forward slash
    #   [a-zA-Z]               - Any letter (start of the command)
    #   [a-zA-Z0-9_]*          - Any number of letters, digits, or underscores
    #   (@\w+)?                - Optionally match @ followed by one or more word characters (for bot name)
    #   \s                     - A single whitespace character (space or newline)
    # |                        - OR
    #   [a-zA-Z]               - Any letter (start of the command)
    #   [a-zA-Z0-9_]*          - Any number of letters, digits, or underscores
    #   :\s                    - Colon followed by a single whitespace character
    # )                        - End of the group
    pattern = r"^(/[a-zA-Z][a-zA-Z0-9_]*(@\w+)?\s|[a-zA-Z][a-zA-Z0-9_]*:\s)"

    return re.sub(pattern, "", message).strip()


def non_llm_handler(handler: T) -> T:
    handler.__is_llm_handler__ = False
    return handler


def wrap_handler(handler: T, bot: TeleBot) -> T:
    def wrapper(message: Message, *args: Any, **kwargs: Any) -> None:
        try:
            if getattr(handler, "__is_llm_handler__", True):
                m = ""

                if message.text is not None:
                    m = message.text = extract_prompt(
                        message.text, bot.get_me().username
                    )
                elif message.caption is not None:
                    m = message.caption = extract_prompt(
                        message.caption, bot.get_me().username
                    )
                elif message.location and message.location.latitude is not None:
                    # for location map handler just return
                    return handler(message, *args, **kwargs)
                if not m:
                    bot.reply_to(message, "Please provide info after start words.")
                    return
            return handler(message, *args, **kwargs)
        except Exception as e:
            logger.exception("Error in handler %s: %s", handler.__name__, e)
            # handle more here
            if str(e).find("RECITATION") > 0:
                bot.reply_to(message, "Your prompt `RECITATION` please check the log")
            else:
                bot.reply_to(message, "Something wrong, please check the log")

    return update_wrapper(wrapper, handler)


def load_handlers(bot: TeleBot, disable_commands: list[str]) -> None:
    # import all submodules
    modules_with_priority = []
    for name in list_available_commands():
        if name in disable_commands:
            continue
        module = importlib.import_module(f".{name}", __package__)
        load_priority = getattr(module, "load_priority", DEFAULT_LOAD_PRIORITY)
        modules_with_priority.append((module, name, load_priority))

    modules_with_priority.sort(key=lambda x: x[-1])
    for module, name, priority in modules_with_priority:
        if hasattr(module, "register"):
            logger.debug(f"Loading {name} handlers with priority {priority}.")
            module.register(bot)
    logger.info("Loading handlers done.")

    all_commands: list[BotCommand] = []
    for handler in bot.message_handlers:
        help_text = getattr(handler["function"], "__doc__", "")
        # tricky ignore the latest_handle_messages
        if help_text and help_text == "ignore":
            continue
        # Add pre-processing and error handling to all callbacks
        handler["function"] = wrap_handler(handler["function"], bot)
        for command in handler["filters"].get("commands", []):
            all_commands.append(BotCommand(command, help_text))

    if all_commands:
        bot.set_my_commands(all_commands)
        logger.info("Setting commands done.")


def list_available_commands() -> list[str]:
    commands = []
    this_path = Path(__file__).parent
    for child in this_path.iterdir():
        if child.name.startswith("_"):
            continue
        commands.append(child.stem)
    return commands


def extract_url_from_text(text: str) -> list[str]:
    extractor = URLExtract()
    urls = extractor.find_urls(text)
    return urls


def get_text_from_jina_reader(url: str):
    try:
        r = requests.get(f"https://r.jina.ai/{url}")
        return r.text
    except Exception as e:
        logger.exception("Error fetching text from Jina reader: %s", e)
        return None


def enrich_text_with_urls(text: str) -> str:
    urls = extract_url_from_text(text)
    for u in urls:
        try:
            url_text = get_text_from_jina_reader(u)
            url_text = f"\n```markdown\n{url_text}\n```\n"
            text = text.replace(u, url_text)
        except Exception:
            # just ignore the error
            pass

    return text


def image_to_data_uri(file_path):
    content_type = guess_type(file_path)[0]
    with open(file_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
        return f"data:{content_type};base64,{encoded_image}"


import json
import os

import markdown
from bs4 import BeautifulSoup


class TelegraphAPI:
    def __init__(
        self,
        access_token=None,
        short_name="tg_bot_collections",
        author_name="Telegram Bot Collections",
        author_url=None,
    ):
        self.access_token = (
            access_token
            if access_token
            else self._create_ph_account(short_name, author_name, author_url)
        )
        self.base_url = "https://api.telegra.ph"

        # Get account info on initialization
        account_info = self.get_account_info()
        self.short_name = account_info.get("short_name")
        self.author_name = account_info.get("author_name")
        self.author_url = account_info.get("author_url")

    def _create_ph_account(self, short_name, author_name, author_url):
        Store_Token = False
        TELEGRAPH_API_URL = "https://api.telegra.ph/createAccount"
        TOKEN_FILE = "token_key.json"

        # Try to load existing token information
        try:
            with open(TOKEN_FILE, "r") as f:
                tokens = json.load(f)
            if "TELEGRA_PH_TOKEN" in tokens and tokens["TELEGRA_PH_TOKEN"] != "example":
                return tokens["TELEGRA_PH_TOKEN"]
        except FileNotFoundError:
            tokens = {}

        # If no existing valid token in TOKEN_FILE, create a new account
        data = {
            "short_name": short_name,
            "author_name": author_name,
            "author_url": author_url,
        }

        # Make API request
        response = requests.post(TELEGRAPH_API_URL, data=data)
        response.raise_for_status()

        account = response.json()
        access_token = account["result"]["access_token"]

        # Update the token in the dictionary
        tokens["TELEGRA_PH_TOKEN"] = access_token

        # Store the updated tokens
        if Store_Token:
            with open(TOKEN_FILE, "w") as f:
                json.dump(tokens, f, indent=4)
        else:
            logger.info(
                f"Token not stored to file, but here is your token:\n{access_token}"
            )

        # Store it to the environment variable
        os.environ["TELEGRA_PH_TOKEN"] = access_token

        return access_token

    def create_page(
        self, title, content, author_name=None, author_url=None, return_content=False
    ):
        url = f"{self.base_url}/createPage"
        data = {
            "access_token": self.access_token,
            "title": title,
            "content": json.dumps(content),
            "return_content": return_content,
            "author_name": author_name if author_name else self.author_name,
            "author_url": author_url if author_url else self.author_url,
        }

        # Max 65,536 characters/64KB.
        if len(json.dumps(content)) > 65536:
            content = content[:64000]
            data["content"] = json.dumps(content)

        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
            response = response.json()
            page_url = response["result"]["url"]
            return page_url
        except:
            return "https://telegra.ph/api"

    def get_account_info(self):
        url = f'{self.base_url}/getAccountInfo?access_token={self.access_token}&fields=["short_name","author_name","author_url","auth_url"]'
        response = requests.get(url)

        if response.status_code == 200:
            return response.json()["result"]
        else:
            logger.info(f"Fail getting telegra.ph token info: {response.status_code}")
            return None

    def edit_page(
        self,
        path,
        title,
        content,
        author_name=None,
        author_url=None,
        return_content=False,
    ):
        url = f"{self.base_url}/editPage"
        data = {
            "access_token": self.access_token,
            "path": path,
            "title": title,
            "content": json.dumps(content),
            "return_content": return_content,
            "author_name": author_name if author_name else self.author_name,
            "author_url": author_url if author_url else self.author_url,
        }

        response = requests.post(url, data=data)
        response.raise_for_status()
        response = response.json()

        page_url = response["result"]["url"]
        return page_url

    def get_page(self, path):
        url = f"{self.base_url}/getPage/{path}?return_content=true"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()["result"]["content"]

    def create_page_md(
        self,
        title,
        markdown_text,
        author_name=None,
        author_url=None,
        return_content=False,
    ):
        content = self._md_to_dom(markdown_text)
        return self.create_page(title, content, author_name, author_url, return_content)

    def edit_page_md(
        self,
        path,
        title,
        markdown_text,
        author_name=None,
        author_url=None,
        return_content=False,
    ):
        content = self._md_to_dom(markdown_text)
        return self.edit_page(
            path, title, content, author_name, author_url, return_content
        )

    def authorize_browser(self):
        url = f'{self.base_url}/getAccountInfo?access_token={self.access_token}&fields=["auth_url"]'
        response = requests.get(url)
        response.raise_for_status()
        return response.json()["result"]["auth_url"]

    def _md_to_dom(self, markdown_text):
        html = markdown.markdown(
            markdown_text,
            extensions=["markdown.extensions.extra", "markdown.extensions.sane_lists"],
        )

        soup = BeautifulSoup(html, "html.parser")

        def parse_element(element):
            tag_dict = {"tag": element.name}
            if element.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                if element.name == "h1":
                    tag_dict["tag"] = "h3"
                elif element.name == "h2":
                    tag_dict["tag"] = "h4"
                else:
                    tag_dict["tag"] = "p"
                    tag_dict["children"] = [
                        {"tag": "strong", "children": element.contents}
                    ]

                if element.attrs:
                    tag_dict["attrs"] = element.attrs
                if element.contents:
                    children = []
                    for child in element.contents:
                        if isinstance(child, str):
                            children.append(child.strip())
                        else:
                            children.append(parse_element(child))
                    tag_dict["children"] = children
            else:
                if element.attrs:
                    tag_dict["attrs"] = element.attrs
                if element.contents:
                    children = []
                    for child in element.contents:
                        if isinstance(child, str):
                            children.append(child.strip())
                        else:
                            children.append(parse_element(child))
                    if children:
                        tag_dict["children"] = children
            return tag_dict

        new_dom = []
        for element in soup.contents:
            if isinstance(element, str) and not element.strip():
                continue
            elif isinstance(element, str):
                new_dom.append({"tag": "text", "content": element.strip()})
            else:
                new_dom.append(parse_element(element))

        return new_dom

    def upload_image(self, file_name: str) -> str:
        base_url = "https://telegra.ph"
        upload_url = f"{base_url}/upload"

        try:
            content_type = guess_type(file_name)[0]
            with open(file_name, "rb") as f:
                response = requests.post(
                    upload_url, files={"file": ("blob", f, content_type)}
                )
                response.raise_for_status()
                # [{'src': '/file/xx.jpg'}]
                response = response.json()
                image_url = f"{base_url}{response[0]['src']}"
                return image_url
        except Exception as e:
            logger.info(f"upload image: {e}")
            return "https://telegra.ph/api"


# `import *` will give you these
__all__ = [
    "bot_reply_first",
    "bot_reply_markdown",
    "remove_prompt_prefix",
    "enrich_text_with_urls",
    "image_to_data_uri",
    "TelegraphAPI",
    "non_llm_handler",
]
