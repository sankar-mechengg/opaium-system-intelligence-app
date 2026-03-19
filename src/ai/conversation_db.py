"""
OP(AI)UM — Conversation History Database

SQLite-backed persistent storage for chat conversations.
Each conversation stores its messages, folder context, and metadata.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, Generator

from loguru import logger

from src.config.constants import AppConstants


CONVERSATIONS_DB_FILE = AppConstants.APPDATA_DIR / "conversations.db"


class ConversationRecord:
    """A stored conversation with its messages."""

    def __init__(
        self,
        id: int = 0,
        title: str = "",
        folder_path: str = "",
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        message_count: int = 0,
    ) -> None:
        self.id = id
        self.title = title
        self.folder_path = folder_path
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        self.message_count = message_count

    @property
    def folder_name(self) -> str:
        if not self.folder_path:
            return ""
        return Path(self.folder_path).name

    @property
    def display_time(self) -> str:
        now = datetime.now()
        diff = now - self.updated_at
        if diff.days == 0:
            return self.updated_at.strftime("%H:%M")
        elif diff.days == 1:
            return "Yesterday"
        elif diff.days < 7:
            return self.updated_at.strftime("%A")
        else:
            return self.updated_at.strftime("%b %d")


class MessageRecord:
    """A stored message within a conversation."""

    def __init__(
        self,
        id: int = 0,
        conversation_id: int = 0,
        role: str = "",
        content: str = "",
        timestamp: datetime | None = None,
    ) -> None:
        self.id = id
        self.conversation_id = conversation_id
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now()


class ConversationDB:
    """SQLite database for conversation history persistence."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or CONVERSATIONS_DB_FILE
        self._connection: Optional[sqlite3.Connection] = None
        self._initialize()

    def _initialize(self) -> None:
        AppConstants.ensure_dirs()
        try:
            conn = self._get_connection()
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL DEFAULT '',
                    folder_path TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_msg_conv
                    ON messages(conversation_id);
                CREATE INDEX IF NOT EXISTS idx_conv_updated
                    ON conversations(updated_at);
            """)
            conn.commit()
            logger.debug(f"Conversation DB initialized: {self._db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize conversation DB: {e}")

    def _get_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            self._connection = sqlite3.connect(
                str(self._db_path),
                timeout=10,
                check_same_thread=False,
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA foreign_keys=ON")
        return self._connection

    @contextmanager
    def _cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def create_conversation(self, title: str = "", folder_path: str = "") -> int:
        """Create a new conversation and return its ID."""
        now = datetime.now().isoformat()
        with self._cursor() as cursor:
            cursor.execute(
                "INSERT INTO conversations (title, folder_path, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (title, folder_path, now, now),
            )
            conv_id = cursor.lastrowid
            logger.debug(f"Created conversation #{conv_id}: {title}")
            return conv_id  # type: ignore[return-value]

    def update_conversation(self, conv_id: int, title: str | None = None, folder_path: str | None = None) -> None:
        """Update conversation metadata."""
        with self._cursor() as cursor:
            updates = ["updated_at = ?"]
            params: list = [datetime.now().isoformat()]
            if title is not None:
                updates.append("title = ?")
                params.append(title)
            if folder_path is not None:
                updates.append("folder_path = ?")
                params.append(folder_path)
            params.append(conv_id)
            cursor.execute(
                f"UPDATE conversations SET {', '.join(updates)} WHERE id = ?",
                params,
            )

    def add_message(self, conversation_id: int, role: str, content: str) -> int:
        """Add a message to a conversation."""
        now = datetime.now().isoformat()
        with self._cursor() as cursor:
            cursor.execute(
                "INSERT INTO messages (conversation_id, role, content, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (conversation_id, role, content, now),
            )
            # Update conversation timestamp
            cursor.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
            return cursor.lastrowid  # type: ignore[return-value]

    def get_conversations(self, limit: int = 100) -> list[ConversationRecord]:
        """Get all conversations, newest first."""
        with self._cursor() as cursor:
            cursor.execute(
                """SELECT c.*, COUNT(m.id) as message_count
                   FROM conversations c
                   LEFT JOIN messages m ON m.conversation_id = c.id
                   GROUP BY c.id
                   ORDER BY c.updated_at DESC
                   LIMIT ?""",
                (limit,),
            )
            return [self._row_to_conversation(row) for row in cursor.fetchall()]

    def get_messages(self, conversation_id: int) -> list[MessageRecord]:
        """Get all messages for a conversation, oldest first."""
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC",
                (conversation_id,),
            )
            return [self._row_to_message(row) for row in cursor.fetchall()]

    def delete_conversation(self, conv_id: int) -> None:
        """Delete a conversation and all its messages."""
        with self._cursor() as cursor:
            cursor.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            logger.info(f"Deleted conversation #{conv_id}")

    def _generate_title(self, first_message: str) -> str:
        """Generate a short title from the first user message."""
        title = first_message.strip()
        # Remove folder context prefix
        if title.startswith("[Working in:"):
            lines = title.split("\n", 1)
            title = lines[1] if len(lines) > 1 else lines[0]
        title = title.strip()
        if len(title) > 60:
            title = title[:57] + "..."
        return title or "New Conversation"

    def _row_to_conversation(self, row: sqlite3.Row) -> ConversationRecord:
        return ConversationRecord(
            id=row["id"],
            title=row["title"],
            folder_path=row["folder_path"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            message_count=row["message_count"],
        )

    def _row_to_message(self, row: sqlite3.Row) -> MessageRecord:
        return MessageRecord(
            id=row["id"],
            conversation_id=row["conversation_id"],
            role=row["role"],
            content=row["content"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )

    def close(self) -> None:
        if self._connection:
            self._connection.close()
            self._connection = None
