"""
OP(AI)UM — Explorer Panel

A real file browser with a Recent "Home" view:
- Left: folder tree (quick access + drives)
- Center: toolbar (navigation, breadcrumb, search, filter, sort, view) and
  the card grid or details list
- Right: preview panel with quick actions

Native operations (rename, delete to Recycle Bin, new folder) are journaled
so they can be undone from History, and the open folder is watched for
changes so the view stays live.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
from datetime import datetime
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QInputDialog, QMessageBox, QSplitter, QStackedWidget, QVBoxLayout, QWidget

from src.config.config_manager import ConfigManager, enum_value
from src.config.defaults import ExplorerView, SortField
from src.core.directory_scanner import DirectoryScanner
from src.core.folder_monitor import DirectoryWatcher
from src.core.models import RecentItem
from src.core.recent_parser import RecentParser
from src.core.tracking_db import TrackingDB
from src.ui.explorer.card_grid_view import CardGridView, item_matches
from src.ui.explorer.explorer_toolbar import ExplorerToolbar
from src.ui.explorer.file_list_view import FileListView
from src.ui.explorer.preview_panel import PreviewPanel
from src.ui.explorer.tree_view import FolderTreeView
from src.ui.widgets.context_menu import ContextMenuBuilder
from src.undo.operation_journal import OperationJournal
from src.undo.operation_models import FileMapping, Operation, OperationType
from src.utils.path_utils import PathUtils
from src.utils.thread_pool import ThreadPoolManager, Worker
from src.utils.time_utils import TimeGroup, TimeUtils


class ExplorerPanel(QWidget):
    """
    Signals:
        item_selected(RecentItem): An item was selected.
        ask_ai_requested(str, str): AI action from context menu (question, path).
        status_message(str): Text for the window status bar.
        operation_recorded(str): A native operation was journaled (description).
    """

    item_selected = Signal(object)
    ask_ai_requested = Signal(str, str)
    status_message = Signal(str)
    operation_recorded = Signal(str)

    def __init__(self, config: ConfigManager, journal: OperationJournal, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._journal = journal
        self._tracking_db = TrackingDB()
        self._recent_parser = RecentParser(tracking_db=self._tracking_db)
        self._context_menu = ContextMenuBuilder()
        self._watcher = DirectoryWatcher(self)

        self._current_path: str = ""  # "" = Home (Recent)
        self._history: list[str] = [""]
        self._history_index = 0
        self._items: list[RecentItem] = []
        self._home_grouped: dict[TimeGroup, list[RecentItem]] | None = None
        self._selected_item: RecentItem | None = None
        self._load_token = 0
        self._pending_select: str | None = None

        self._build_ui()
        self._connect_signals()
        self._setup_shortcuts()
        self.apply_settings()

        self.refresh_data()

    # === UI ===

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._toolbar = ExplorerToolbar()
        main_layout.addWidget(self._toolbar)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setObjectName("explorerSplitter")
        self._splitter.setHandleWidth(1)
        self._splitter.setChildrenCollapsible(False)

        self._tree_view = FolderTreeView()
        self._splitter.addWidget(self._tree_view)

        self._views = QStackedWidget()
        self._card_grid = CardGridView()
        self._list_view = FileListView()
        self._views.addWidget(self._card_grid)
        self._views.addWidget(self._list_view)
        self._splitter.addWidget(self._views)

        self._preview_panel = PreviewPanel()
        self._splitter.addWidget(self._preview_panel)

        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 0)
        self._splitter.setSizes([240, 760, 290])

        main_layout.addWidget(self._splitter, stretch=1)

    def _connect_signals(self) -> None:
        tb = self._toolbar
        tb.back_requested.connect(self.go_back)
        tb.forward_requested.connect(self.go_forward)
        tb.up_requested.connect(self.go_up)
        tb.path_requested.connect(self.navigate_to)
        tb.search_changed.connect(lambda _t: self._apply_filters())
        tb.filter_changed.connect(lambda _t: self._apply_filters())
        tb.sort_changed.connect(self._on_sort_changed)
        tb.view_changed.connect(self._on_view_changed)
        tb.refresh_requested.connect(self.refresh_data)

        for view in (self._card_grid, self._list_view):
            view.item_selected.connect(self._on_item_selected)
            view.item_opened.connect(self._on_item_opened)
            view.context_menu_requested.connect(self._on_context_menu)
            view.selection_cleared.connect(self._on_selection_cleared)

        self._tree_view.folder_selected.connect(self.navigate_to)
        self._tree_view.folder_double_clicked.connect(self.navigate_to)
        self._tree_view.context_menu_requested.connect(self._on_tree_context_menu)

        self._context_menu.ask_ai.connect(self.ask_ai_requested.emit)
        self._context_menu.action_triggered.connect(self._on_context_action)
        self._preview_panel.action_requested.connect(self._on_context_action)

        self._watcher.changed.connect(self._on_folder_changed)

    def _setup_shortcuts(self) -> None:
        def sc(seq: str, slot: object) -> None:
            shortcut = QShortcut(QKeySequence(seq), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(slot)  # type: ignore[arg-type]

        sc("Alt+Left", self.go_back)
        sc("Alt+Right", self.go_forward)
        sc("Alt+Up", self.go_up)
        sc("Backspace", self.go_up)
        sc("Ctrl+F", self._toolbar.focus_search)
        sc("Alt+D", self._toolbar.edit_path)
        sc("F2", self._rename_selected)
        sc("Delete", self._delete_selected)
        sc("Ctrl+Shift+N", lambda: self._new_folder(self._current_path))
        sc("Ctrl+C", self._copy_selected_path)
        sc("Alt+Home", lambda: self.navigate_to(""))
        sc("Escape", self._toolbar.clear_search)

    # === Settings ===

    def apply_settings(self) -> None:
        a = self._config.settings.appearance
        self._card_grid.set_card_size(a.card_width, a.card_height)
        self._toolbar.set_sort(enum_value(a.sort_field), a.sort_descending)
        view = enum_value(a.explorer_view)
        self._toolbar.set_view(view)
        self._views.setCurrentIndex(1 if view == "list" else 0)
        if self._items:
            self.refresh_data()  # hidden-items and sort settings may have changed

    # === Navigation ===

    @property
    def current_path(self) -> str:
        return self._current_path

    def navigate_to(self, path: str, record_history: bool = True) -> None:
        """Open a folder (or Home when path is empty)."""
        path = (path or "").strip()
        if path:
            expanded = os.path.expandvars(os.path.expanduser(path))
            if os.path.isfile(expanded):
                self._pending_select = expanded
                expanded = str(Path(expanded).parent)
            if not os.path.isdir(expanded):
                self.status_message.emit(f"Folder not found: {path}")
                QMessageBox.warning(
                    self, "Folder not found", f"The folder does not exist or is not accessible:\n{path}"
                )
                return
            path = os.path.normpath(expanded)

        if record_history:
            self._history = self._history[: self._history_index + 1]
            self._history.append(path)
            self._history_index = len(self._history) - 1

        self._current_path = path
        self._toolbar.set_path(path)
        self._toolbar.set_nav_state(self._history_index > 0, self._history_index < len(self._history) - 1)
        self._toolbar.clear_search()
        self._selected_item = None
        self._preview_panel.clear()

        if path:
            self._tree_view.select_path(path)
            self._watcher.watch(path)
        else:
            self._tree_view.clear_selection()
            self._watcher.stop()

        self.refresh_data()

    def go_back(self) -> None:
        if self._history_index > 0:
            self._history_index -= 1
            self.navigate_to(self._history[self._history_index], record_history=False)

    def go_forward(self) -> None:
        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            self.navigate_to(self._history[self._history_index], record_history=False)

    def go_up(self) -> None:
        if not self._current_path:
            return
        parent = str(Path(self._current_path).parent)
        if parent == self._current_path:
            self.navigate_to("")
        else:
            self._pending_select = self._current_path
            self.navigate_to(parent)

    # === Data loading ===

    def refresh_data(self) -> None:
        """Reload the current view in a background thread."""
        self._load_token += 1
        token = self._load_token
        self._toolbar.start_spinner()
        path = self._current_path

        worker = Worker(self._load_data, path)
        worker.signals.result.connect(lambda data, t=token: self._on_data_loaded(t, data))
        worker.signals.error.connect(lambda err, t=token: self._on_data_error(t, err))
        worker.signals.finished.connect(self._toolbar.stop_spinner)
        ThreadPoolManager.run(worker)

    def _load_data(self, path: str) -> dict:  # type: ignore[type-arg]
        show_hidden = self._config.settings.appearance.show_hidden_folders
        if path:
            items = DirectoryScanner.scan(path, show_hidden=show_hidden)
            return {"mode": "browse", "items": items}

        grouped = self._recent_parser.get_grouped_items(include_files=True, include_folders=True)
        for group in grouped:
            grouped[group] = [
                item
                for item in grouped[group]
                if item.exists and (show_hidden or not PathUtils.is_system_or_hidden(item.path))
            ]
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
        return {"mode": "home", "grouped": grouped}

    def _on_data_loaded(self, token: int, data: object) -> None:
        if token != self._load_token or not isinstance(data, dict):
            return
        if data.get("mode") == "home":
            grouped: dict[TimeGroup, list[RecentItem]] = data["grouped"]
            self._items = [i for g in TimeUtils.group_order() for i in grouped.get(g, [])]
            self._home_grouped = grouped
            folders = [i.path for i in self._items if i.is_folder][:20]
            self._tree_view.add_recent_folders(folders)
        else:
            self._items = list(data["items"])
            self._home_grouped = None
        self._render()
        total = len(self._items)
        where = self._current_path or "Recent"
        self.status_message.emit(f"{total} item{'s' if total != 1 else ''} in {where}")

        if self._pending_select:
            target = self._pending_select
            self._pending_select = None
            self._card_grid.select_path(target)
            self._list_view.select_path(target)

    def _on_data_error(self, token: int, error: str) -> None:
        if token != self._load_token:
            return
        logger.error(f"Explorer load error: {error}")
        self._items = []
        self._home_grouped = None
        self._card_grid.set_empty_state("Cannot open this folder", error, icon="warning")
        self._card_grid.set_groups([])
        self._list_view.clear()
        self.status_message.emit(f"Error: {error}")

    def _render(self) -> None:
        a = self._config.settings.appearance
        sort_field = self._toolbar.sort_field
        descending = self._toolbar.sort_descending

        if self._current_path:
            ordered = DirectoryScanner.sort(self._items, sort_field, descending, a.folders_first)
            folders = [i for i in ordered if i.is_folder]
            files = [i for i in ordered if not i.is_folder]
            self._card_grid.set_empty_state(
                "This folder is empty", "Drop files here from Explorer or ask the AI to create something."
            )
            self._card_grid.set_groups([("Folders", folders), ("Files", files)])
            self._list_view.set_items(ordered)
        else:
            groups = []
            grouped = getattr(self, "_home_grouped", None) or {}
            for g in TimeUtils.group_order():
                items = (
                    DirectoryScanner.sort(grouped.get(g, []), sort_field, descending, a.folders_first)
                    if sort_field != "modified"
                    else grouped.get(g, [])
                )
                groups.append((g.value, items))
            self._card_grid.set_empty_state(
                "No recent activity yet",
                "Files and folders you open in Windows will appear here. Use the tree on the left to browse your drives.",
                icon="clock",
            )
            self._card_grid.set_groups(groups)
            self._list_view.set_items([i for _t, items in groups for i in items])

        self._apply_filters()

    def _apply_filters(self) -> None:
        search = self._toolbar.search_text.lower()
        type_filter = self._toolbar.active_filter
        visible = self._card_grid.filter_items(search, type_filter)
        self._list_view.filter_items(lambda item: item_matches(item, search, type_filter))
        if search or type_filter != "All Items":
            self.status_message.emit(f"{visible} of {len(self._items)} items match")

    def _on_sort_changed(self, field: str, descending: bool) -> None:
        self._config.settings.appearance.sort_field = SortField(field)
        self._config.settings.appearance.sort_descending = descending
        self._config.auto_save_if_dirty()
        self._render()

    def _on_view_changed(self, view: str) -> None:
        self._views.setCurrentIndex(1 if view == "list" else 0)
        self._config.settings.appearance.explorer_view = ExplorerView(view)
        with contextlib.suppress(Exception):
            self._config.save()
        if self._selected_item:
            (self._list_view if view == "list" else self._card_grid).select_path(self._selected_item.path)

    def _on_folder_changed(self, path: str) -> None:
        if path == self._current_path:
            self.refresh_data()

    # === Selection & opening ===

    def _on_item_selected(self, item: RecentItem) -> None:
        self._selected_item = item
        self._preview_panel.show_item(item)
        self.item_selected.emit(item)

    def _on_selection_cleared(self) -> None:
        self._selected_item = None
        self._preview_panel.clear()

    def _on_item_opened(self, item: RecentItem) -> None:
        """Double-click / Enter: browse into folders, open files with their default app."""
        if not item.exists and not os.path.exists(item.path):
            self.status_message.emit(f"Not found: {item.path}")
            return
        if item.is_folder:
            self.navigate_to(item.path)
        else:
            self._open_file(item.path)

    @staticmethod
    def _open_file(path: str) -> None:
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception as e:
            logger.error(f"Failed to open file: {e}")

    def _on_context_menu(self, item: RecentItem, pos: QPoint) -> None:
        if item.is_folder:
            menu = self._context_menu.build_folder_menu(item.path, self)
        else:
            menu = self._context_menu.build_file_menu(item.path, self)
        menu.exec(pos)

    def _on_tree_context_menu(self, path: str, pos: QPoint) -> None:
        menu = self._context_menu.build_folder_menu(path, self)
        menu.exec(pos)

    def contextMenuEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        # Right-click on empty space while browsing a folder
        if self._current_path and self._views.underMouse():
            menu = self._context_menu.build_background_menu(self._current_path, self)
            menu.exec(event.globalPos())
            event.accept()
        else:
            super().contextMenuEvent(event)

    # === Actions ===

    def _on_context_action(self, action: str, path: str) -> None:
        if action == "browse":
            self.navigate_to(path)
        elif action == "open":
            if os.path.isdir(path):
                self.navigate_to(path)
            else:
                self._open_file(path)
        elif action == "reveal":
            try:
                if os.path.isdir(path):
                    subprocess.Popen(["explorer", path])
                else:
                    subprocess.Popen(["explorer", "/select,", path])
            except Exception as e:
                logger.error(f"Reveal failed: {e}")
        elif action == "copy_path":
            from PySide6.QtWidgets import QApplication

            QApplication.clipboard().setText(path)
            self.status_message.emit("Path copied to clipboard")
        elif action == "ask_ai":
            question = f"Tell me about {'the folder' if os.path.isdir(path) else 'the file'} {Path(path).name}"
            self.ask_ai_requested.emit(question, path)
        elif action == "properties":
            self._show_properties(path)
        elif action == "rename":
            self._rename(path)
        elif action == "delete":
            self._delete(path)
        elif action == "new_folder":
            self._new_folder(path)
        elif action == "open_with":
            self._open_with(path)
        elif action == "refresh":
            self.refresh_data()

    def _rename_selected(self) -> None:
        if self._selected_item:
            self._rename(self._selected_item.path)

    def _delete_selected(self) -> None:
        if self._selected_item:
            self._delete(self._selected_item.path)

    def _copy_selected_path(self) -> None:
        if self._selected_item:
            self._on_context_action("copy_path", self._selected_item.path)

    def _rename(self, path: str) -> None:
        p = Path(path)
        if not p.exists():
            return
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=p.name)
        new_name = (new_name or "").strip()
        if not ok or not new_name or new_name == p.name:
            return
        if any(c in new_name for c in '<>:"/\\|?*'):
            QMessageBox.warning(
                self, "Invalid name", 'A name cannot contain any of these characters:  < > : " / \\ | ? *'
            )
            return
        target = p.with_name(new_name)
        if target.exists():
            QMessageBox.warning(self, "Name in use", f"'{new_name}' already exists in this folder.")
            return
        try:
            p.rename(target)
        except OSError as e:
            QMessageBox.critical(self, "Rename failed", str(e))
            return
        self._record(
            OperationType.RENAME_FOLDER if target.is_dir() else OperationType.RENAME,
            f"Renamed {p.name} to {new_name}",
            [FileMapping(source=str(p), destination=str(target), original_name=p.name, new_name=new_name)],
        )
        self._pending_select = str(target)
        self.refresh_data()

    def _delete(self, path: str) -> None:
        p = Path(path)
        if not p.exists():
            return
        kind = "folder" if p.is_dir() else "file"
        reply = QMessageBox.question(
            self,
            "Delete to Recycle Bin",
            f"Move this {kind} to the Recycle Bin?\n\n{p}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            from send2trash import send2trash

            send2trash(str(p))
        except Exception as e:
            QMessageBox.critical(self, "Delete failed", str(e))
            return
        self._record(
            OperationType.DELETE_FOLDER if kind == "folder" else OperationType.DELETE,
            f"Deleted {kind} to Recycle Bin: {p.name}",
            [FileMapping(source=str(p), destination=str(p), original_name=p.name, new_name=p.name)],
            metadata={"method": "recycle_bin", "source": "explorer"},
        )
        self._selected_item = None
        self._preview_panel.clear()
        self.refresh_data()

    def _new_folder(self, parent_path: str) -> None:
        if not parent_path or not os.path.isdir(parent_path):
            return
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:", text="New folder")
        name = (name or "").strip()
        if not ok or not name:
            return
        target = Path(parent_path) / name
        if target.exists():
            QMessageBox.warning(self, "Name in use", f"'{name}' already exists here.")
            return
        try:
            target.mkdir(parents=False)
        except OSError as e:
            QMessageBox.critical(self, "Could not create folder", str(e))
            return
        self._record(
            OperationType.CREATE_FOLDER,
            f"Created folder: {name}",
            [FileMapping(source="", destination=str(target), original_name="", new_name=name)],
        )
        if os.path.normpath(parent_path) == os.path.normpath(self._current_path):
            self._pending_select = str(target)
            self.refresh_data()

    @staticmethod
    def _open_with(path: str) -> None:
        try:
            subprocess.Popen(["rundll32.exe", "shell32.dll,OpenAs_RunDLL", path])
        except Exception as e:
            logger.error(f"Open With failed: {e}")

    def _record(
        self,
        op_type: OperationType,
        description: str,
        mappings: list[FileMapping],
        metadata: dict | None = None,  # type: ignore[type-arg]
    ) -> None:
        try:
            self._journal.record(
                Operation(
                    timestamp=datetime.now(),
                    operation_type=op_type,
                    description=description,
                    file_mappings=mappings,
                    affected_count=len(mappings),
                    is_undoable=True,
                    metadata=metadata or {"source": "explorer"},
                )
            )
            self.operation_recorded.emit(description)
        except Exception as e:
            logger.error(f"Failed to journal explorer operation: {e}")

    def _show_properties(self, path: str) -> None:
        """Show the Windows file/folder properties dialog."""
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
        except Exception as e:
            logger.error(f"Failed to show properties: {e}")

    # === Accessors ===

    def get_selected_item(self) -> RecentItem | None:
        return self._selected_item

    def get_selected_path(self) -> str:
        return self._selected_item.path if self._selected_item else ""

    def shutdown(self) -> None:
        self._watcher.shutdown()
        self._tracking_db.close()
