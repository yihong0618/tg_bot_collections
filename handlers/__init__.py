from __future__ import annotations

import base64
import importlib
import re
import traceback
from functools import update_wrapper
from pathlib import Path
from typing import Any, Callable, TypeVar

import requests
from telebot import TeleBot
from telebot.types import BotCommand, Message
from telebot.util import smart_split
import telegramify_markdown
from telegramify_markdown.customize import markdown_symbol
from urlextract import URLExtract

markdown_symbol.head_level_1 = "📌"  # If you want, Customizing the head level 1 symbol
markdown_symbol.link = "🔗"  # If you want, Customizing the link symbol

T = TypeVar("T", bound=Callable)

BOT_MESSAGE_LENGTH = 4000


def bot_reply_first(message: Message, who: str, bot: TeleBot) -> Message:
    """Create the first reply message which make user feel the bot is working."""
    return bot.reply_to(
        message, f"*{who}* is _thinking_ \.\.\.", parse_mode="MarkdownV2"
    )


def bot_reply_markdown(
    reply_id: Message, who: str, text: str, bot: TeleBot, split_text: bool = True
) -> bool:
    """
    reply the Markdown by take care of the message length.
    it will fallback to plain text in case of any failure
    """
    try:
        if len(text.encode("utf-8")) <= BOT_MESSAGE_LENGTH or not split_text:
            bot.edit_message_text(
                f"*{who}*:\n{telegramify_markdown.convert(text)}",
                chat_id=reply_id.chat.id,
                message_id=reply_id.message_id,
                parse_mode="MarkdownV2",
            )
            return True

        # Need a split of message
        msgs = smart_split(text, BOT_MESSAGE_LENGTH)
        bot.edit_message_text(
            f"*{who}* \[1/{len(msgs)}\]:\n{telegramify_markdown.convert(msgs[0])}",
            chat_id=reply_id.chat.id,
            message_id=reply_id.message_id,
            parse_mode="MarkdownV2",
        )
        for i in range(1, len(msgs)):
            bot.reply_to(
                reply_id.reply_to_message,
                f"*{who}* \[{i+1}/{len(msgs)}\]:\n{telegramify_markdown.convert(msgs[i])}",
                parse_mode="MarkdownV2",
            )

        return True
    except Exception as e:
        print(traceback.format_exc())
        # print(f"wrong markdown format: {text}")
        bot.edit_message_text(
            f"*{who}*:\n{text}",
            chat_id=reply_id.chat.id,
            message_id=reply_id.message_id,
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


def wrap_handler(handler: T, bot: TeleBot) -> T:
    def wrapper(message: Message, *args: Any, **kwargs: Any) -> None:
        try:
            m = ""

            if message.text and message.text.find("answer_it") != -1:
                # for answer_it no args
                return handler(message, *args, **kwargs)
            elif message.text is not None:
                m = message.text = extract_prompt(message.text, bot.get_me().username)
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
            traceback.print_exc()
            # handle more here
            if str(e).find("RECITATION") > 0:
                bot.reply_to(message, "Your prompt `RECITATION` please check the log")
            else:
                bot.reply_to(message, "Something wrong, please check the log")

    return update_wrapper(wrapper, handler)


def load_handlers(bot: TeleBot, disable_commands: list[str]) -> None:
    # import all submodules
    for name in list_available_commands():
        if name in disable_commands:
            continue
        module = importlib.import_module(f".{name}", __package__)
        if hasattr(module, "register"):
            print(f"Loading {name} handlers.")
            module.register(bot)
    print("Loading handlers done.")

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
        print("Setting commands done.")


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
        print(e)
        return None


def enrich_text_with_urls(text: str) -> str:
    urls = extract_url_from_text(text)
    for u in urls:
        try:
            url_text = get_text_from_jina_reader(u)
            url_text = f"\n```markdown\n{url_text}\n```\n"
            text = text.replace(u, url_text)
        except Exception as e:
            # just ignore the error
            pass

    return text


def image_to_data_uri(file_path):
    with open(file_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
        return f"data:image/png;base64,{encoded_image}"


import requests
import json
import markdown  # pip install Markdown
from bs4 import BeautifulSoup  # pip install beautifulsoup4


def create_ph_account(short_name: str, author_name: str, author_url: str = None) -> str:
    """
        Creates a new account on the Telegra.ph platform.
        If an account already exists (stored in a local JSON file), returns the existing access token.
        Otherwise, creates a new account and stores the information locally.
        Sample request
    https://api.telegra.ph/editAccountInfo?access_token=d3b25feccb89e508a9114afb82aa421fe2a9712b963b387cc5ad71e58722&short_name=Sandbox&author_name=Anonymous

        Args:
            short_name (str): The short name of the account.
            author_name (str): The name of the author.
            author_url (str, optional): The URL of the author's profile. Defaults to None.

        Returns:
            str: The access token for the account.

        Raises:
            requests.RequestException: If the API request fails.
            json.JSONDecodeError: If the API response is not valid JSON.
            KeyError: If the API response does not contain the expected data.
    """
    TELEGRAPH_API_URL = "https://api.telegra.ph/createAccount"

    # Try to load existing account information
    try:
        with open("telegraph_token.json", "r") as f:
            account = json.load(f)
        return account["result"]["access_token"]
    except FileNotFoundError:
        # If no existing account, create a new one
        data = {
            "short_name": short_name,
            "author_name": author_name,
        }
        if author_url:
            data["author_url"] = author_url

        # Make API request
        response = requests.post(TELEGRAPH_API_URL, data=data)
        response.raise_for_status()  # Raises an HTTPError for bad responses

        account = response.json()
        access_token = account["result"]["access_token"]

        # Store the new account information
        with open("telegraph_token.json", "w") as f:
            json.dump(account, f)

        return access_token


class TelegraphAPI:
    def __init__(self, access_token):
        self.access_token = access_token
        self.base_url = "https://api.telegra.ph"

        # Get account info on initialization
        account_info = self.get_account_info()
        self.short_name = account_info.get("short_name")
        self.author_name = account_info.get("author_name")
        self.author_url = account_info.get("author_url")

    def create_page(
        self, title, content, author_name=None, author_url=None, return_content=False
    ):
        """
        Creates a new Telegraph page.

        Args:
            title (str): Page title (1-256 characters).
            content (list): Content of the page as a list of Node dictionaries.
            author_name (str, optional): Author name (0-128 characters). Defaults to account's author_name.
            author_url (str, optional): Profile link (0-512 characters). Defaults to account's author_url.
            return_content (bool, optional): If True, return the content field in the response.

        Returns:
            str: URL of the created page.

        Raises:
            requests.exceptions.RequestException: If the request fails.


        """
        url = f"{self.base_url}/createPage"
        data = {
            "access_token": self.access_token,
            "title": title,
            "content": json.dumps(content),
            "return_content": return_content,
            # Use provided author info or fall back to account info
            "author_name": author_name if author_name else self.author_name,
            "author_url": author_url if author_url else self.author_url,
        }

        response = requests.post(url, data=data)
        response.raise_for_status()
        response = response.json()
        page_url = response["result"]["url"]
        return page_url

    def get_account_info(self):
        """
        Gets information about the Telegraph account.

        Returns:
            dict: Account information including short_name, author_name, and author_url.
                 Returns None if there's an error.
        """
        url = f"{self.base_url}/getAccountInfo?access_token={self.access_token}"  # &fields=[\"author_name\",\"author_url\"] for specific fields
        response = requests.get(url)

        if response.status_code == 200:
            return response.json()["result"]
        else:
            print(f"Fail getting telegra.ph token info: {response.status_code}")
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
        """
        Edits an existing Telegraph page.

        Args:
            path (str): Path of the page to edit.
            title (str): New page title (1-256 characters).
            content (list): New content of the page as a list of Node dictionaries.
            author_name (str, optional): Author name (0-128 characters). Defaults to account's author_name.
            author_url (str, optional): Profile link (0-512 characters). Defaults to account's author_url.
            return_content (bool, optional): If True, return the content field in the response.

        Returns:
            str: URL of the edited page.

        Raises:
            requests.exceptions.RequestException: If the request fails.
        """
        url = f"{self.base_url}/editPage"
        data = {
            "access_token": self.access_token,
            "path": path,
            "title": title,
            "content": json.dumps(content),
            "return_content": return_content,
            # Use provided author info or fall back to account info
            "author_name": author_name if author_name else self.author_name,
            "author_url": author_url if author_url else self.author_url,
        }

        response = requests.post(url, data=data)
        response.raise_for_status()
        response = response.json()

        page_url = response["result"]["url"]
        return page_url

    def get_page(self, path):
        """
        Gets information about a Telegraph page.

        Args:
            path (str): Path of the page to get.

        Returns:
            dict: Information about the page.
        """
        url = f"{self.base_url}/getPage/{path}?return_content=true"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()["result"]

    def create_page_md(
        self,
        title,
        markdown_text,
        author_name=None,
        author_url=None,
        return_content=False,
    ):
        """
        Creates a new Telegraph page from markdown text.

        Args:
            title (str): Page title (1-256 characters).
            markdown_text (str): Markdown text to convert to HTML.
            author_name (str, optional): Author name (0-128 characters). Defaults to account's author_name.
            author_url (str, optional): Profile link (0-512 characters). Defaults to account's author_url.
            return_content (bool, optional): If True, return the content field in the response.

        Returns:
            str: URL of the created page.

        Raises:
            requests.exceptions.RequestException: If the request fails.
        """
        content = md_to_dom(markdown_text)
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
        content = md_to_dom(markdown_text)
        return self.edit_page(
            path, title, content, author_name, author_url, return_content
        )


def md_to_dom(markdown_text):
    """Converts markdown text to a Python dictionary representing the DOM,
    limiting heading levels to h3 and h4.

    Args:
        markdown_text: The markdown text to convert.

    Returns:
        A Python list representing the DOM, where each element is a dictionary
        with the following keys:
            - 'tag': The tag name of the element.
            - 'attributes': A dictionary of attributes for the element (optional).
            - 'children': A list of child elements (optional).
    """

    # Convert markdown to HTML
    html = markdown.markdown(
        markdown_text,
        extensions=["markdown.extensions.extra", "markdown.extensions.sane_lists"],
    )

    # Parse the HTML with BeautifulSoup
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
                tag_dict["children"] = [{"tag": "strong", "children": element.contents}]

            # Correctly handle children for h1-h6
            if element.attrs:
                tag_dict["attributes"] = element.attrs
            if element.contents:
                children = []
                for child in element.contents:
                    if isinstance(child, str):
                        # Remove leading/trailing whitespace from text nodes
                        children.append(child.strip())
                    else:  # it's another tag
                        children.append(parse_element(child))
                tag_dict["children"] = children
        else:
            if element.attrs:
                tag_dict["attributes"] = element.attrs
            if element.contents:
                children = []
                for child in element.contents:
                    if isinstance(child, str):
                        # Remove leading/trailing whitespace from text nodes
                        children.append(child.strip())
                    else:  # it's another tag
                        children.append(parse_element(child))
                if children:
                    tag_dict["children"] = children
        return tag_dict

    new_dom = []
    for element in soup.contents:
        if isinstance(element, str) and not element.strip():
            # Skip empty text nodes
            continue
        elif isinstance(element, str):
            # Treat remaining text nodes as separate elements for clarity
            new_dom.append({"tag": "text", "content": element.strip()})
        else:
            new_dom.append(parse_element(element))

    return new_dom


# `import *` will give you these
__all__ = [
    "bot_reply_first",
    "bot_reply_markdown",
    "enrich_text_with_urls",
    "image_to_data_uri",
    "TelegraphAPI",
    "create_ph_account",
]
