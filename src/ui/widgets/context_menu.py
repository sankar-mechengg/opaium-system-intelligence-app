"""
OP(AI)UM — Context Menu Builder

Builds right-click context menus for files, folders and empty space in the
explorer. Native file operations are emitted as actions and executed by the
explorer panel (so they are journaled and undoable); AI questions go to chat.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QInputDialog, QMenu, QWidget

from src.utils.icon_provider import SvgIcons

FOLDER_AI_ACTIONS = [
    ("Count files", "How many files are in {name}?"),
    ("Analyze size", "What's the total size of {name} and what takes the most space?"),
    ("Find duplicates", "Find duplicate files in {name}"),
    ("Find large files", "Find the largest files in {name}"),
    ("File type summary", "What types of files are in {name}?"),
    ("Find old files", "Which files in {name} have not been modified for over a year?"),
    ("Organize by type", "Organize the files in {name} into folders by type"),
    ("Clean empty folders", "Find and remove empty folders inside {name}"),
]

FILE_AI_ACTIONS = [
    ("Summarize this file", "Read {name} and give me a concise summary"),
    ("Get file info", "Tell me about the file {name}"),
    ("Find similar files", "Find files similar to {name} in the same folder"),
    ("Suggest a better name", "Suggest a clearer file name for {name} based on its contents"),
]


class ContextMenuBuilder(QObject):
    """
    Signals:
        action_triggered(str, str): (action_name, item_path)
            actions: open, reveal, terminal, copy_path, copy_name, rename, delete,
                     new_folder, open_with, properties, browse
        ask_ai(str, str): (question, item_path)
    """

    action_triggered = Signal(str, str)
    ask_ai = Signal(str, str)

    def _icon(self, name: str, role: str = "icon"):  # type: ignore[no-untyped-def]
        return SvgIcons.themed(name, role, 16)

    def build_folder_menu(self, folder_path: str, parent: QWidget, browsable: bool = True) -> QMenu:
        """Build context menu for a folder item."""
        menu = QMenu(parent)
        menu.setObjectName("contextMenu")
        name = Path(folder_path).name or folder_path

        if browsable:
            menu.addAction(
                self._icon("folder-open"), "Open in OP(AI)UM", lambda: self.action_triggered.emit("browse", folder_path)
            )
        menu.addAction(self._icon("external"), "Open in Windows Explorer", lambda: self._open_in_explorer(folder_path))
        menu.addAction(self._icon("terminal"), "Open in Terminal", lambda: self._open_in_terminal(folder_path))

        menu.addSeparator()
        menu.addAction(self._icon("copy"), "Copy Path", lambda: self._copy_to_clipboard(folder_path))
        menu.addAction(self._icon("copy"), "Copy Name", lambda: self._copy_to_clipboard(name))

        menu.addSeparator()
        ai_menu = menu.addMenu(self._icon("sparkle", "accent"), "Ask AI")
        for label, template in FOLDER_AI_ACTIONS:
            question = template.format(name=name)
            ai_menu.addAction(label, lambda checked=False, q=question, p=folder_path: self.ask_ai.emit(q, p))
        ai_menu.addSeparator()
        ai_menu.addAction("Custom question…", lambda: self._ask_custom_question(folder_path))

        menu.addSeparator()
        menu.addAction(
            self._icon("folder-plus"),
            "New Folder Inside…",
            lambda: self.action_triggered.emit("new_folder", folder_path),
        )
        menu.addAction(self._icon("rename"), "Rename\tF2", lambda: self.action_triggered.emit("rename", folder_path))
        menu.addAction(
            self._icon("trash", "red"),
            "Delete to Recycle Bin\tDel",
            lambda: self.action_triggered.emit("delete", folder_path),
        )

        menu.addSeparator()
        menu.addAction(
            self._icon("properties"), "Properties", lambda: self.action_triggered.emit("properties", folder_path)
        )
        return menu

    def build_file_menu(self, file_path: str, parent: QWidget) -> QMenu:
        """Build context menu for a file item."""
        menu = QMenu(parent)
        menu.setObjectName("contextMenu")
        name = Path(file_path).name

        menu.addAction(self._icon("external"), "Open", lambda: self._open_file(file_path))
        menu.addAction(
            self._icon("open-with"), "Open With…", lambda: self.action_triggered.emit("open_with", file_path)
        )
        menu.addAction(
            self._icon("folder-open"),
            "Show in Windows Explorer",
            lambda: self._open_in_explorer(str(Path(file_path).parent), select=file_path),
        )

        menu.addSeparator()
        menu.addAction(self._icon("copy"), "Copy Path", lambda: self._copy_to_clipboard(file_path))
        menu.addAction(self._icon("copy"), "Copy Name", lambda: self._copy_to_clipboard(name))

        menu.addSeparator()
        ai_menu = menu.addMenu(self._icon("sparkle", "accent"), "Ask AI")
        for label, template in FILE_AI_ACTIONS:
            question = template.format(name=name)
            ai_menu.addAction(label, lambda checked=False, q=question, p=file_path: self.ask_ai.emit(q, p))
        ai_menu.addSeparator()
        ai_menu.addAction("Custom question…", lambda: self._ask_custom_question(file_path))

        menu.addSeparator()
        menu.addAction(self._icon("rename"), "Rename\tF2", lambda: self.action_triggered.emit("rename", file_path))
        menu.addAction(
            self._icon("trash", "red"),
            "Delete to Recycle Bin\tDel",
            lambda: self.action_triggered.emit("delete", file_path),
        )

        menu.addSeparator()
        menu.addAction(
            self._icon("properties"), "Properties", lambda: self.action_triggered.emit("properties", file_path)
        )
        return menu

    def build_background_menu(self, folder_path: str, parent: QWidget) -> QMenu:
        """Context menu for empty space while browsing a folder."""
        menu = QMenu(parent)
        menu.setObjectName("contextMenu")
        menu.addAction(
            self._icon("folder-plus"),
            "New Folder…\tCtrl+Shift+N",
            lambda: self.action_triggered.emit("new_folder", folder_path),
        )
        menu.addAction(self._icon("refresh"), "Refresh\tF5", lambda: self.action_triggered.emit("refresh", folder_path))
        menu.addSeparator()
        menu.addAction(self._icon("external"), "Open in Windows Explorer", lambda: self._open_in_explorer(folder_path))
        menu.addAction(self._icon("terminal"), "Open in Terminal", lambda: self._open_in_terminal(folder_path))
        menu.addSeparator()
        menu.addAction(
            self._icon("sparkle", "accent"), "Ask AI about this folder…", lambda: self._ask_custom_question(folder_path)
        )
        return menu

    # === Helpers ===

    @staticmethod
    def _open_in_explorer(path: str, select: str | None = None) -> None:
        try:
            if select:
                subprocess.Popen(["explorer", "/select,", select])
            else:
                subprocess.Popen(["explorer", path])
        except Exception as e:
            logger.error(f"Failed to open Explorer: {e}")

    @staticmethod
    def _open_in_terminal(path: str) -> None:
        try:
            # Prefer Windows Terminal when available
            import shutil

            if shutil.which("wt.exe"):
                subprocess.Popen(["wt.exe", "-d", path])
            else:
                subprocess.Popen(["cmd", "/k", f'cd /d "{path}"'], creationflags=subprocess.CREATE_NEW_CONSOLE)
        except Exception as e:
            logger.error(f"Failed to open terminal: {e}")

    @staticmethod
    def _open_file(path: str) -> None:
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception as e:
            logger.error(f"Failed to open file: {e}")

    @staticmethod
    def _copy_to_clipboard(text: str) -> None:
        try:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(text)
        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {e}")

    def _ask_custom_question(self, item_path: str) -> None:
        item_name = Path(item_path).name or item_path
        item_type = "folder" if Path(item_path).is_dir() else "file"
        text, ok = QInputDialog.getText(
            None,
            "Ask OP(AI)UM",
            f"What would you like to know or do with the {item_type} '{item_name}'?",
            text="",
        )
        if ok and text.strip():
            self.ask_ai.emit(text.strip(), item_path)
