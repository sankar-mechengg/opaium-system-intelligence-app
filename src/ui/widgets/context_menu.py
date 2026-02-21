"""
OP(AI)UM — Context Menu Builder

Builds right-click context menus for files and folders
in the explorer view with relevant actions.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional, Callable

from PySide6.QtWidgets import QMenu, QWidget
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import Signal, QObject
from loguru import logger


class ContextMenuBuilder(QObject):
    """
    Builds context menus for files and folders.

    Signals:
        action_triggered(str, str): (action_name, item_path)
        ask_ai(str, str): (question, item_path)
    """

    action_triggered = Signal(str, str)
    ask_ai = Signal(str, str)

    def build_folder_menu(
        self,
        folder_path: str,
        parent: QWidget,
    ) -> QMenu:
        """Build context menu for a folder item."""
        menu = QMenu(parent)
        menu.setObjectName("contextMenu")

        name = Path(folder_path).name

        # Open in Explorer
        open_action = menu.addAction("Open in Explorer")
        open_action.triggered.connect(lambda: self._open_in_explorer(folder_path))

        # Open in Terminal
        terminal_action = menu.addAction("Open in Terminal")
        terminal_action.triggered.connect(lambda: self._open_in_terminal(folder_path))

        menu.addSeparator()

        # Copy path
        copy_path = menu.addAction("Copy Path")
        copy_path.triggered.connect(lambda: self._copy_to_clipboard(folder_path))

        copy_name = menu.addAction("Copy Name")
        copy_name.triggered.connect(lambda: self._copy_to_clipboard(name))

        menu.addSeparator()

        # AI Actions submenu
        ai_menu = menu.addMenu("Ask AI...")
        ai_actions = [
            ("Count files", f"How many files are in {name}?"),
            ("Analyze size", f"What's the total size of {name}?"),
            ("Find duplicates", f"Find duplicate files in {name}"),
            ("Organize by type", f"Organize files in {name} by type"),
            ("Find large files", f"Find large files in {name}"),
            ("File type summary", f"What types of files are in {name}?"),
        ]

        for label, question in ai_actions:
            action = ai_menu.addAction(label)
            q = question
            p = folder_path
            action.triggered.connect(lambda checked=False, qn=q, pt=p: self.ask_ai.emit(qn, pt))

        menu.addSeparator()

        # Properties
        props_action = menu.addAction("Properties")
        props_action.triggered.connect(
            lambda: self.action_triggered.emit("properties", folder_path)
        )

        return menu

    def build_file_menu(
        self,
        file_path: str,
        parent: QWidget,
    ) -> QMenu:
        """Build context menu for a file item."""
        menu = QMenu(parent)
        menu.setObjectName("contextMenu")

        name = Path(file_path).name

        # Open file
        open_action = menu.addAction("Open")
        open_action.triggered.connect(lambda: self._open_file(file_path))

        # Open containing folder
        open_folder = menu.addAction("Open Containing Folder")
        open_folder.triggered.connect(
            lambda: self._open_in_explorer(str(Path(file_path).parent), select=file_path)
        )

        menu.addSeparator()

        # Copy actions
        copy_path = menu.addAction("Copy Path")
        copy_path.triggered.connect(lambda: self._copy_to_clipboard(file_path))

        copy_name = menu.addAction("Copy Name")
        copy_name.triggered.connect(lambda: self._copy_to_clipboard(name))

        menu.addSeparator()

        # AI Actions
        ai_menu = menu.addMenu("Ask AI...")
        ai_actions = [
            ("Get file info", f"Tell me about the file {name}"),
            ("Find similar", f"Find files similar to {name}"),
        ]

        for label, question in ai_actions:
            action = ai_menu.addAction(label)
            q = question
            p = file_path
            action.triggered.connect(lambda checked=False, qn=q, pt=p: self.ask_ai.emit(qn, pt))

        menu.addSeparator()

        # Delete (to recycle bin)
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(
            lambda: self.action_triggered.emit("delete", file_path)
        )

        # Properties
        props_action = menu.addAction("Properties")
        props_action.triggered.connect(
            lambda: self.action_triggered.emit("properties", file_path)
        )

        return menu

    @staticmethod
    def _open_in_explorer(path: str, select: Optional[str] = None) -> None:
        """Open a path in Windows Explorer."""
        try:
            if select:
                subprocess.Popen(["explorer", "/select,", select])
            else:
                subprocess.Popen(["explorer", path])
        except Exception as e:
            logger.error(f"Failed to open Explorer: {e}")

    @staticmethod
    def _open_in_terminal(path: str) -> None:
        """Open a terminal at the given path."""
        try:
            subprocess.Popen(["cmd", "/k", f"cd /d {path}"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        except Exception as e:
            logger.error(f"Failed to open terminal: {e}")

    @staticmethod
    def _open_file(path: str) -> None:
        """Open a file with the default application."""
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception as e:
            logger.error(f"Failed to open file: {e}")

    @staticmethod
    def _copy_to_clipboard(text: str) -> None:
        """Copy text to clipboard."""
        try:
            from PySide6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(text)
        except Exception as e:
            logger.error(f"Failed to copy to clipboard: {e}")
