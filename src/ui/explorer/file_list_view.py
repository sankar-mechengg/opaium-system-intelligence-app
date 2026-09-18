"""
OP(AI)UM — File List View

Details-style view (Name, Date modified, Type, Size) for the explorer,
sharing the same signals as the card grid so the panel can switch freely.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QModelIndex, QObject, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTreeView, QVBoxLayout, QWidget

from src.core.models import RecentItem
from src.utils.icon_provider import IconProvider
from src.utils.path_utils import PathUtils

ROLE_ITEM = Qt.ItemDataRole.UserRole + 10


class FileListView(QWidget):
    """
    Signals:
        item_selected(RecentItem)
        item_opened(RecentItem)
        context_menu_requested(RecentItem, QPoint)
        selection_cleared()
    """

    item_selected = Signal(object)
    item_opened = Signal(object)
    context_menu_requested = Signal(object, object)
    selection_cleared = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[RecentItem] = []
        self._icons = IconProvider.shared()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self._tree = QTreeView()
        self._tree.setObjectName("fileListView")
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(False)
        self._tree.setUniformRowHeights(True)
        self._tree.setSortingEnabled(False)
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.setIconSize(QSize(20, 20))
        self._tree.installEventFilter(self)

        self._model = QStandardItemModel(0, 4, self)
        self._model.setHorizontalHeaderLabels(["Name", "Date modified", "Type", "Size"])
        self._tree.setModel(self._model)

        header = self._tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(False)

        self._tree.doubleClicked.connect(self._on_double_clicked)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.selectionModel().selectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self._tree)

    # === Data ===

    def set_items(self, items: list[RecentItem]) -> None:
        self._items = list(items)
        self._model.removeRows(0, self._model.rowCount())
        for item in self._items:
            icon = self._icons.get_folder_icon(item.path) if item.is_folder else self._icons.get_file_icon(item.path)
            name = QStandardItem(icon, item.name)
            name.setData(item, ROLE_ITEM)
            name.setToolTip(item.path)
            date = QStandardItem(item.accessed_at.strftime("%Y-%m-%d %H:%M"))
            kind = QStandardItem(
                "Folder" if item.is_folder else (item.extension.upper() + " file" if item.extension else "File")
            )
            size = QStandardItem("" if item.is_folder else PathUtils.format_size(item.size_bytes))
            size.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            for cell in (name, date, kind, size):
                cell.setEditable(False)
            self._model.appendRow([name, date, kind, size])

    def filter_items(self, predicate) -> int:  # type: ignore[no-untyped-def]
        visible = 0
        for row in range(self._model.rowCount()):
            item = self._model.item(row, 0).data(ROLE_ITEM)
            show = bool(predicate(item))
            self._tree.setRowHidden(row, QModelIndex(), not show)
            visible += int(show)
        return visible

    def clear(self) -> None:
        self._items = []
        self._model.removeRows(0, self._model.rowCount())

    def select_path(self, path: str) -> None:
        for row in range(self._model.rowCount()):
            item = self._model.item(row, 0).data(ROLE_ITEM)
            if item and item.path == path:
                idx = self._model.index(row, 0)
                self._tree.setCurrentIndex(idx)
                self._tree.scrollTo(idx)
                return

    def selected_item(self) -> RecentItem | None:
        idx = self._tree.currentIndex()
        if not idx.isValid():
            return None
        return self._model.item(idx.row(), 0).data(ROLE_ITEM)

    def focus_view(self) -> None:
        self._tree.setFocus()

    # === Events ===

    def _item_at(self, index: QModelIndex) -> RecentItem | None:
        if not index.isValid():
            return None
        return self._model.item(index.row(), 0).data(ROLE_ITEM)

    def _on_double_clicked(self, index: QModelIndex) -> None:
        item = self._item_at(index)
        if item is not None:
            self.item_opened.emit(item)

    def _on_selection_changed(self, *_args: object) -> None:
        item = self.selected_item()
        if item is None:
            self.selection_cleared.emit()
        else:
            self.item_selected.emit(item)

    def _on_context_menu(self, pos: QPoint) -> None:
        index = self._tree.indexAt(pos)
        item = self._item_at(index)
        if item is None:
            return
        self._tree.setCurrentIndex(index)
        self.context_menu_requested.emit(item, self._tree.viewport().mapToGlobal(pos))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._tree and event.type() == QEvent.Type.KeyPress:
            key = event.key()  # type: ignore[attr-defined]
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                item = self.selected_item()
                if item is not None:
                    self.item_opened.emit(item)
                    return True
        return super().eventFilter(watched, event)
