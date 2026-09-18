"""
OP(AI)UM — Idle Monitor

Tracks user input inside the app (and system-wide via GetLastInputInfo) and
emits `idle_timeout` after the configured number of minutes without activity,
which the app uses to lock itself.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import time

from loguru import logger
from PySide6.QtCore import QEvent, QObject, QTimer, Signal


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]


def system_idle_seconds() -> float:
    """Seconds since the last keyboard/mouse input anywhere on the system."""
    try:
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            tick = ctypes.windll.kernel32.GetTickCount()
            return max(0.0, (tick - info.dwTime) / 1000.0)
    except Exception:
        pass
    return 0.0


class IdleMonitor(QObject):
    """
    Signals:
        idle_timeout(): emitted once when the idle threshold is crossed.
    """

    idle_timeout = Signal()

    _ACTIVITY_EVENTS = {
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseMove,
        QEvent.Type.KeyPress,
        QEvent.Type.Wheel,
        QEvent.Type.TouchBegin,
        QEvent.Type.FocusIn,
    }

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._minutes = 0
        self._last_activity = time.monotonic()
        self._fired = False
        self._timer = QTimer(self)
        self._timer.setInterval(15_000)
        self._timer.timeout.connect(self._tick)

    def set_minutes(self, minutes: int) -> None:
        self._minutes = max(0, int(minutes))
        self._last_activity = time.monotonic()
        self._fired = False
        if self._minutes > 0:
            if not self._timer.isActive():
                self._timer.start()
            logger.info(f"Idle auto-lock armed: {self._minutes} min")
        else:
            self._timer.stop()

    def reset(self) -> None:
        self._last_activity = time.monotonic()
        self._fired = False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in self._ACTIVITY_EVENTS:
            self._last_activity = time.monotonic()
            self._fired = False
        return False

    def _tick(self) -> None:
        if self._minutes <= 0 or self._fired:
            return
        idle_app = time.monotonic() - self._last_activity
        idle_sys = system_idle_seconds()
        idle = min(idle_app, idle_sys) if idle_sys > 0 else idle_app
        if idle >= self._minutes * 60:
            self._fired = True
            logger.info("Idle threshold reached — requesting lock.")
            self.idle_timeout.emit()
