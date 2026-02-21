"""
OP(AI)UM — Custom Tracking Database

SQLite database that tracks file and folder access beyond what
Windows Recent provides. Maps NTFS file IDs to paths for
detecting renames and moves. Supplements the .lnk-based tracking.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, Generator

from loguru import logger

from src.config.constants import AppConstants
from src.core.models import TrackingRecord, ItemType


class TrackingDB:
    """
    SQLite-based tracking database for file/folder access history.

    Stores NTFS file IDs alongside paths so that renames and
    moves within the same drive can be detected and auto-updated.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or AppConstants.TRACKING_DB_FILE
        self._connection: Optional[sqlite3.Connection] = None
        self._initialize()

    def _initialize(self) -> None:
        """Create the database and tables if they don't exist."""
        AppConstants.ensure_dirs()
        try:
            conn = self._get_connection()
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tracked_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL,
                    volume_serial INTEGER NOT NULL,
                    path TEXT NOT NULL,
                    name TEXT NOT NULL,
                    item_type TEXT NOT NULL DEFAULT 'folder',
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    access_count INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    UNIQUE(file_id, volume_serial)
                );

                CREATE INDEX IF NOT EXISTS idx_tracked_path
                    ON tracked_items(path);
                CREATE INDEX IF NOT EXISTS idx_tracked_fileid
                    ON tracked_items(file_id, volume_serial);
                CREATE INDEX IF NOT EXISTS idx_tracked_active
                    ON tracked_items(is_active);
                CREATE INDEX IF NOT EXISTS idx_tracked_lastseen
                    ON tracked_items(last_seen);
            """)
            conn.commit()
            logger.debug(f"Tracking DB initialized: {self._db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize tracking DB: {e}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(
                str(self._db_path),
                timeout=10,
                check_same_thread=False,
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA busy_timeout=5000")
        return self._connection

    @contextmanager
    def _cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """Context manager for database cursor with auto-commit."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def upsert_item(
        self,
        file_id: int,
        volume_serial: int,
        path: str,
        name: str,
        item_type: ItemType = ItemType.FOLDER,
    ) -> None:
        """
        Insert or update a tracked item.

        If the file_id + volume_serial already exists, updates
        the path (handles renames) and increments access count.
        """
        now = datetime.now().isoformat()

        with self._cursor() as cursor:
            # Check if exists
            cursor.execute(
                "SELECT id, path FROM tracked_items WHERE file_id = ? AND volume_serial = ?",
                (file_id, volume_serial),
            )
            row = cursor.fetchone()

            if row:
                old_path = row["path"]
                if old_path != path:
                    logger.info(f"Tracking: path updated {old_path} -> {path}")
                cursor.execute(
                    """UPDATE tracked_items
                       SET path = ?, name = ?, last_seen = ?,
                           access_count = access_count + 1, is_active = 1
                       WHERE file_id = ? AND volume_serial = ?""",
                    (path, name, now, file_id, volume_serial),
                )
            else:
                cursor.execute(
                    """INSERT INTO tracked_items
                       (file_id, volume_serial, path, name, item_type, first_seen, last_seen)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (file_id, volume_serial, path, name, item_type.value, now, now),
                )

    def get_current_path(self, file_id: int, volume_serial: int) -> Optional[str]:
        """
        Get the last known path for a file ID.

        Args:
            file_id: NTFS file reference number.
            volume_serial: Volume serial number.

        Returns:
            Current path string or None.
        """
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT path FROM tracked_items WHERE file_id = ? AND volume_serial = ? AND is_active = 1",
                (file_id, volume_serial),
            )
            row = cursor.fetchone()
            return row["path"] if row else None

    def find_by_path(self, path: str) -> Optional[TrackingRecord]:
        """Look up a tracking record by path."""
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT * FROM tracked_items WHERE path = ? AND is_active = 1",
                (path,),
            )
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None

    def get_all_active(self, item_type: Optional[ItemType] = None) -> list[TrackingRecord]:
        """Get all active tracked items."""
        with self._cursor() as cursor:
            if item_type:
                cursor.execute(
                    "SELECT * FROM tracked_items WHERE is_active = 1 AND item_type = ? ORDER BY last_seen DESC",
                    (item_type.value,),
                )
            else:
                cursor.execute(
                    "SELECT * FROM tracked_items WHERE is_active = 1 ORDER BY last_seen DESC"
                )
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def get_recently_seen(self, max_days: int = 30) -> list[TrackingRecord]:
        """Get items seen within the last N days."""
        cutoff = datetime.now().isoformat()[:10]  # Simple date comparison
        with self._cursor() as cursor:
            cursor.execute(
                """SELECT * FROM tracked_items
                   WHERE is_active = 1 AND last_seen >= date(?, ?)
                   ORDER BY last_seen DESC""",
                (cutoff, f"-{max_days} days"),
            )
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def mark_inactive(self, file_id: int, volume_serial: int) -> None:
        """Mark an item as inactive (deleted/inaccessible)."""
        with self._cursor() as cursor:
            cursor.execute(
                "UPDATE tracked_items SET is_active = 0 WHERE file_id = ? AND volume_serial = ?",
                (file_id, volume_serial),
            )

    def update_path(self, file_id: int, volume_serial: int, new_path: str, new_name: str) -> None:
        """Update the path for a tracked item (after rename/move detection)."""
        now = datetime.now().isoformat()
        with self._cursor() as cursor:
            cursor.execute(
                """UPDATE tracked_items
                   SET path = ?, name = ?, last_seen = ?
                   WHERE file_id = ? AND volume_serial = ?""",
                (new_path, new_name, now, file_id, volume_serial),
            )
            logger.debug(f"Tracking path updated: file_id={file_id} -> {new_path}")

    def cleanup_stale(self, days: int = 90) -> int:
        """Remove tracking records older than N days."""
        with self._cursor() as cursor:
            cursor.execute(
                "DELETE FROM tracked_items WHERE last_seen < date('now', ?)",
                (f"-{days} days",),
            )
            removed = cursor.rowcount
            if removed:
                logger.info(f"Cleaned up {removed} stale tracking records.")
            return removed

    def get_stats(self) -> dict[str, int]:
        """Get database statistics."""
        with self._cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as total FROM tracked_items")
            total = cursor.fetchone()["total"]
            cursor.execute("SELECT COUNT(*) as active FROM tracked_items WHERE is_active = 1")
            active = cursor.fetchone()["active"]
            return {"total": total, "active": active, "inactive": total - active}

    def _row_to_record(self, row: sqlite3.Row) -> TrackingRecord:
        """Convert a database row to a TrackingRecord."""
        return TrackingRecord(
            file_id=row["file_id"],
            volume_serial=row["volume_serial"],
            path=row["path"],
            name=row["name"],
            item_type=ItemType(row["item_type"]),
            first_seen=datetime.fromisoformat(row["first_seen"]),
            last_seen=datetime.fromisoformat(row["last_seen"]),
            access_count=row["access_count"],
            is_active=bool(row["is_active"]),
        )

    def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
