"""
OP(AI)UM — Custom Title Bar

Title bar for the native frameless main window: logo, app name, navigation
tabs (Dashboard, Explorer, AI Chat, History), lock + settings buttons and
the window controls. Dragging, double-click maximize and Snap Layouts are
handled natively via hit-testing (see native_window.py).
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from src.config.constants import AppConstants
from src.ui.native_window import HTCAPTION, HTCLIENT, HTCLOSE, HTMAXBUTTON, HTMINBUTTON
from src.ui.widgets.icon_button import IconButton

TABS: list[tuple[str, str, str]] = [
    ("dashboard", "Dashboard", "dashboard"),
    ("explorer", "Explorer", "explorer"),
    ("chat", "AI Chat", "sparkle"),
    ("history", "History", "history"),
]


class TitleBar(QWidget):
    """
    Custom title bar for the frameless main window.

    Signals:
        tab_changed(str): Navigation tab clicked ('dashboard', 'explorer', 'chat', 'history').
        settings_clicked(): Settings button clicked.
        lock_clicked(): Lock button clicked.
        minimize_clicked(): Minimize window.
        maximize_clicked(): Maximize/restore window.
        close_clicked(): Close window.
    """

    tab_changed = Signal(str)
    settings_clicked = Signal()
    lock_clicked = Signal()
    minimize_clicked = Signal()
    maximize_clicked = Signal()
    close_clicked = Signal()

    TITLE_HEIGHT = 46

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_tab = "explorer"
        self._hovered_control: int = 0

        self.setObjectName("titleBar")
        self.setFixedHeight(self.TITLE_HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(6)

        # Logo
        self._logo = QLabel()
        self._logo.setObjectName("titleLogo")
        if AppConstants.LOGO_PATH.exists():
            pixmap = QPixmap(str(AppConstants.LOGO_PATH))
            self._logo.setPixmap(
                pixmap.scaled(26, 26, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        self._logo.setFixedSize(30, 30)
        layout.addWidget(self._logo)

        # App name
        self._name = QLabel(AppConstants.APP_NAME)
        self._name.setObjectName("titleAppName")
        layout.addWidget(self._name)

        layout.addSpacing(18)

        # Navigation tabs
        self._tab_buttons: dict[str, IconButton] = {}
        for tab_id, label, icon in TABS:
            btn = IconButton(icon, label, role="text_muted", icon_size=16, object_name="titleTab", checkable=True)
            btn.set_checked_role("accent")
            btn.setFixedHeight(32)
            btn.setChecked(tab_id == self._current_tab)
            btn.clicked.connect(lambda checked=False, t=tab_id: self._on_tab_clicked(t))
            self._tab_buttons[tab_id] = btn
            layout.addWidget(btn)

        layout.addStretch()

        # Lock + settings
        self._lock_btn = IconButton(
            "lock", role="text_muted", icon_size=17, tooltip="Lock OP(AI)UM (Ctrl+L)", object_name="titleLockBtn"
        )
        self._lock_btn.setFixedSize(36, 32)
        self._lock_btn.clicked.connect(self.lock_clicked.emit)
        layout.addWidget(self._lock_btn)

        self._settings_btn = IconButton(
            "settings", role="text_muted", icon_size=17, tooltip="Settings (Ctrl+,)", object_name="titleSettingsBtn"
        )
        self._settings_btn.setFixedSize(36, 32)
        self._settings_btn.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self._settings_btn)

        layout.addSpacing(10)

        # Window controls — hover/press handled through native hit-testing
        self._min_btn = IconButton(
            "minimize", role="text_muted", icon_size=14, tooltip="Minimize", object_name="titleMinBtn"
        )
        self._max_btn = IconButton(
            "maximize", role="text_muted", icon_size=13, tooltip="Maximize", object_name="titleMaxBtn"
        )
        self._close_btn = IconButton(
            "close", role="text_muted", icon_size=14, tooltip="Close", object_name="titleCloseBtn"
        )
        for btn in (self._min_btn, self._max_btn, self._close_btn):
            btn.setFixedSize(46, self.TITLE_HEIGHT)
            btn.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            layout.addWidget(btn)

    # === Tabs ===

    def _on_tab_clicked(self, tab_id: str) -> None:
        if tab_id != self._current_tab:
            self._current_tab = tab_id
            self.tab_changed.emit(tab_id)
        for tid, btn in self._tab_buttons.items():
            btn.setChecked(tid == tab_id)

    def set_active_tab(self, tab_id: str) -> None:
        """Programmatically set the active tab."""
        self._on_tab_clicked(tab_id)

    @property
    def current_tab(self) -> str:
        return self._current_tab

    def set_lock_visible(self, visible: bool) -> None:
        self._lock_btn.setVisible(visible)

    def update_maximize_icon(self, is_maximized: bool) -> None:
        """Update the maximize button icon to reflect window state."""
        self._max_btn.set_icon_name("restore" if is_maximized else "maximize")
        self._max_btn.setToolTip("Restore" if is_maximized else "Maximize")

    # === Native hit-testing support ===

    def hit_test(self, pos: QPoint) -> int:
        """Map a point (title-bar coordinates) to a Win32 HT* code."""
        if not self.rect().contains(pos):
            return HTCLIENT
        for btn, code in ((self._min_btn, HTMINBUTTON), (self._max_btn, HTMAXBUTTON), (self._close_btn, HTCLOSE)):
            if btn.isVisible() and btn.geometry().contains(pos):
                return code
        child = self.childAt(pos)
        if child is None or child in (self._logo, self._name):
            return HTCAPTION
        return HTCLIENT

    def set_control_hover(self, code: int) -> None:
        """Highlight the window control the cursor is over (0 = none)."""
        if code == self._hovered_control:
            return
        self._hovered_control = code
        for btn, c in ((self._min_btn, HTMINBUTTON), (self._max_btn, HTMAXBUTTON), (self._close_btn, HTCLOSE)):
            hovered = code == c
            if btn.property("hover") != hovered:
                btn.setProperty("hover", hovered)
                if c == HTCLOSE:
                    btn.set_icon_name("close", "accent_text" if hovered else "text_muted")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                btn.update()
