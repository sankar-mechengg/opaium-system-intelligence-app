"""
OP(AI)UM — Search Bar Widget

Top search/filter bar for the explorer view.
Supports instant filtering as-you-type with debounce.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from src.ui.widgets.loading_spinner import LoadingSpinner


class SearchBar(QWidget):
    """
    Search/filter bar with type selector and debounced input.

    Signals:
        search_changed(str): Emitted after debounce when text changes.
        filter_changed(str): Emitted when type filter changes.
        refresh_requested(): Emitted when refresh button is clicked.
    """

    search_changed = Signal(str)
    filter_changed = Signal(str)
    refresh_requested = Signal()

    DEBOUNCE_MS = 300

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # Loading spinner (shown during refresh, left of search)
        self._spinner = LoadingSpinner(self, size=24, line_width=2)
        self._spinner.hide()
        layout.addWidget(self._spinner)

        # Search input
        self._search_input = QLineEdit()
        self._search_input.setObjectName("searchInput")
        self._search_input.setPlaceholderText("Search files and folders...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMinimumHeight(36)
        search_font = QFont()
        search_font.setPointSize(10)
        self._search_input.setFont(search_font)
        layout.addWidget(self._search_input, stretch=1)

        # Type filter dropdown
        self._type_filter = QComboBox()
        self._type_filter.setObjectName("typeFilter")
        self._type_filter.setMinimumHeight(36)
        self._type_filter.setMinimumWidth(130)
        self._type_filter.addItems(
            [
                "All Items",
                "Folders Only",
                "Files Only",
                "Images",
                "Documents",
                "Videos",
                "Audio",
                "Archives",
                "Code",
            ]
        )
        layout.addWidget(self._type_filter)

        # Refresh button
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setObjectName("refreshBtn")
        self._refresh_btn.setMinimumHeight(36)
        self._refresh_btn.setMinimumWidth(80)
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self._refresh_btn)

        # Debounce timer
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._emit_search)

    def _connect_signals(self) -> None:
        self._search_input.textChanged.connect(self._on_text_changed)
        self._type_filter.currentTextChanged.connect(self._on_filter_changed)
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)

    def _on_text_changed(self, text: str) -> None:
        self._debounce_timer.stop()
        self._debounce_timer.start(self.DEBOUNCE_MS)

    def _emit_search(self) -> None:
        self.search_changed.emit(self._search_input.text().strip())

    def _on_filter_changed(self, text: str) -> None:
        self.filter_changed.emit(text)

    @property
    def search_text(self) -> str:
        return self._search_input.text().strip()

    @property
    def active_filter(self) -> str:
        return self._type_filter.currentText()

    def clear(self) -> None:
        self._search_input.clear()
        self._type_filter.setCurrentIndex(0)

    def set_focus(self) -> None:
        self._search_input.setFocus()

    def start_spinner(self) -> None:
        """Show and start the loading spinner."""
        self._spinner.start()

    def stop_spinner(self) -> None:
        """Stop and hide the loading spinner."""
        self._spinner.stop()
