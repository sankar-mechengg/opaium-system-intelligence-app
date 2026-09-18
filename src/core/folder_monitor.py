"""
OP(AI)UM — Directory Watcher

Watches the folder currently open in the explorer with `watchdog` and emits a
debounced `changed` signal when files are created, deleted, moved or
modified, so the view stays live without polling.
"""

from __future__ import annotations

import contextlib
from typing import Any

from loguru import logger
from PySide6.QtCore import QObject, QTimer, Signal


class DirectoryWatcher(QObject):
    """
    Signals:
        changed(str): the watched directory's contents changed (debounced).
        unavailable(str): watching failed (e.g. watchdog missing or access denied).
    """

    changed = Signal(str)
    unavailable = Signal(str)

    DEBOUNCE_MS = 600

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._observer: Any | None = None
        self._watch: Any | None = None
        self._path: str = ""
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(self.DEBOUNCE_MS)
        self._debounce.timeout.connect(self._emit_changed)
        # Signal used to hop from the watchdog thread onto the Qt thread.
        self._pending_changed.connect(self._on_fs_event_main)

    _pending_changed = Signal(str)

    @property
    def path(self) -> str:
        return self._path

    def watch(self, path: str) -> None:
        """Start watching `path` (replaces any previous watch)."""
        if path == self._path and self._watch is not None:
            return
        self.stop()
        if not path:
            return
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError:
            self.unavailable.emit("watchdog is not installed")
            return

        watcher = self

        class _Handler(FileSystemEventHandler):
            def on_any_event(self, event: Any) -> None:  # noqa: D401 - watchdog API
                if getattr(event, "is_directory", False) and event.event_type == "modified":
                    return  # directory mtime churn; real changes come as created/deleted/moved
                watcher._pending_changed.emit(path)

        try:
            if self._observer is None:
                self._observer = Observer()
                self._observer.daemon = True
                self._observer.start()
            self._watch = self._observer.schedule(_Handler(), path, recursive=False)
            self._path = path
            logger.debug(f"Watching folder: {path}")
        except Exception as e:
            logger.debug(f"Cannot watch {path}: {e}")
            self._watch = None
            self._path = ""
            self.unavailable.emit(str(e))

    def stop(self) -> None:
        if self._observer is not None and self._watch is not None:
            with contextlib.suppress(Exception):
                self._observer.unschedule(self._watch)
        self._watch = None
        self._path = ""
        self._debounce.stop()

    def shutdown(self) -> None:
        self.stop()
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=1.0)
            except Exception:
                pass
            self._observer = None

    def _on_fs_event_main(self, path: str) -> None:
        if path != self._path:
            return
        self._debounce.start()

    def _emit_changed(self) -> None:
        if self._path:
            self.changed.emit(self._path)
