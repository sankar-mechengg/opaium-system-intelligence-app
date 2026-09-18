"""
OP(AI)UM — Operation Journal

SQLite-backed persistent journal of all AI-performed file operations.
Stores full operation details including file mappings for undo.
Supports 2-day auto-purge and export to CSV/text.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Generator
from contextlib import contextmanager, suppress
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

from src.config.constants import AppConstants
from src.undo.operation_models import FileMapping, Operation, OperationType


class OperationJournal:
    """
    Persistent journal of file operations for undo support.

    Every AI operation is recorded here with enough detail to
    reverse it. The journal auto-purges entries older than the
    configured retention period (default: 2 days).
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or AppConstants.UNDO_DB_FILE
        self._connection: sqlite3.Connection | None = None
        # Tools record from the thread pool while the UI reads on the main thread.
        self._lock = threading.RLock()
        self._initialize()

    def _initialize(self) -> None:
        """Create database and tables."""
        AppConstants.ensure_dirs()
        try:
            conn = self._get_connection()
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    operation_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    affected_count INTEGER DEFAULT 0,
                    is_undone INTEGER DEFAULT 0,
                    is_undoable INTEGER DEFAULT 1,
                    error_message TEXT DEFAULT '',
                    metadata TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS file_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_id INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    destination TEXT DEFAULT '',
                    original_name TEXT DEFAULT '',
                    new_name TEXT DEFAULT '',
                    FOREIGN KEY (operation_id) REFERENCES operations(id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_ops_timestamp
                    ON operations(timestamp);
                CREATE INDEX IF NOT EXISTS idx_ops_type
                    ON operations(operation_type);
                CREATE INDEX IF NOT EXISTS idx_ops_undone
                    ON operations(is_undone);
                CREATE INDEX IF NOT EXISTS idx_mappings_opid
                    ON file_mappings(operation_id);
            """)
            conn.commit()
            logger.debug(f"Operation journal initialized: {self._db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize operation journal: {e}")

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
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                yield cursor
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()

    def record(self, operation: Operation) -> int:
        """
        Record a new operation in the journal.

        Args:
            operation: The Operation to record.

        Returns:
            The database ID of the recorded operation.
        """
        with self._cursor() as cursor:
            cursor.execute(
                """INSERT INTO operations
                   (timestamp, operation_type, description, affected_count,
                    is_undone, is_undoable, error_message, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    operation.timestamp.isoformat(),
                    operation.operation_type.value,
                    operation.description,
                    operation.affected_count,
                    int(operation.is_undone),
                    int(operation.is_undoable),
                    operation.error_message,
                    json.dumps(operation.metadata),
                ),
            )
            op_id = cursor.lastrowid

            # Insert file mappings
            for mapping in operation.file_mappings:
                cursor.execute(
                    """INSERT INTO file_mappings
                       (operation_id, source, destination, original_name, new_name)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        op_id,
                        mapping.source,
                        mapping.destination,
                        mapping.original_name,
                        mapping.new_name,
                    ),
                )

            logger.info(f"Recorded operation #{op_id}: {operation.type_label} ({operation.affected_count} items)")
            return op_id  # type: ignore[return-value]

    def get_operation(self, op_id: int) -> Operation | None:
        """Get a specific operation by ID."""
        with self._cursor() as cursor:
            cursor.execute("SELECT * FROM operations WHERE id = ?", (op_id,))
            row = cursor.fetchone()
            if not row:
                return None

            cursor.execute("SELECT * FROM file_mappings WHERE operation_id = ?", (op_id,))
            mapping_rows = cursor.fetchall()

            return self._row_to_operation(row, mapping_rows)

    def get_recent(self, limit: int = 50) -> list[Operation]:
        """Get recent operations, newest first."""
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT * FROM operations ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
            operations = []
            for row in cursor.fetchall():
                cursor.execute(
                    "SELECT * FROM file_mappings WHERE operation_id = ?",
                    (row["id"],),
                )
                mappings = cursor.fetchall()
                operations.append(self._row_to_operation(row, mappings))
            return operations

    def get_undoable(self) -> list[Operation]:
        """Get operations that can still be undone."""
        with self._cursor() as cursor:
            cursor.execute(
                """SELECT * FROM operations
                   WHERE is_undoable = 1 AND is_undone = 0
                   ORDER BY timestamp DESC""",
            )
            operations = []
            for row in cursor.fetchall():
                cursor.execute(
                    "SELECT * FROM file_mappings WHERE operation_id = ?",
                    (row["id"],),
                )
                mappings = cursor.fetchall()
                operations.append(self._row_to_operation(row, mappings))
            return operations

    def mark_undone(self, op_id: int) -> None:
        """Mark an operation as undone."""
        with self._cursor() as cursor:
            cursor.execute("UPDATE operations SET is_undone = 1 WHERE id = ?", (op_id,))
            logger.info(f"Operation #{op_id} marked as undone.")

    def mark_not_undoable(self, op_id: int, reason: str = "") -> None:
        """Mark an operation as no longer undoable."""
        with self._cursor() as cursor:
            cursor.execute(
                "UPDATE operations SET is_undoable = 0, error_message = ? WHERE id = ?",
                (reason, op_id),
            )

    def count(self) -> int:
        with self._cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS cnt FROM operations")
            return int(cursor.fetchone()["cnt"])

    def delete_operation(self, op_id: int) -> bool:
        """Delete a single operation and its file mappings."""
        with self._cursor() as cursor:
            cursor.execute("DELETE FROM file_mappings WHERE operation_id = ?", (op_id,))
            cursor.execute("DELETE FROM operations WHERE id = ?", (op_id,))
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted operation #{op_id} from journal.")
            return deleted

    def clear_all(self) -> int:
        """Delete every operation and its file mappings. Returns count removed."""
        with self._cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM operations")
            count = cursor.fetchone()["cnt"]
            cursor.execute("DELETE FROM file_mappings")
            cursor.execute("DELETE FROM operations")
            if count:
                logger.info(f"Cleared all {count} operations from journal.")
            return count

    def purge_old(self, days: int = AppConstants.UNDO_PURGE_DAYS) -> int:
        """
        Remove operations older than the specified number of days.

        Returns:
            Number of operations purged.
        """
        cutoff = (datetime.now() - timedelta(days=max(1, days))).isoformat()
        with self._cursor() as cursor:
            cursor.execute("SELECT id FROM operations WHERE timestamp < ?", (cutoff,))
            ids = [row["id"] for row in cursor.fetchall()]
            if ids:
                cursor.executemany("DELETE FROM file_mappings WHERE operation_id = ?", [(i,) for i in ids])
                cursor.executemany("DELETE FROM operations WHERE id = ?", [(i,) for i in ids])
            purged = len(ids)
            if purged:
                logger.info(f"Purged {purged} operations older than {days} days.")
            return purged

    def get_stats(self) -> dict[str, int]:
        """Get journal statistics."""
        with self._cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as total FROM operations")
            total = cursor.fetchone()["total"]
            cursor.execute("SELECT COUNT(*) as undoable FROM operations WHERE is_undoable = 1 AND is_undone = 0")
            undoable = cursor.fetchone()["undoable"]
            cursor.execute("SELECT COUNT(*) as undone FROM operations WHERE is_undone = 1")
            undone = cursor.fetchone()["undone"]
            return {"total": total, "undoable": undoable, "undone": undone}

    def export_log(self, output_path: str | Path) -> None:
        """Export operation history to a text file."""
        operations = self.get_recent(limit=10000)
        with open(str(output_path), "w", encoding="utf-8") as f:
            f.write(f"OP(AI)UM Operation Log — Exported {datetime.now().isoformat()}\n")
            f.write("=" * 70 + "\n\n")
            for op in operations:
                status = "UNDONE" if op.is_undone else "ACTIVE"
                f.write(f"[{op.display_datetime}] {op.type_label} — {status}\n")
                f.write(f"  {op.description}\n")
                f.write(f"  Items affected: {op.affected_count}\n")
                if op.file_mappings:
                    for m in op.file_mappings[:10]:
                        f.write(f"    {m.source} -> {m.destination}\n")
                    if len(op.file_mappings) > 10:
                        f.write(f"    ... and {len(op.file_mappings) - 10} more\n")
                f.write("\n")
        logger.info(f"Operation log exported to {output_path}")

    def _row_to_operation(
        self,
        row: sqlite3.Row,
        mapping_rows: list[sqlite3.Row],
    ) -> Operation:
        mappings = [
            FileMapping(
                source=m["source"],
                destination=m["destination"],
                original_name=m["original_name"],
                new_name=m["new_name"],
            )
            for m in mapping_rows
        ]
        return Operation(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            operation_type=OperationType(row["operation_type"]),
            description=row["description"],
            file_mappings=mappings,
            affected_count=row["affected_count"],
            is_undone=bool(row["is_undone"]),
            is_undoable=bool(row["is_undoable"]),
            error_message=row["error_message"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    def close(self) -> None:
        with self._lock:
            if self._connection:
                self._connection.close()
                self._connection = None

    def __del__(self) -> None:
        with suppress(Exception):
            self.close()
