import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class ChatMessage:
    chat_id: int
    message_id: int
    content: str
    user_id: int
    user_name: str
    timestamp: datetime


@dataclass(frozen=True)
class StatsEntry:
    date: str
    message_count: int


@dataclass(frozen=True)
class UserStatsEntry:
    user_id: int
    user_name: str
    message_count: int


class MessageStore:
    def __init__(self, db_file: str):
        parent_folder = os.path.dirname(db_file)
        if not os.path.exists(parent_folder):
            os.makedirs(parent_folder)
        self._db_file = db_file
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        """Create a new database connection."""
        return sqlite3.connect(self._db_file)

    def _init_db(self):
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    chat_id INTEGER,
                    message_id INTEGER,
                    content TEXT,
                    user_id INTEGER,
                    user_name TEXT,
                    timestamp TEXT,
                    PRIMARY KEY (chat_id, message_id)
                );
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_timestamp ON messages (chat_id, timestamp);
            """
            )
            conn.commit()

    def add_message(
        self, message: ChatMessage, conn: sqlite3.Connection | None = None
    ) -> None:
        need_close = False
        if conn is None:
            conn = self.connect()
            need_close = True
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO messages (chat_id, message_id, content, user_id, user_name, timestamp)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    message.chat_id,
                    message.message_id,
                    message.content,
                    message.user_id,
                    message.user_name,
                    message.timestamp.isoformat(),
                ),
            )
            self._clean_old_messages(message.chat_id, conn)
            conn.commit()
        finally:
            if need_close:
                conn.close()

    def get_messages_since(self, chat_id: int, since: datetime) -> list[ChatMessage]:
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT chat_id, message_id, content, user_id, user_name, timestamp
                FROM messages
            WHERE chat_id = ? AND timestamp >= ?
            ORDER BY timestamp ASC;
        """,
                (chat_id, since.astimezone(timezone.utc).isoformat()),
            )
            rows = cursor.fetchall()
        return [
            ChatMessage(
                chat_id=row[0],
                message_id=row[1],
                content=row[2],
                user_id=row[3],
                user_name=row[4],
                timestamp=datetime.fromisoformat(row[5]),
            )
            for row in rows
        ]

    def get_stats(self, chat_id: int) -> list[StatsEntry]:
        with self.connect() as conn:
            self._clean_old_messages(chat_id, conn)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DATE(timestamp), COUNT(*)
                FROM messages
                WHERE chat_id = ?
            GROUP BY DATE(timestamp)
            ORDER BY DATE(timestamp) ASC;
        """,
                (chat_id,),
            )
            rows = cursor.fetchall()
        return [StatsEntry(date=row[0], message_count=row[1]) for row in rows]

    def get_user_stats(self, chat_id: int, topk: int = 10) -> list[UserStatsEntry]:
        with self.connect() as conn:
            self._clean_old_messages(chat_id, conn)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT user_id, 
                    (SELECT user_name FROM messages m0 WHERE m0.user_id = m1.user_id LIMIT 1) AS name,
                    COUNT(*) AS num
                FROM messages m1
                WHERE chat_id = ?
                GROUP BY user_id
                ORDER BY num DESC
                LIMIT ?;""",
                (chat_id, topk),
            )
            rows = cursor.fetchall()
            return [UserStatsEntry(*row) for row in rows]

    def search_messages(
        self, chat_id: int, keyword: str, limit: int = 10
    ) -> list[ChatMessage]:
        # TODO: Fuzzy search with full-text search or similar
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT chat_id, message_id, content, user_id, user_name, timestamp
                FROM messages
                WHERE chat_id = ? AND content LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?;
            """,
                (chat_id, f"%{keyword}%", limit),
            )
            rows = cursor.fetchall()
        return [
            ChatMessage(
                chat_id=row[0],
                message_id=row[1],
                content=row[2],
                user_id=row[3],
                user_name=row[4],
                timestamp=datetime.fromisoformat(row[5]),
            )
            for row in rows
        ]

    def _clean_old_messages(
        self, chat_id: int, conn: sqlite3.Connection, days: int = 30
    ) -> None:
        cursor = conn.cursor()
        threshold_date = datetime.now(tz=timezone.utc) - timedelta(days=days)
        cursor.execute(
            "DELETE FROM messages WHERE chat_id = ? AND timestamp < ?;",
            (chat_id, threshold_date.isoformat()),
        )
