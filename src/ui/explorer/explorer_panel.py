"""
OP(AI)UM — Explorer Panel

Main explorer container that combines:
- Left: Folder tree navigation
- Center: Card/grid view with time-grouped items
- Right: Preview panel for selected item

Orchestrates data loading, search filtering, and selection.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.config.config_manager import ConfigManager
from src.core.models import RecentItem
from src.core.recent_parser import RecentParser
from src.core.tracking_db import TrackingDB
from src.ui.explorer.card_grid_view import CardGridView
from src.ui.explorer.preview_panel import PreviewPanel
from src.ui.explorer.search_bar import SearchBar
from src.ui.explorer.tree_view import FolderTreeView
from src.ui.widgets.context_menu import ContextMenuBuilder
from src.utils.thread_pool import ThreadPoolManager, Worker
from src.utils.time_utils import TimeGroup


class ExplorerPanel(QWidget):
    """
    Main explorer view combining all navigation and display components.

    Signals:
        item_selected(RecentItem): An item was selected in the grid.
        ask_ai_requested(str, str): AI action from context menu (question, path).
    """

    item_selected = Signal(object)
    ask_ai_requested = Signal(str, str)

    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._tracking_db = TrackingDB()
        self._recent_parser = RecentParser(tracking_db=self._tracking_db)
        self._context_menu = ContextMenuBuilder()
        self._selected_item: RecentItem | None = None

        self._build_ui()
        self._connect_signals()

        # Initial data load
        self.refresh_data()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Search bar at the top
        self._search_bar = SearchBar()
        self._search_bar.setObjectName("explorerSearchBar")
        main_layout.addWidget(self._search_bar)

        # Splitter: Tree | Grid | Preview
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setObjectName("explorerSplitter")
        self._splitter.setHandleWidth(2)

        # Left: Tree view
        self._tree_view = FolderTreeView()
        self._splitter.addWidget(self._tree_view)

        # Center: Card grid
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        self._card_grid = CardGridView()
        center_layout.addWidget(self._card_grid)

        self._splitter.addWidget(center_widget)

        # Right: Preview panel
        self._preview_panel = PreviewPanel()
        self._splitter.addWidget(self._preview_panel)

        # Set initial sizes (tree: 250, grid: stretch, preview: 280)
        self._splitter.setSizes([250, 600, 280])

        main_layout.addWidget(self._splitter, stretch=1)

    def _connect_signals(self) -> None:
        # Search
        self._search_bar.search_changed.connect(self._on_search_changed)
        self._search_bar.filter_changed.connect(self._on_filter_changed)
        self._search_bar.refresh_requested.connect(self.refresh_data)

        # Card grid
        self._card_grid.item_selected.connect(self._on_item_selected)
        self._card_grid.item_opened.connect(self._on_item_opened)
        self._card_grid.context_menu_requested.connect(self._on_context_menu)

        # Tree view
        self._tree_view.folder_selected.connect(self._on_tree_folder_selected)
        self._tree_view.folder_double_clicked.connect(self._on_tree_folder_double_clicked)
        self._tree_view.context_menu_requested.connect(self._on_tree_context_menu)

        # Context menu AI actions
        self._context_menu.ask_ai.connect(self.ask_ai_requested.emit)
        self._context_menu.action_triggered.connect(self._on_context_action)

    def refresh_data(self) -> None:
        """Refresh the recent items data in a background thread."""
        self._search_bar.start_spinner()

        worker = Worker(self._load_data)
        worker.signals.result.connect(self._on_data_loaded)
        worker.signals.error.connect(self._on_data_error)
        worker.signals.finished.connect(lambda: self._search_bar.stop_spinner())
        ThreadPoolManager.run(worker)

    def _load_data(self) -> dict[TimeGroup, list[RecentItem]]:
        """Background: load recent items."""
        show_hidden = self._config.settings.appearance.show_hidden_folders

        grouped = self._recent_parser.get_grouped_items(
            include_files=True,
            include_folders=True,
        )

        # Filter hidden if needed, but keep items that exist
        # Note: Broken links that couldn't be resolved are already filtered out by parser
        if not show_hidden:
            from src.utils.path_utils import PathUtils

            for group in grouped:
                grouped[group] = [
                    item for item in grouped[group] if item.exists and not PathUtils.is_system_or_hidden(item.path)
                ]
        else:
            # Only show items that exist
            for group in grouped:
                grouped[group] = [item for item in grouped[group] if item.exists]

        # Track items in DB for future rename detection
        for group_items in grouped.values():
            for item in group_items:
                if item.file_id and item.volume_serial and item.exists:
                    self._tracking_db.upsert_item(
                        file_id=item.file_id,
                        volume_serial=item.volume_serial,
                        path=item.path,
                        name=item.name,
                        item_type=item.item_type,
                    )

        return grouped

    def _on_data_loaded(self, grouped: dict[TimeGroup, list[RecentItem]]) -> None:
        """Handle loaded data on the main thread."""
        self._card_grid.set_items(grouped)
        self._card_grid.filter_items(
            self._search_bar.search_text,
            self._search_bar.active_filter,
        )

        # Add recent folders to tree
        all_folders: list[str] = []
        for items in grouped.values():
            all_folders.extend(item.path for item in items if item.is_folder and item.exists)
        self._tree_view.add_recent_folders(all_folders[:20])

        total = sum(len(items) for items in grouped.values())
        logger.info(f"Explorer loaded {total} items.")

    def _on_data_error(self, error: str) -> None:
        logger.error(f"Data load error: {error}")

    def _on_search_changed(self, text: str) -> None:
        self._card_grid.filter_items(text, self._search_bar.active_filter)

    def _on_filter_changed(self, filter_type: str) -> None:
        self._card_grid.filter_items(self._search_bar.search_text, filter_type)

    def _on_item_selected(self, item: RecentItem) -> None:
        self._selected_item = item
        self._preview_panel.show_item(item)
        self.item_selected.emit(item)

    def _on_item_opened(self, item: RecentItem) -> None:
        """Handle double-click: open in Explorer for folders, open file for files."""
        if not item.exists:
            return
        try:
            if item.is_folder:
                subprocess.Popen(["explorer", item.path])
            else:
                os.startfile(item.path)  # type: ignore[attr-defined]
        except Exception as e:
            logger.error(f"Failed to open item: {e}")

    def _on_context_menu(self, item: RecentItem, pos: QPoint) -> None:
        if item.is_folder:
            menu = self._context_menu.build_folder_menu(item.path, self)
        else:
            menu = self._context_menu.build_file_menu(item.path, self)
        menu.exec(pos)

    def _on_tree_folder_selected(self, path: str) -> None:
        """Handle folder selection from tree — could browse into it."""
        logger.debug(f"Tree folder selected: {path}")

    def _on_tree_folder_double_clicked(self, path: str) -> None:
        """Open folder in Explorer from tree."""
        try:
            subprocess.Popen(["explorer", path])
        except Exception as e:
            logger.error(f"Failed to open folder: {e}")

    def _on_tree_context_menu(self, path: str, pos: QPoint) -> None:
        """Handle right-click on a tree view folder."""
        if Path(path).is_dir():
            menu = self._context_menu.build_folder_menu(path, self)
        else:
            menu = self._context_menu.build_file_menu(path, self)
        menu.exec(pos)

    def _on_context_action(self, action: str, path: str) -> None:
        """Handle context menu actions like 'properties'."""
        if action == "properties":
            self._show_properties(path)

    def _show_properties(self, path: str) -> None:
        """Show Windows file/folder properties dialog."""
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
            sei.lpFile = path
            sei.nShow = 1

            ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei))
            logger.debug(f"Opened properties for: {path}")
        except Exception as e:
            logger.error(f"Failed to show properties: {e}")

    def get_selected_item(self) -> RecentItem | None:
        return self._selected_item

    def get_selected_path(self) -> str:
        if self._selected_item:
            return self._selected_item.path
        return ""
