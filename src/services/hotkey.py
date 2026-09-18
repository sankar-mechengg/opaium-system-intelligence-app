"""
OP(AI)UM — Global Hotkey

Registers a system-wide shortcut (default Ctrl+Shift+Space) with
RegisterHotKey so the window can be summoned from anywhere. The owning
window forwards WM_HOTKEY from its nativeEvent to `handle_native()`.
"""

from __future__ import annotations

import ctypes

from loguru import logger
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QWidget

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

# Qt key -> Win32 virtual key for non-letter keys
_VK_MAP: dict[str, int] = {
    "Space": 0x20,
    "Tab": 0x09,
    "Return": 0x0D,
    "Enter": 0x0D,
    "Esc": 0x1B,
    "Escape": 0x1B,
    "Backspace": 0x08,
    "Ins": 0x2D,
    "Del": 0x2E,
    "Home": 0x24,
    "End": 0x23,
    "PgUp": 0x21,
    "PgDown": 0x22,
    "Left": 0x25,
    "Up": 0x26,
    "Right": 0x27,
    "Down": 0x28,
    "`": 0xC0,
    "-": 0xBD,
    "=": 0xBB,
    "[": 0xDB,
    "]": 0xDD,
    "\\": 0xDC,
    ";": 0xBA,
    "'": 0xDE,
    ",": 0xBC,
    ".": 0xBE,
    "/": 0xBF,
}


def parse_hotkey(text: str) -> tuple[int, int] | None:
    """Convert 'Ctrl+Shift+Space' into (modifiers, virtual_key)."""
    seq = QKeySequence(text)
    if seq.isEmpty():
        return None
    portable = seq.toString(QKeySequence.SequenceFormat.PortableText)
    parts = [p for p in portable.split("+") if p]
    if not parts:
        return None
    key = parts[-1]
    mods = 0
    for mod in parts[:-1]:
        m = mod.lower()
        if m == "ctrl":
            mods |= MOD_CONTROL
        elif m == "shift":
            mods |= MOD_SHIFT
        elif m == "alt":
            mods |= MOD_ALT
        elif m == "meta":
            mods |= MOD_WIN
    if not mods:
        return None  # a bare key would hijack normal typing

    if len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    elif key.startswith("F") and key[1:].isdigit():
        vk = 0x70 + int(key[1:]) - 1
    else:
        vk = _VK_MAP.get(key, 0)
    if not vk:
        return None
    return mods | MOD_NOREPEAT, vk


class GlobalHotkey(QObject):
    """
    Signals:
        activated(): the registered hotkey was pressed.
    """

    activated = Signal()
    HOTKEY_ID = 0x0A1

    def __init__(self, window: QWidget, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._window = window
        self._registered = False
        self._sequence = ""

    @property
    def is_registered(self) -> bool:
        return self._registered

    @property
    def sequence(self) -> str:
        return self._sequence

    def register(self, sequence: str) -> bool:
        self.unregister()
        parsed = parse_hotkey(sequence)
        if parsed is None:
            logger.warning(f"Invalid global hotkey: {sequence!r}")
            return False
        mods, vk = parsed
        try:
            hwnd = int(self._window.winId())
            ok = bool(ctypes.windll.user32.RegisterHotKey(hwnd, self.HOTKEY_ID, mods, vk))
        except Exception as e:
            logger.warning(f"RegisterHotKey failed: {e}")
            ok = False
        self._registered = ok
        self._sequence = sequence if ok else ""
        if ok:
            logger.info(f"Global hotkey registered: {sequence}")
        else:
            logger.warning(f"Global hotkey {sequence} is unavailable (already taken?).")
        return ok

    def unregister(self) -> None:
        if not self._registered:
            return
        try:
            hwnd = int(self._window.winId())
            ctypes.windll.user32.UnregisterHotKey(hwnd, self.HOTKEY_ID)
        except Exception:
            pass
        self._registered = False
        self._sequence = ""

    def handle_native(self, message: int, w_param: int) -> bool:
        """Return True when the message was our WM_HOTKEY."""
        if message == 0x0312 and int(w_param) == self.HOTKEY_ID:
            self.activated.emit()
            return True
        return False
