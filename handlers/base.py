from telebot import TeleBot
from telebot.types import Message
from typing import Dict, List

from handlers import enrich_text_with_urls, bot_reply_first, bot_reply_markdown


class BasicTextHandler:
    """
    use in memory storage as the user history context
    todo: use persistent storage as the provider
    """
    user_based_context: Dict[str, List[any]] = {}

    bot: TeleBot

    def __init__(self, bot: TeleBot):
        self.bot = bot

    def who_am_i(self) -> str:
        pass

    def register(self):
        pass

    """
    get the user history from the context
    return empty array if there is no history in context
    """

    def get_user_context(self, user_id):

        user_context = []

        if str(user_id) not in self.user_based_context:
            self.user_based_context[user_id] = (
                user_context  # for the imuutable list
            )
        else:
            user_context = self.user_based_context[user_id]

        return user_context

    def clear_user_context(self, user_id):
        user_context = self.get_user_context(user_id)
        user_context.clear()

    def handle(self, msg: Message):
        user_id = str(msg.from_user.id)

        msg_content = msg.text.strip()
        if msg_content == "clear":
            self.bot.reply_to(
                msg,
                "just clear your llama messages history",
            )
            self.clear_user_context(str(msg.from_user.id))
            return

        if msg_content[:4].lower() == "new ":
            self.clear_user_context(str(msg.from_user.id))
            msg_content = msg_content[:4].lower()

        msg_content = enrich_text_with_urls(msg_content)

        # show something, make it more responsible
        reply_msg = bot_reply_first(msg, self.who_am_i(), self.bot)

        user_msg_context = self.get_user_context(user_id)
        user_msg_context.append({"role": "user", "content": msg_content})
        if len(user_msg_context) > 10:
            user_msg_context = user_msg_context[2:]

        try:
            answer = self.process(msg, user_msg_context)
            self.on_success(msg, reply_msg, answer)
        except Exception as e:
            self.on_failure(msg, reply_msg, e)

    """
    how to AI agent process msg and return the answer
    """

    def process(self, msg: Message, chat_context) -> str:
        raise Exception("process method is not implemented")

    def on_success(self, msg: Message, reply_msg: Message, content):
        user_msg_context = self.get_user_context(msg.from_user.id)
        if not content:
            llama_reply_text = f"{self.who_am_i()} did not answer."
            user_msg_context.pop()
        else:
            llama_reply_text = content
            user_msg_context.append(
                {
                    "role": "assistant",
                    "content": llama_reply_text,
                }
            )
            bot_reply_markdown(reply_msg, self.who_am_i(), llama_reply_text, self.bot)

    def on_failure(self, msg: Message, reply_msg: Message, e: Exception = None, ):
        if e is not None:
            print(e)
        user_id = str(msg.from_user.id)
        bot_reply_markdown(reply_msg, self.who_am_i(), "answer wrong", self.bot)
        user_msg_context = self.get_user_context(user_id)
        user_msg_context.pop()
