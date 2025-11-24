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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tigong_alerts (
                    chat_id INTEGER,
                    user_id INTEGER,
                    user_name TEXT,
                    username TEXT,
                    date TEXT,
                    confirmed INTEGER DEFAULT 0,
                    PRIMARY KEY (chat_id, user_id, date)
                );
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

    def get_user_stats(self, chat_id: int, limit: int = 10) -> list[UserStatsEntry]:
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
                (chat_id, limit),
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

    def add_tigong_alert_user(
        self, chat_id: int, user_id: int, user_name: str, username: str, date: str
    ) -> None:
        """添加用户到提肛提醒队列"""
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tigong_alerts (chat_id, user_id, user_name, username, date, confirmed)
                VALUES (?, ?, ?, ?, ?, 0);
                """,
                (chat_id, user_id, user_name, username, date),
            )
            conn.commit()

    def confirm_tigong_alert(self, chat_id: int, user_id: int, date: str) -> bool:
        """确认用户完成提肛"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE tigong_alerts SET confirmed = 1
                WHERE chat_id = ? AND user_id = ? AND date = ?;
                """,
                (chat_id, user_id, date),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_unconfirmed_users(self, chat_id: int, date: str) -> list[dict]:
        """获取当天未确认的用户列表"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT user_id, user_name, username
                FROM tigong_alerts
                WHERE chat_id = ? AND date = ? AND confirmed = 0;
                """,
                (chat_id, date),
            )
            rows = cursor.fetchall()
        return [
            {"user_id": row[0], "user_name": row[1], "username": row[2]} for row in rows
        ]

    def get_today_message_count(self, chat_id: int, date_str: str) -> int:
        """获取当天的消息数量"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM messages
                WHERE chat_id = ? AND DATE(timestamp) = ?;
                """,
                (chat_id, date_str),
            )
            result = cursor.fetchone()
            return result[0] if result else 0
