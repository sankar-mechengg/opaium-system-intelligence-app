"""
OP(AI)UM — Custom Title Bar

Frameless window title bar with logo, app name, navigation
tabs, and window controls (minimize, maximize, close).
Supports window dragging.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QFont, QPixmap, QMouseEvent

from src.config.constants import AppConstants


class TitleBar(QWidget):
    """
    Custom title bar for the frameless main window.

    Signals:
        tab_changed(str): Navigation tab clicked ('explorer', 'chat', 'history').
        settings_clicked(): Settings button clicked.
        minimize_clicked(): Minimize window.
        maximize_clicked(): Maximize/restore window.
        close_clicked(): Close window.
    """

    tab_changed = Signal(str)
    settings_clicked = Signal()
    minimize_clicked = Signal()
    maximize_clicked = Signal()
    close_clicked = Signal()

    TITLE_HEIGHT = 44

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._drag_pos: QPoint | None = None
        self._current_tab = "explorer"

        self.setObjectName("titleBar")
        self.setFixedHeight(self.TITLE_HEIGHT)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 4, 0)
        layout.setSpacing(6)

        # Logo
        logo_label = QLabel()
        if AppConstants.LOGO_PATH.exists():
            pixmap = QPixmap(str(AppConstants.LOGO_PATH))
            scaled = pixmap.scaled(
                28, 28,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo_label.setPixmap(scaled)
        logo_label.setFixedSize(32, 32)
        layout.addWidget(logo_label)

        # App name
        name = QLabel(AppConstants.APP_NAME)
        name.setObjectName("titleAppName")
        name_font = QFont()
        name_font.setPointSize(11)
        name_font.setBold(True)
        name.setFont(name_font)
        layout.addWidget(name)

        layout.addSpacing(20)

        # Navigation tabs
        self._tab_buttons: dict[str, QPushButton] = {}

        tabs = [
            ("explorer", "Explorer"),
            ("chat", "AI Chat"),
            ("history", "History"),
        ]

        for tab_id, tab_label in tabs:
            btn = QPushButton(tab_label)
            btn.setObjectName("titleTab")
            btn.setCheckable(True)
            btn.setChecked(tab_id == "explorer")
            btn.setFixedHeight(32)
            btn.setMinimumWidth(80)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            tab_font = QFont()
            tab_font.setPointSize(9)
            btn.setFont(tab_font)

            tid = tab_id
            btn.clicked.connect(lambda checked=False, t=tid: self._on_tab_clicked(t))

            self._tab_buttons[tab_id] = btn
            layout.addWidget(btn)

        layout.addStretch()

        # Settings button
        settings_btn = QPushButton("⚙")
        settings_btn.setObjectName("titleSettingsBtn")
        settings_btn.setFixedSize(36, 32)
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setToolTip("Settings")
        settings_font = QFont()
        settings_font.setPointSize(14)
        settings_btn.setFont(settings_font)
        settings_btn.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(settings_btn)

        layout.addSpacing(8)

        # Window controls
        for symbol, obj_name, signal, tooltip in [
            ("—", "titleMinBtn", self.minimize_clicked, "Minimize"),
            ("☐", "titleMaxBtn", self.maximize_clicked, "Maximize"),
            ("✕", "titleCloseBtn", self.close_clicked, "Close"),
        ]:
            btn = QPushButton(symbol)
            btn.setObjectName(obj_name)
            btn.setFixedSize(40, 32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tooltip)
            ctrl_font = QFont()
            ctrl_font.setPointSize(11)
            btn.setFont(ctrl_font)
            btn.clicked.connect(signal.emit)
            layout.addWidget(btn)

    def _on_tab_clicked(self, tab_id: str) -> None:
        """Handle navigation tab click."""
        if tab_id == self._current_tab:
            return

        self._current_tab = tab_id

        for tid, btn in self._tab_buttons.items():
            btn.setChecked(tid == tab_id)

        self.tab_changed.emit(tab_id)

    def set_active_tab(self, tab_id: str) -> None:
        """Programmatically set the active tab."""
        self._on_tab_clicked(tab_id)

    # === Window Dragging ===

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.window().pos()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_clicked.emit()
