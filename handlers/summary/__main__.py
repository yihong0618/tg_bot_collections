from __future__ import annotations

import asyncio
import os
import sys

from .messages import ChatMessage, MessageStore


async def fetch_messages(chat_id: int) -> None:
    from telethon import TelegramClient
    from telethon.tl.types import Message

    store = MessageStore("data/messages.db")

    api_id = int(os.getenv("TELEGRAM_API_ID"))
    api_hash = os.getenv("TELEGRAM_API_HASH")
    async with TelegramClient("test", api_id, api_hash) as client:
        assert isinstance(client, TelegramClient)
        with store.connect() as conn:
            async for message in client.iter_messages(chat_id, reverse=True):
                if not isinstance(message, Message) or not message.message:
                    continue
                if not message.from_id:
                    continue
                print(message.pretty_format(message))
                user = await client.get_entity(message.from_id)
                fullname = user.first_name
                if user.last_name:
                    fullname += f" {user.last_name}"
                store.add_message(
                    ChatMessage(
                        chat_id=chat_id,
                        message_id=message.id,
                        content=message.message,
                        user_id=message.from_id.user_id,
                        user_name=fullname,
                        timestamp=message.date,
                    ),
                    conn=conn,
                )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m handlers.summary <chat_id>")
        sys.exit(1)
    chat_id = int(sys.argv[1])
    asyncio.run(fetch_messages(chat_id))  # 替换为实际的群组ID
