import json
import os
from mimetypes import guess_type

import markdown
import requests
from bs4 import BeautifulSoup

from ._utils import logger


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
        except requests.exceptions.RequestException:
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
