"""
OP(AI)UM — Explorer Toolbar

Navigation (back / forward / up / home), breadcrumb path, search box with
debounce, type filter, sort selector, grid/list toggle and refresh.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QWidget

from src.ui.explorer.breadcrumb import BreadcrumbBar
from src.ui.widgets.icon_button import IconButton
from src.ui.widgets.loading_spinner import LoadingSpinner

TYPE_FILTERS = ["All Items", "Folders Only", "Files Only", "Images", "Documents", "Videos", "Audio", "Archives", "Code"]
SORT_OPTIONS = [("Name", "name"), ("Date modified", "modified"), ("Size", "size"), ("Type", "type")]


class ExplorerToolbar(QWidget):
    """
    Signals:
        back_requested / forward_requested / up_requested / home_requested
        path_requested(str): navigate to a path ("" = Home)
        search_changed(str): debounced search text
        filter_changed(str): type filter label
        sort_changed(str, bool): sort field, descending
        view_changed(str): "grid" or "list"
        refresh_requested()
    """

    back_requested = Signal()
    forward_requested = Signal()
    up_requested = Signal()
    home_requested = Signal()
    path_requested = Signal(str)
    search_changed = Signal(str)
    filter_changed = Signal(str)
    sort_changed = Signal(str, bool)
    view_changed = Signal(str)
    refresh_requested = Signal()

    DEBOUNCE_MS = 250

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("explorerToolbar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._descending = False
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)

        self._back_btn = IconButton("back", role="icon", icon_size=18, tooltip="Back (Alt+Left)", object_name="navBtn")
        self._fwd_btn = IconButton(
            "forward", role="icon", icon_size=18, tooltip="Forward (Alt+Right)", object_name="navBtn"
        )
        self._up_btn = IconButton("up", role="icon", icon_size=18, tooltip="Up (Alt+Up)", object_name="navBtn")
        for b in (self._back_btn, self._fwd_btn, self._up_btn):
            b.setFixedSize(32, 32)
            layout.addWidget(b)

        self._breadcrumb = BreadcrumbBar()
        layout.addWidget(self._breadcrumb, stretch=3)

        self._spinner = LoadingSpinner(self, size=20, line_width=2)
        self._spinner.hide()
        layout.addWidget(self._spinner)

        self._search = QLineEdit()
        self._search.setObjectName("searchInput")
        self._search.setPlaceholderText("Search this view…  (Ctrl+F)")
        self._search.setClearButtonEnabled(True)
        self._search.setFixedHeight(34)
        self._search.setMinimumWidth(180)
        layout.addWidget(self._search, stretch=2)

        self._type_filter = QComboBox()
        self._type_filter.setObjectName("typeFilter")
        self._type_filter.setFixedHeight(34)
        self._type_filter.setMinimumWidth(120)
        self._type_filter.addItems(TYPE_FILTERS)
        layout.addWidget(self._type_filter)

        self._sort_combo = QComboBox()
        self._sort_combo.setObjectName("sortCombo")
        self._sort_combo.setFixedHeight(34)
        self._sort_combo.setMinimumWidth(130)
        for label, key in SORT_OPTIONS:
            self._sort_combo.addItem(label, key)
        layout.addWidget(self._sort_combo)

        self._sort_dir_btn = IconButton(
            "sort",
            role="icon",
            icon_size=16,
            tooltip="Toggle ascending / descending",
            object_name="viewToggleBtn",
            checkable=True,
        )
        self._sort_dir_btn.setFixedSize(32, 32)
        layout.addWidget(self._sort_dir_btn)

        self._grid_btn = IconButton(
            "grid", role="icon", icon_size=16, tooltip="Grid view", object_name="viewToggleBtn", checkable=True
        )
        self._list_btn = IconButton(
            "list", role="icon", icon_size=16, tooltip="List view", object_name="viewToggleBtn", checkable=True
        )
        for b in (self._grid_btn, self._list_btn):
            b.setFixedSize(32, 32)
            b.set_checked_role("accent")
            layout.addWidget(b)
        self._grid_btn.setChecked(True)

        self._refresh_btn = IconButton(
            "refresh", role="accent", icon_size=16, tooltip="Refresh (F5)", object_name="refreshBtn"
        )
        self._refresh_btn.setFixedSize(34, 34)
        layout.addWidget(self._refresh_btn)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(lambda: self.search_changed.emit(self.search_text))

    def _connect_signals(self) -> None:
        self._back_btn.clicked.connect(self.back_requested.emit)
        self._fwd_btn.clicked.connect(self.forward_requested.emit)
        self._up_btn.clicked.connect(self.up_requested.emit)
        self._breadcrumb.path_requested.connect(self.path_requested.emit)
        self._search.textChanged.connect(lambda _t: self._debounce.start(self.DEBOUNCE_MS))
        self._type_filter.currentTextChanged.connect(self.filter_changed.emit)
        self._sort_combo.currentIndexChanged.connect(lambda _i: self._emit_sort())
        self._sort_dir_btn.toggled.connect(self._on_sort_dir)
        self._grid_btn.clicked.connect(lambda: self._set_view("grid"))
        self._list_btn.clicked.connect(lambda: self._set_view("list"))
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)

    # === State ===

    def set_path(self, path: str) -> None:
        self._breadcrumb.set_path(path)
        self._up_btn.setEnabled(bool(path))

    def set_nav_state(self, can_back: bool, can_forward: bool) -> None:
        self._back_btn.setEnabled(can_back)
        self._fwd_btn.setEnabled(can_forward)

    def set_sort(self, field: str, descending: bool) -> None:
        idx = self._sort_combo.findData(field)
        if idx >= 0:
            self._sort_combo.blockSignals(True)
            self._sort_combo.setCurrentIndex(idx)
            self._sort_combo.blockSignals(False)
        self._sort_dir_btn.blockSignals(True)
        self._sort_dir_btn.setChecked(descending)
        self._sort_dir_btn.blockSignals(False)
        self._descending = descending

    def set_view(self, view: str) -> None:
        self._grid_btn.setChecked(view == "grid")
        self._list_btn.setChecked(view == "list")

    def _set_view(self, view: str) -> None:
        self.set_view(view)
        self.view_changed.emit(view)

    def _on_sort_dir(self, checked: bool) -> None:
        self._descending = checked
        self._emit_sort()

    def _emit_sort(self) -> None:
        self.sort_changed.emit(str(self._sort_combo.currentData()), self._descending)

    @property
    def search_text(self) -> str:
        return self._search.text().strip()

    @property
    def active_filter(self) -> str:
        return self._type_filter.currentText()

    @property
    def sort_field(self) -> str:
        return str(self._sort_combo.currentData())

    @property
    def sort_descending(self) -> bool:
        return self._descending

    def focus_search(self) -> None:
        self._search.setFocus()
        self._search.selectAll()

    def edit_path(self) -> None:
        self._breadcrumb.begin_edit()

    def clear_search(self) -> None:
        self._search.clear()

    def start_spinner(self) -> None:
        self._spinner.start()

    def stop_spinner(self) -> None:
        self._spinner.stop()
