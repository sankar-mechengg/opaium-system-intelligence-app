"""
OP(AI)UM — Content Backup Store

Before the AI overwrites or appends to an existing file, a copy of the
original is placed in %APPDATA%/OPAIUM/backups so the change can be undone.
Backups are pruned together with the undo journal.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import time
import uuid
from pathlib import Path

from loguru import logger

from src.config.constants import AppConstants


class BackupStore:
    """File-content backups used by write/append undo."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or AppConstants.BACKUP_DIR

    @property
    def root(self) -> Path:
        return self._root

    def backup(self, path: str | Path) -> str | None:
        """
        Copy `path` into the store. Returns the backup path, or None when the
        file does not exist, is too large, or copying failed.
        """
        src = Path(path)
        try:
            if not src.is_file():
                return None
            size = src.stat().st_size
            if size > AppConstants.MAX_BACKUP_FILE_BYTES:
                logger.info(f"Skipping backup of {src.name}: {size} bytes exceeds limit.")
                return None
            self._root.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            dest = self._root / f"{stamp}_{uuid.uuid4().hex[:8]}_{src.name}"
            shutil.copy2(src, dest)
            logger.debug(f"Backed up {src} -> {dest}")
            return str(dest)
        except Exception as e:
            logger.warning(f"Backup failed for {src}: {e}")
            return None

    @staticmethod
    def restore(backup_path: str | Path, target: str | Path) -> bool:
        """Copy a backup back over `target`."""
        try:
            b = Path(backup_path)
            if not b.is_file():
                logger.warning(f"Backup missing: {b}")
                return False
            t = Path(target)
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(b, t)
            logger.info(f"Restored {t} from backup {b.name}")
            return True
        except Exception as e:
            logger.error(f"Restore failed for {target}: {e}")
            return False

    def purge_older_than(self, days: int) -> int:
        """Delete backups older than `days`. Returns the number removed."""
        removed = 0
        cutoff = time.time() - max(1, days) * 86400
        try:
            if not self._root.exists():
                return 0
            for entry in self._root.iterdir():
                try:
                    if entry.is_file() and entry.stat().st_mtime < cutoff:
                        entry.unlink()
                        removed += 1
                except OSError:
                    continue
        except Exception as e:
            logger.debug(f"Backup purge error: {e}")
        if removed:
            logger.info(f"Purged {removed} old content backup(s).")
        return removed

    def total_size(self) -> int:
        total = 0
        try:
            for entry in self._root.iterdir():
                if entry.is_file():
                    total += entry.stat().st_size
        except OSError:
            pass
        return total

    @staticmethod
    def delete_backup(backup_path: str | None) -> None:
        if not backup_path:
            return
        with contextlib.suppress(OSError):
            os.remove(backup_path)
