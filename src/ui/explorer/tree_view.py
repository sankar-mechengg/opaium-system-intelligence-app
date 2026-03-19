"""
OP(AI)UM — Folder Tree View

Left-side tree navigation showing the folder hierarchy.
Supports lazy loading of subdirectories on expand.
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtGui import QFont, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from src.config.constants import AppConstants
from src.utils.icon_provider import IconProvider
from src.utils.path_utils import PathUtils


class FolderTreeView(QWidget):
    """
    Folder tree navigation panel.

    Displays a tree of the filesystem starting from user drives
    and recently accessed folders. Lazy-loads subdirectories.

    Signals:
        folder_selected(str): Emitted when a folder is selected.
        folder_double_clicked(str): Emitted on double-click.
    """

    folder_selected = Signal(str)
    folder_double_clicked = Signal(str)
    context_menu_requested = Signal(str, object)  # (path, global_pos)

    ROLE_PATH = Qt.ItemDataRole.UserRole + 1
    ROLE_LOADED = Qt.ItemDataRole.UserRole + 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_provider = IconProvider()

        self.setMinimumWidth(AppConstants.TREE_PANEL_WIDTH)
        self.setMaximumWidth(350)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header
        header = QLabel("  Navigation")
        header.setObjectName("treeHeader")
        header_font = QFont()
        header_font.setPointSize(10)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setFixedHeight(32)
        layout.addWidget(header)

        # Tree view
        self._tree = QTreeView()
        self._tree.setObjectName("folderTree")
        self._tree.setHeaderHidden(True)
        self._tree.setAnimated(True)
        self._tree.setIndentation(18)
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self._model = QStandardItemModel()
        self._tree.setModel(self._model)

        # Connect signals
        self._tree.clicked.connect(self._on_clicked)
        self._tree.doubleClicked.connect(self._on_double_clicked)
        self._tree.expanded.connect(self._on_expanded)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)

        layout.addWidget(self._tree)

        # Populate root
        self._populate_root()

    def _populate_root(self) -> None:
        """Add root items: drives and quick access folders."""
        self._model.clear()

        # Quick Access section
        quick_access = QStandardItem("Quick Access")
        quick_access.setFont(self._bold_font())
        quick_access.setEditable(False)
        quick_access.setSelectable(False)
        self._model.appendRow(quick_access)

        # Add common user folders
        user_folders = {
            "Desktop": os.path.expandvars("%USERPROFILE%\\Desktop"),
            "Documents": os.path.expandvars("%USERPROFILE%\\Documents"),
            "Downloads": os.path.expandvars("%USERPROFILE%\\Downloads"),
            "Pictures": os.path.expandvars("%USERPROFILE%\\Pictures"),
            "Videos": os.path.expandvars("%USERPROFILE%\\Videos"),
            "Music": os.path.expandvars("%USERPROFILE%\\Music"),
        }

        for name, path in user_folders.items():
            if os.path.exists(path):
                item = self._create_folder_item(name, path)
                quick_access.appendRow(item)

        # Drives section
        drives_item = QStandardItem("Drives")
        drives_item.setFont(self._bold_font())
        drives_item.setEditable(False)
        drives_item.setSelectable(False)
        self._model.appendRow(drives_item)

        import string

        for letter in string.ascii_uppercase:
            drive_path = f"{letter}:\\"
            if os.path.exists(drive_path):
                label = self._get_volume_label(drive_path)
                display_name = f"{letter}: {label}" if label else f"{letter}: Drive"
                drive_item = self._create_folder_item(display_name, drive_path)
                drives_item.appendRow(drive_item)

        # Expand Quick Access by default
        self._tree.expand(self._model.indexFromItem(quick_access))

    def _create_folder_item(self, name: str, path: str) -> QStandardItem:
        """Create a tree item for a folder with lazy-load placeholder."""
        item = QStandardItem(name)
        item.setData(path, self.ROLE_PATH)
        item.setData(False, self.ROLE_LOADED)
        item.setEditable(False)

        icon = self._icon_provider.get_folder_icon(path)
        item.setIcon(icon)

        # Add placeholder child for expand arrow
        placeholder = QStandardItem("Loading...")
        placeholder.setEditable(False)
        placeholder.setSelectable(False)
        item.appendRow(placeholder)

        return item

    def _on_expanded(self, index: QModelIndex) -> None:
        """Lazy-load subdirectories when a folder is expanded."""
        item = self._model.itemFromIndex(index)
        if item is None:
            return

        path = item.data(self.ROLE_PATH)
        loaded = item.data(self.ROLE_LOADED)

        if loaded or not path:
            return

        # Remove placeholder
        item.removeRows(0, item.rowCount())
        item.setData(True, self.ROLE_LOADED)

        # Load subdirectories
        try:
            entries = sorted(os.scandir(path), key=lambda e: e.name.lower())
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if PathUtils.is_system_or_hidden(entry.path):
                            continue
                        child = self._create_folder_item(entry.name, entry.path)
                        item.appendRow(child)
                except (OSError, PermissionError):
                    continue
        except (OSError, PermissionError):
            no_access = QStandardItem("(Access Denied)")
            no_access.setEditable(False)
            no_access.setSelectable(False)
            item.appendRow(no_access)

    def _on_clicked(self, index: QModelIndex) -> None:
        """Handle folder selection."""
        item = self._model.itemFromIndex(index)
        if item:
            path = item.data(self.ROLE_PATH)
            if path:
                self.folder_selected.emit(path)

    def _on_double_clicked(self, index: QModelIndex) -> None:
        """Handle folder double-click."""
        item = self._model.itemFromIndex(index)
        if item:
            path = item.data(self.ROLE_PATH)
            if path:
                self.folder_double_clicked.emit(path)

    def _on_context_menu(self, pos) -> None:
        """Handle right-click on tree item."""
        index = self._tree.indexAt(pos)
        if not index.isValid():
            return
        item = self._model.itemFromIndex(index)
        if item is None:
            return
        path = item.data(self.ROLE_PATH)
        if path:
            global_pos = self._tree.viewport().mapToGlobal(pos)
            self.context_menu_requested.emit(path, global_pos)

    def add_recent_folders(self, folder_paths: list[str]) -> None:
        """Add recently accessed folders to the Quick Access section."""
        quick_access = self._model.item(0)  # First item is Quick Access
        if quick_access is None:
            return

        existing = set()
        for i in range(quick_access.rowCount()):
            child = quick_access.child(i)
            if child:
                existing.add(child.data(self.ROLE_PATH))

        for path in folder_paths:
            if path not in existing and os.path.exists(path):
                name = Path(path).name
                item = self._create_folder_item(name, path)
                quick_access.appendRow(item)

    def select_path(self, path: str) -> None:
        """Programmatically select a path in the tree."""
        # Simple linear search — works for shallow trees
        for i in range(self._model.rowCount()):
            root = self._model.item(i)
            if root:
                result = self._find_path_item(root, path)
                if result:
                    self._tree.setCurrentIndex(self._model.indexFromItem(result))
                    return

    def _find_path_item(self, parent: QStandardItem, path: str) -> QStandardItem | None:
        """Recursively find an item by path."""
        for i in range(parent.rowCount()):
            child = parent.child(i)
            if child and child.data(self.ROLE_PATH) == path:
                return child
            if child and child.rowCount() > 0:
                result = self._find_path_item(child, path)
                if result:
                    return result
        return None

    @staticmethod
    def _get_volume_label(drive_path: str) -> str:
        """Get Windows volume label for a drive (e.g. 'Code Drive 3')."""
        try:
            import ctypes
            from ctypes import wintypes

            volume_name = ctypes.create_unicode_buffer(wintypes.MAX_PATH + 1)
            ctypes.windll.kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(drive_path),
                volume_name,
                ctypes.sizeof(volume_name),
                None,
                None,
                None,
                None,
                0,
            )
            label = volume_name.value.strip()
            return label if label else ""
        except Exception:
            return ""

    @staticmethod
    def _bold_font() -> QFont:
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        return font
