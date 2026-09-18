"""
OP(AI)UM — Update Checker

Once a day (configurable) asks the GitHub Releases API for the latest tag and
notifies the UI when a newer version is available. Never downloads anything.
"""

from __future__ import annotations

import contextlib
import json
import re
import urllib.request
from datetime import datetime, timedelta
from typing import Any

from loguru import logger
from PySide6.QtCore import QObject, Signal

from src.config.config_manager import ConfigManager
from src.config.constants import AppConstants
from src.utils.thread_pool import ThreadPoolManager, Worker

_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def parse_version(text: str) -> tuple[int, int, int]:
    m = _VERSION_RE.search(text or "")
    if not m:
        return (0, 0, 0)
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


class UpdateChecker(QObject):
    """
    Signals:
        update_available(str, str, str): version, release page URL, release notes (markdown).
        check_finished(bool, str): success flag, status message.
    """

    update_available = Signal(str, str, str)
    check_finished = Signal(bool, str)

    def __init__(self, config: ConfigManager, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._busy = False

    def should_check(self) -> bool:
        settings = self._config.settings.updates
        if not settings.check_for_updates:
            return False
        if not settings.last_check_iso:
            return True
        try:
            last = datetime.fromisoformat(settings.last_check_iso)
        except ValueError:
            return True
        return datetime.now() - last >= timedelta(hours=AppConstants.UPDATE_CHECK_INTERVAL_HOURS)

    def check(self, force: bool = False) -> None:
        if self._busy:
            return
        if not force and not self.should_check():
            return
        self._busy = True
        worker = Worker(self._fetch_latest)
        worker.signals.result.connect(self._on_result)
        worker.signals.error.connect(self._on_error)
        worker.signals.finished.connect(self._on_done)
        ThreadPoolManager.run(worker)

    @staticmethod
    def _fetch_latest() -> dict[str, Any]:
        req = urllib.request.Request(
            AppConstants.RELEASES_API_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"OPAIUM/{AppConstants.APP_VERSION}",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 - fixed https URL
            data = json.loads(resp.read().decode("utf-8"))
        return {
            "tag": str(data.get("tag_name", "")),
            "url": str(data.get("html_url", AppConstants.RELEASES_URL)),
            "notes": str(data.get("body", "") or ""),
            "prerelease": bool(data.get("prerelease", False)),
        }

    def _on_result(self, data: object) -> None:
        info = data if isinstance(data, dict) else {}
        self._config.settings.updates.last_check_iso = datetime.now().isoformat()
        with contextlib.suppress(Exception):
            self._config.save()

        tag = str(info.get("tag", ""))
        latest = parse_version(tag)
        current = parse_version(AppConstants.APP_VERSION)
        skipped = parse_version(self._config.settings.updates.skipped_version)
        if info.get("prerelease"):
            self.check_finished.emit(True, f"Latest release is a pre-release ({tag}).")
            return
        if latest > current and latest != skipped:
            logger.info(f"Update available: {tag} (current {AppConstants.APP_VERSION})")
            self.update_available.emit(tag.lstrip("v"), str(info.get("url")), str(info.get("notes")))
            self.check_finished.emit(True, f"Update {tag} available.")
        else:
            self.check_finished.emit(True, "You are on the latest version.")

    def _on_error(self, message: str) -> None:
        logger.debug(f"Update check failed: {message}")
        self.check_finished.emit(False, f"Update check failed: {message}")

    def _on_done(self) -> None:
        self._busy = False

    def skip_version(self, version: str) -> None:
        self._config.settings.updates.skipped_version = version
        self._config.save()
