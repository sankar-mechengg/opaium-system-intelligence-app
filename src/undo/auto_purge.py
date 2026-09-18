"""
OP(AI)UM — Auto-Purge Scheduler

Periodically cleans up old operation records from the undo journal.
Default: purge operations older than 2 days.
Runs on a QTimer in the background.
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import QObject, QTimer, Signal

from src.config.constants import AppConstants
from src.undo.backup_store import BackupStore
from src.undo.operation_journal import OperationJournal


class AutoPurge(QObject):
    """
    Background scheduler that periodically purges old undo records.

    Runs every hour (configurable) and removes operations older
    than the configured retention period (default: 2 days).

    Signals:
        purge_completed: Emitted after a purge with count of removed items.
    """

    purge_completed = Signal(int)

    def __init__(
        self,
        journal: OperationJournal,
        purge_days: int = AppConstants.UNDO_PURGE_DAYS,
        check_interval_ms: int = AppConstants.UNDO_PURGE_CHECK_INTERVAL * 1000,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._journal = journal
        self._purge_days = purge_days
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._run_purge)
        self._check_interval = check_interval_ms

    def start(self) -> None:
        """Start the auto-purge scheduler."""
        # Run once immediately
        self._run_purge()
        # Then schedule periodic runs
        self._timer.start(self._check_interval)
        logger.info(
            f"Auto-purge started: every {self._check_interval // 1000}s, "
            f"removing entries older than {self._purge_days} days."
        )

    def stop(self) -> None:
        """Stop the auto-purge scheduler."""
        self._timer.stop()
        logger.info("Auto-purge stopped.")

    def set_purge_days(self, days: int) -> None:
        """Update the purge retention period."""
        self._purge_days = max(1, days)
        logger.info(f"Auto-purge retention updated to {self._purge_days} days.")

    def force_purge(self) -> int:
        """Force an immediate purge and return count."""
        return self._run_purge()

    def _run_purge(self) -> int:
        """Execute the purge."""
        try:
            count = self._journal.purge_old(days=self._purge_days)
            BackupStore().purge_older_than(self._purge_days)
            if count > 0:
                self.purge_completed.emit(count)
                logger.info(f"Auto-purge removed {count} old operation(s).")
            return count
        except Exception as e:
            logger.error(f"Auto-purge error: {e}")
            return 0

    @property
    def is_running(self) -> bool:
        return self._timer.isActive()
