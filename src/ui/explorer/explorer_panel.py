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
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QFrame,
)
from PySide6.QtCore import Qt, Signal
from loguru import logger

from src.config.config_manager import ConfigManager
from src.core.models import RecentItem
from src.core.recent_parser import RecentParser
from src.core.tracking_db import TrackingDB
from src.core.folder_monitor import FolderMonitor
from src.ui.explorer.search_bar import SearchBar
from src.ui.explorer.tree_view import FolderTreeView
from src.ui.explorer.card_grid_view import CardGridView
from src.ui.explorer.preview_panel import PreviewPanel
from src.ui.widgets.context_menu import ContextMenuBuilder
from src.ui.widgets.loading_spinner import LoadingSpinner
from src.utils.thread_pool import Worker, ThreadPoolManager
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
        self._recent_parser = RecentParser()
        self._tracking_db = TrackingDB()
        self._context_menu = ContextMenuBuilder()
        self._selected_item: Optional[RecentItem] = None

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

        # Loading spinner overlay
        self._spinner = LoadingSpinner(self, size=48)
        self._spinner.hide()

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

        # Context menu AI actions
        self._context_menu.ask_ai.connect(self.ask_ai_requested.emit)

    def refresh_data(self) -> None:
        """Refresh the recent items data in a background thread."""
        self._spinner.start()

        worker = Worker(self._load_data)
        worker.signals.result.connect(self._on_data_loaded)
        worker.signals.error.connect(self._on_data_error)
        worker.signals.finished.connect(lambda: self._spinner.stop())
        ThreadPoolManager.run(worker)

    def _load_data(self) -> dict:
        """Background: load recent items."""
        show_hidden = self._config.settings.appearance.show_hidden_folders

        grouped = self._recent_parser.get_grouped_items(
            include_files=True,
            include_folders=True,
        )

        # Filter hidden if needed
        if not show_hidden:
            from src.utils.path_utils import PathUtils
            for group in grouped:
                grouped[group] = [
                    item for item in grouped[group]
                    if not PathUtils.is_system_or_hidden(item.path)
                ]

        # Track items in DB
        for group_items in grouped.values():
            for item in group_items:
                if item.file_id and item.volume_serial:
                    self._tracking_db.upsert_item(
                        file_id=item.file_id,
                        volume_serial=item.volume_serial,
                        path=item.path,
                        name=item.name,
                        item_type=item.item_type,
                    )

        return grouped

    def _on_data_loaded(self, grouped: dict) -> None:
        """Handle loaded data on the main thread."""
        self._card_grid.set_items(grouped)

        # Add recent folders to tree
        all_folders = []
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

    def _on_context_menu(self, item: RecentItem, pos) -> None:
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

    def get_selected_item(self) -> Optional[RecentItem]:
        return self._selected_item

    def get_selected_path(self) -> str:
        if self._selected_item:
            return self._selected_item.path
        return ""
