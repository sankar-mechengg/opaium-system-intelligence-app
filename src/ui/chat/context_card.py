"""
OP(AI)UM — Chat Context Card

A compact inline card shown in the chat when user asks AI
about a specific file or folder from the context menu.
Supports right-click context menu (all card options except Ask AI).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QVBoxLayout,
)

from src.ui.chat.message_bubble import StyledBubbleFrame


class ChatContextCard(QFrame):
    """Compact card showing the file/folder context for an AI question."""

    def __init__(self, path: str, parent=None) -> None:
        super().__init__(parent)
        self._path = path
        self.setObjectName("chatContextCard")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 2, 8, 2)

        outer.addStretch()

        card = StyledBubbleFrame()
        card.setObjectName("contextCardInner")
        card.setMaximumWidth(400)
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(10, 6, 12, 6)
        card_layout.setSpacing(8)

        # Icon
        icon_label = QLabel()
        icon_label.setObjectName("contextCardIcon")
        path_obj = Path(self._path)
        is_folder = path_obj.is_dir()

        try:
            from src.utils.icon_provider import IconProvider

            provider = IconProvider()
            if is_folder:
                icon = provider.get_folder_icon(self._path)
            else:
                icon = provider.get_file_icon(self._path)
            pixmap = icon.pixmap(QSize(24, 24))
            icon_label.setPixmap(pixmap)
        except Exception:
            icon_label.setText("📁" if is_folder else "📄")

        icon_label.setFixedSize(24, 24)
        card_layout.addWidget(icon_label)

        # Info column
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(1)

        name_label = QLabel(path_obj.name)
        name_label.setObjectName("contextCardName")
        name_font = QFont()
        name_font.setPointSize(9)
        name_font.setBold(True)
        name_label.setFont(name_font)
        info_layout.addWidget(name_label)

        parent_text = str(path_obj.parent)
        if len(parent_text) > 50:
            parent_text = "..." + parent_text[-47:]
        parent_label = QLabel(parent_text)
        parent_label.setObjectName("contextCardPath")
        path_font = QFont()
        path_font.setPointSize(7)
        parent_label.setFont(path_font)
        info_layout.addWidget(parent_label)

        card_layout.addLayout(info_layout, stretch=1)

        # Type badge
        type_text = "Folder" if is_folder else path_obj.suffix.upper().lstrip(".")
        type_label = QLabel(type_text)
        type_label.setObjectName("contextCardType")
        type_font = QFont()
        type_font.setPointSize(7)
        type_label.setFont(type_font)
        type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(type_label)

        outer.addWidget(card)

    def _on_context_menu(self, pos) -> None:
        """Show context menu (same as explorer cards, minus Ask AI)."""
        path_obj = Path(self._path)
        is_folder = path_obj.is_dir()
        name = path_obj.name

        menu = QMenu(self)

        if is_folder:
            menu.addAction("Open in Explorer", lambda: subprocess.Popen(["explorer", self._path]))
            menu.addAction(
                "Open in Terminal",
                lambda: subprocess.Popen(
                    ["cmd", "/k", f"cd /d {self._path}"],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                ),
            )
        else:
            menu.addAction("Open", lambda: os.startfile(self._path))  # type: ignore
            menu.addAction(
                "Open Containing Folder",
                lambda: subprocess.Popen(["explorer", "/select,", self._path]),
            )

        menu.addSeparator()
        menu.addAction("Copy Path", lambda: self._copy_to_clipboard(self._path))
        menu.addAction("Copy Name", lambda: self._copy_to_clipboard(name))
        menu.addSeparator()

        if not is_folder:
            menu.addAction("Delete", lambda: self._delete_file())

        menu.addAction("Properties", lambda: self._show_properties())
        menu.exec(self.mapToGlobal(pos))

    @staticmethod
    def _copy_to_clipboard(text: str) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    def _delete_file(self) -> None:
        try:
            from send2trash import send2trash

            send2trash(self._path)
        except Exception:
            import shutil

            if Path(self._path).is_dir():
                shutil.rmtree(self._path)
            else:
                os.remove(self._path)

    def _show_properties(self) -> None:
        try:
            import ctypes
            from ctypes import wintypes

            SEE_MASK_INVOKEIDLIST = 0x0000000C

            class SHELLEXECUTEINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("fMask", ctypes.c_ulong),
                    ("hwnd", wintypes.HANDLE),
                    ("lpVerb", ctypes.c_wchar_p),
                    ("lpFile", ctypes.c_wchar_p),
                    ("lpParameters", ctypes.c_wchar_p),
                    ("lpDirectory", ctypes.c_wchar_p),
                    ("nShow", ctypes.c_int),
                    ("hInstApp", wintypes.HINSTANCE),
                    ("lpIDList", ctypes.c_void_p),
                    ("lpClass", ctypes.c_wchar_p),
                    ("hkeyClass", wintypes.HKEY),
                    ("dwHotKey", wintypes.DWORD),
                    ("hIcon", wintypes.HANDLE),
                    ("hProcess", wintypes.HANDLE),
                ]

            sei = SHELLEXECUTEINFO()
            sei.cbSize = ctypes.sizeof(SHELLEXECUTEINFO)
            sei.fMask = SEE_MASK_INVOKEIDLIST
            sei.lpVerb = "properties"
            sei.lpFile = self._path
            sei.nShow = 1
            ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei))
        except Exception:
            pass
