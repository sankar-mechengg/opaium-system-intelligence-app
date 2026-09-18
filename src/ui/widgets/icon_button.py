"""
OP(AI)UM — Themed Icon Button

A QPushButton (optionally with text) whose SVG icon is tinted from a theme
token and re-tinted automatically whenever the theme changes.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QPushButton, QWidget

from src.utils.icon_provider import SvgIcons


class IconButton(QPushButton):
    """Push button with a themed SVG icon."""

    def __init__(
        self,
        icon_name: str,
        text: str = "",
        role: str = "icon",
        icon_size: int = 18,
        tooltip: str = "",
        object_name: str = "",
        checkable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._icon_name = icon_name
        self._role = role
        self._icon_px = icon_size
        self._checked_role: str | None = None
        if object_name:
            self.setObjectName(object_name)
        if tooltip:
            self.setToolTip(tooltip)
        self.setCheckable(checkable)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIconSize(QSize(icon_size, icon_size))
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.refresh_icon()

        from src.ui.theme import ThemeManager

        mgr = ThemeManager.instance()
        if mgr is not None:
            mgr.theme_applied.connect(self._on_theme)
        if checkable:
            self.toggled.connect(lambda _c: self.refresh_icon())

    def set_icon_name(self, name: str, role: str | None = None) -> None:
        self._icon_name = name
        if role is not None:
            self._role = role
        self.refresh_icon()

    def set_checked_role(self, role: str) -> None:
        """Token used for the icon while the button is checked."""
        self._checked_role = role
        self.refresh_icon()

    def refresh_icon(self) -> None:
        role = self._checked_role if (self._checked_role and self.isChecked()) else self._role
        self.setIcon(SvgIcons.themed(self._icon_name, role, self._icon_px))

    def _on_theme(self, _effective: str) -> None:
        self.refresh_icon()
