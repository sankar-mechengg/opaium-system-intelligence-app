"""
OP(AI)UM — Native Frameless Window (Windows)

Removes the standard title bar while keeping every native window behaviour:
DWM shadow and rounded corners, Aero Snap / Snap Layouts, Win+Arrow, edge
resizing, drag-to-maximize and the maximize-button snap flyout on Windows 11.

Implementation: keep WS_THICKFRAME/WS_CAPTION styles, answer WM_NCCALCSIZE
with a zero non-client area, and answer WM_NCHITTEST ourselves so the OS
handles moving/resizing (the title bar widget reports which regions count
as caption, buttons or client).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
from typing import Any

from loguru import logger
from PySide6.QtCore import QByteArray, QPoint, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QWidget

# --- Win32 constants -----------------------------------------------------------
WM_NCCALCSIZE = 0x0083
WM_NCHITTEST = 0x0084
WM_NCLBUTTONDOWN = 0x00A1
WM_NCLBUTTONUP = 0x00A2
WM_NCMOUSEMOVE = 0x00A0
WM_NCMOUSELEAVE = 0x02A2
WM_SYSCOMMAND = 0x0112
WM_HOTKEY = 0x0312
WM_DPICHANGED = 0x02E0

HTCLIENT = 1
HTCAPTION = 2
HTMINBUTTON = 8
HTMAXBUTTON = 9
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17
HTCLOSE = 20

GWL_STYLE = -16
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU = 0x00080000
CS_DBLCLKS = 0x0008

SM_CXSIZEFRAME = 32
SM_CXPADDEDBORDER = 92
SC_MAXIMIZE = 0xF030
SC_RESTORE = 0xF120
SC_MINIMIZE = 0xF020

DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2
DWMWA_USE_IMMERSIVE_DARK_MODE = 20


class MARGINS(ctypes.Structure):
    _fields_ = [
        ("cxLeftWidth", ctypes.c_int),
        ("cxRightWidth", ctypes.c_int),
        ("cyTopHeight", ctypes.c_int),
        ("cyBottomHeight", ctypes.c_int),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hWnd", wt.HWND),
        ("message", wt.UINT),
        ("wParam", wt.WPARAM),
        ("lParam", wt.LPARAM),
        ("time", wt.DWORD),
        ("pt", wt.POINT),
    ]


class NCCALCSIZE_PARAMS(ctypes.Structure):
    _fields_ = [("rgrc", wt.RECT * 3), ("lppos", ctypes.c_void_p)]


def _user32() -> Any:
    return ctypes.windll.user32


def _dwm() -> Any:
    return ctypes.windll.dwmapi


class NativeFramelessMixin:
    """
    Mixin for a top-level QWidget/QMainWindow.

    The host must implement:
        hit_test_widget(pos: QPoint) -> int   # returns HT* for a point in window coords
    and call `_init_native_frame()` after the window handle exists (e.g. in showEvent).
    """

    BORDER_PX = 6

    def _init_native_frame(self) -> None:
        if getattr(self, "_native_frame_ready", False):
            return
        hwnd = int(self.winId())  # type: ignore[attr-defined]
        if not hwnd:
            return
        try:
            user32 = _user32()
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            style |= WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU | CS_DBLCLKS
            user32.SetWindowLongW(hwnd, GWL_STYLE, style)

            # Enable the DWM shadow while we own the whole client area.
            margins = MARGINS(-1, -1, -1, -1)
            _dwm().DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))

            # Windows 11 rounded corners (ignored on Windows 10).
            pref = ctypes.c_int(DWMWCP_ROUND)
            _dwm().DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(pref), ctypes.sizeof(pref))

            # Force a frame recalculation.
            SWP_FRAMECHANGED = 0x0020
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOZORDER = 0x0004
            user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER)
            self._native_frame_ready = True
        except Exception as e:
            logger.warning(f"Native frame setup failed: {e}")

    def set_dark_titlebar_hint(self, dark: bool) -> None:
        """Tells DWM the window is dark so the snap flyout / system menu match."""
        try:
            hwnd = int(self.winId())  # type: ignore[attr-defined]
            value = ctypes.c_int(1 if dark else 0)
            _dwm().DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value))
        except Exception:
            pass

    # --- Helpers ---

    @staticmethod
    def _is_maximized(hwnd: int) -> bool:
        try:
            return bool(_user32().IsZoomed(hwnd))
        except Exception:
            return False

    @staticmethod
    def _resize_border(hwnd: int) -> int:
        """Invisible resize border thickness at the window's DPI."""
        try:
            user32 = _user32()
            dpi = user32.GetDpiForWindow(hwnd) if hasattr(user32, "GetDpiForWindow") else 96
            if hasattr(user32, "GetSystemMetricsForDpi"):
                return int(
                    user32.GetSystemMetricsForDpi(SM_CXSIZEFRAME, dpi)
                    + user32.GetSystemMetricsForDpi(SM_CXPADDEDBORDER, dpi)
                )
            return int(user32.GetSystemMetrics(SM_CXSIZEFRAME) + user32.GetSystemMetrics(SM_CXPADDEDBORDER))
        except Exception:
            return 8

    def _hit_test_borders(self, hwnd: int, global_pos: QPoint) -> int | None:
        if self._is_maximized(hwnd) or not getattr(self, "_resize_enabled", True):
            return None
        fg = self.frameGeometry()  # type: ignore[attr-defined]
        x, y = global_pos.x(), global_pos.y()
        b = self.BORDER_PX
        left = x - fg.left() < b
        right = fg.right() - x < b
        top = y - fg.top() < b
        bottom = fg.bottom() - y < b
        if top and left:
            return HTTOPLEFT
        if top and right:
            return HTTOPRIGHT
        if bottom and left:
            return HTBOTTOMLEFT
        if bottom and right:
            return HTBOTTOMRIGHT
        if left:
            return HTLEFT
        if right:
            return HTRIGHT
        if top:
            return HTTOP
        if bottom:
            return HTBOTTOM
        return None

    # --- Qt entry point ---

    def native_event(self, event_type: QByteArray, message: int) -> tuple[bool, int] | None:
        """Call from nativeEvent(); returns (handled, result) or None to fall through."""
        try:
            msg = MSG.from_address(int(message))
        except Exception:
            return None
        if not msg.hWnd:
            return None
        hwnd = int(msg.hWnd)

        if msg.message == WM_NCCALCSIZE:
            if not msg.wParam:
                return True, 0
            params = ctypes.cast(msg.lParam, ctypes.POINTER(NCCALCSIZE_PARAMS)).contents
            rect = params.rgrc[0]
            if self._is_maximized(hwnd):
                # A maximized window is positioned so its invisible frame hangs
                # off-screen; pull the client rect back onto the monitor.
                t = self._resize_border(hwnd)
                rect.top += t
                rect.left += t
                rect.right -= t
                rect.bottom -= t
            return True, 0

        if msg.message == WM_NCHITTEST:
            global_pos = QCursor.pos()
            border = self._hit_test_borders(hwnd, global_pos)
            if border is not None:
                return True, border
            local = self.mapFromGlobal(global_pos)  # type: ignore[attr-defined]
            return True, int(self.hit_test_widget(local))  # type: ignore[attr-defined]

        if msg.message in (WM_NCLBUTTONDOWN, WM_NCLBUTTONUP, WM_NCMOUSEMOVE, WM_NCMOUSELEAVE):
            ht = int(msg.wParam)
            if msg.message == WM_NCMOUSEMOVE:
                self.on_caption_button_hover(ht if ht in (HTMINBUTTON, HTMAXBUTTON, HTCLOSE) else 0)  # type: ignore[attr-defined]
                if ht in (HTMINBUTTON, HTMAXBUTTON, HTCLOSE):
                    return True, 0
                return None
            if msg.message == WM_NCMOUSELEAVE:
                self.on_caption_button_hover(0)  # type: ignore[attr-defined]
                return None
            if ht in (HTMINBUTTON, HTMAXBUTTON, HTCLOSE):
                if msg.message == WM_NCLBUTTONUP:
                    self.on_caption_button_click(ht)  # type: ignore[attr-defined]
                return True, 0
            return None

        return None

    # Hooks with default no-op implementations (override in the window).
    def on_caption_button_hover(self, ht: int) -> None:  # pragma: no cover - UI hook
        pass

    def on_caption_button_click(self, ht: int) -> None:  # pragma: no cover - UI hook
        pass

    def hit_test_widget(self, pos: QPoint) -> int:  # pragma: no cover - UI hook
        return HTCLIENT


def system_menu_command(widget: QWidget, command: int) -> None:
    """Send a WM_SYSCOMMAND (minimize/maximize/restore) so DWM animates it natively."""
    try:
        hwnd = int(widget.winId())
        _user32().PostMessageW(hwnd, WM_SYSCOMMAND, command, 0)
    except Exception:
        if command == SC_MAXIMIZE:
            widget.showMaximized()
        elif command == SC_RESTORE:
            widget.showNormal()
        elif command == SC_MINIMIZE:
            widget.showMinimized()


__all__ = [
    "HTCAPTION",
    "HTCLIENT",
    "HTCLOSE",
    "HTMAXBUTTON",
    "HTMINBUTTON",
    "SC_MAXIMIZE",
    "SC_MINIMIZE",
    "SC_RESTORE",
    "WM_HOTKEY",
    "NativeFramelessMixin",
    "system_menu_command",
    "Qt",
]
