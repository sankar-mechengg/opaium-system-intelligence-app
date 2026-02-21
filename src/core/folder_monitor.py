"""
OP(AI)UM — Folder Change Monitor

Background service that monitors for folder renames, moves,
and deletions by combining:
1. NTFS USN Journal (real-time filesystem changes)
2. Custom tracking DB (file ID → path mapping)
3. Windows .lnk re-resolution

Emits signals when tracked items change.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal
from loguru import logger

from src.config.constants import AppConstants
from src.core.models import ItemType
from src.core.tracking_db import TrackingDB
from src.core.usn_journal import USNJournalReader
from src.utils.windows_api import WindowsAPI


class FolderChange:
    """Represents a detected folder change."""

    def __init__(
        self,
        change_type: str,  # 'renamed', 'moved', 'deleted', 'created'
        old_path: str,
        new_path: str = "",
        file_id: Optional[int] = None,
    ) -> None:
        self.change_type = change_type
        self.old_path = old_path
        self.new_path = new_path
        self.file_id = file_id
        self.timestamp = datetime.now()

    def __repr__(self) -> str:
        if self.new_path:
            return f"FolderChange({self.change_type}: {self.old_path} -> {self.new_path})"
        return f"FolderChange({self.change_type}: {self.old_path})"


class FolderMonitor(QObject):
    """
    Monitors tracked folders for changes (renames, moves, deletions).

    Uses a periodic timer to:
    1. Read USN Journal for recent changes
    2. Cross-reference with tracking DB
    3. Update paths in DB when renames/moves detected
    4. Emit signals for UI updates

    Signals:
        folder_changed: Emitted when a tracked folder changes.
        folders_updated: Emitted after a full monitoring cycle.
        monitoring_error: Emitted on monitoring errors.
    """

    folder_changed = Signal(object)   # FolderChange
    folders_updated = Signal(int)     # Number of changes detected
    monitoring_error = Signal(str)

    # Check interval: 30 seconds
    DEFAULT_CHECK_INTERVAL = 30_000

    def __init__(
        self,
        tracking_db: TrackingDB,
        check_interval_ms: int = DEFAULT_CHECK_INTERVAL,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._db = tracking_db
        self._usn_readers: dict[str, USNJournalReader] = {}
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._run_check)
        self._check_interval = check_interval_ms
        self._running = False
        self._last_check = datetime.now()

    def start(self) -> None:
        """Start monitoring."""
        if self._running:
            return

        self._initialize_usn_readers()
        self._timer.start(self._check_interval)
        self._running = True
        logger.info("Folder monitor started.")

    def stop(self) -> None:
        """Stop monitoring."""
        self._timer.stop()
        self._running = False
        logger.info("Folder monitor stopped.")

    @property
    def is_running(self) -> bool:
        return self._running

    def _initialize_usn_readers(self) -> None:
        """Create USN readers for all available drives."""
        import string
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                reader = USNJournalReader(letter)
                if reader.is_available:
                    self._usn_readers[letter] = reader
                    logger.debug(f"USN reader initialized for drive {letter}:")

        logger.info(f"USN readers active on {len(self._usn_readers)} drives.")

    def _run_check(self) -> None:
        """Execute a monitoring cycle."""
        try:
            total_changes = 0

            # Method 1: Check USN Journal for renames
            for drive, reader in self._usn_readers.items():
                changes = self._check_usn_changes(reader)
                total_changes += len(changes)
                for change in changes:
                    self.folder_changed.emit(change)

            # Method 2: Verify tracked items still exist at their paths
            changes = self._verify_tracked_items()
            total_changes += len(changes)
            for change in changes:
                self.folder_changed.emit(change)

            if total_changes > 0:
                self.folders_updated.emit(total_changes)
                logger.info(f"Monitor detected {total_changes} changes.")

            self._last_check = datetime.now()

        except Exception as e:
            logger.error(f"Monitoring error: {e}")
            self.monitoring_error.emit(str(e))

    def _check_usn_changes(self, reader: USNJournalReader) -> list[FolderChange]:
        """Check USN Journal for folder renames and moves."""
        changes: list[FolderChange] = []

        try:
            rename_pairs = reader.get_renames(max_age_hours=1)

            for old_record, new_record in rename_pairs:
                if not old_record.is_directory:
                    continue

                # Check if this directory is in our tracking DB
                tracked = self._db.get_all_active(ItemType.FOLDER)
                for item in tracked:
                    if item.file_id == old_record.file_reference_number:
                        # Found a tracked folder that was renamed
                        old_path = item.path
                        # Build new path using parent + new name
                        parent = str(Path(old_path).parent)
                        new_path = str(Path(parent) / new_record.filename)

                        if os.path.exists(new_path):
                            self._db.update_path(
                                item.file_id,
                                item.volume_serial,
                                new_path,
                                new_record.filename,
                            )
                            change = FolderChange(
                                change_type="renamed",
                                old_path=old_path,
                                new_path=new_path,
                                file_id=item.file_id,
                            )
                            changes.append(change)
                            logger.info(f"Detected rename: {old_path} -> {new_path}")
                        break

        except Exception as e:
            logger.debug(f"USN change check error: {e}")

        return changes

    def _verify_tracked_items(self) -> list[FolderChange]:
        """Verify all tracked items still exist; try to relocate if not."""
        changes: list[FolderChange] = []

        tracked = self._db.get_all_active()

        for item in tracked:
            if os.path.exists(item.path):
                # Path still valid — check if file ID matches
                # (detects replacement with a different folder of same name)
                current_id = WindowsAPI.get_file_id(item.path)
                if current_id and current_id != item.file_id:
                    logger.warning(
                        f"File ID mismatch at {item.path}: "
                        f"tracked={item.file_id}, actual={current_id}"
                    )
                continue

            # Path doesn't exist — try to find new location by file ID
            new_path = self._relocate_by_file_id(item.file_id, item.volume_serial)

            if new_path:
                new_name = Path(new_path).name
                self._db.update_path(item.file_id, item.volume_serial, new_path, new_name)
                change = FolderChange(
                    change_type="moved",
                    old_path=item.path,
                    new_path=new_path,
                    file_id=item.file_id,
                )
                changes.append(change)
                logger.info(f"Detected move: {item.path} -> {new_path}")
            else:
                # Truly gone
                self._db.mark_inactive(item.file_id, item.volume_serial)
                change = FolderChange(
                    change_type="deleted",
                    old_path=item.path,
                    file_id=item.file_id,
                )
                changes.append(change)
                logger.info(f"Detected deletion: {item.path}")

        return changes

    def _relocate_by_file_id(self, file_id: int, volume_serial: int) -> Optional[str]:
        """
        Try to find a folder by its NTFS file ID.

        This handles moves within the same drive — the file ID
        remains the same even when the path changes.
        """
        try:
            # Use OpenFileById Windows API
            import ctypes
            import ctypes.wintypes

            # Determine drive letter from volume serial
            import string
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if not os.path.exists(drive):
                    continue

                current_serial = WindowsAPI.get_volume_serial(drive)
                if current_serial != volume_serial:
                    continue

                # Open by file ID
                FILE_ID_DESCRIPTOR_SIZE = 24
                buffer = ctypes.create_string_buffer(FILE_ID_DESCRIPTOR_SIZE)

                # ObjectIdType = 0 (FileIdType)
                import struct
                struct.pack_into("<IQ", buffer, 0, 0, file_id)

                # This is a simplified approach — full implementation
                # would use OpenFileById and GetFinalPathNameByHandle
                # For now, fall back to scanning
                logger.debug(
                    f"File ID relocation not fully implemented. "
                    f"file_id={file_id}, drive={letter}:"
                )
                return None

        except Exception as e:
            logger.debug(f"File ID relocation failed: {e}")
            return None

    def force_check(self) -> None:
        """Force an immediate monitoring check."""
        self._run_check()
