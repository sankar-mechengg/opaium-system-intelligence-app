"""
OP(AI)UM — Notification Manager

Handles in-app toast notifications and Windows system
tray balloon notifications.
"""

from __future__ import annotations

from enum import StrEnum

from loguru import logger
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)


class NotificationType(StrEnum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class ToastNotification(QWidget):
    """
    Floating toast notification that appears at the top of the window.
    Auto-dismisses after a timeout with fade animation.
    """

    closed = Signal()

    TYPE_TOKENS = {
        NotificationType.INFO: "accent",
        NotificationType.SUCCESS: "green",
        NotificationType.WARNING: "peach",
        NotificationType.ERROR: "red",
    }

    TYPE_ICONS = {
        NotificationType.INFO: "info",
        NotificationType.SUCCESS: "check-circle",
        NotificationType.WARNING: "warning",
        NotificationType.ERROR: "error-circle",
    }

    def __init__(
        self,
        message: str,
        notification_type: NotificationType = NotificationType.INFO,
        duration_ms: int = 4000,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._duration = duration_ms
        self._type = notification_type

        self.setObjectName("toastNotification")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(46)
        self.setMinimumWidth(320)
        self.setMaximumWidth(640)

        from src.ui.theme import token

        accent = token(self.TYPE_TOKENS.get(notification_type, "accent"))
        self._accent = accent
        self.setStyleSheet(
            f"#toastNotification {{ background-color: {token('bg_surface0')}; border: 1px solid {accent}; "
            f"border-left: 4px solid {accent}; border-radius: 10px; padding: 4px 12px; }}"
        )

        self._build_ui(message, notification_type)

        # Opacity effect for fade
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)

        # Auto-dismiss timer
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.dismiss)

    def _build_ui(self, message: str, ntype: NotificationType) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(8)

        from src.ui.theme import token
        from src.utils.icon_provider import SvgIcons

        # Icon
        icon = QLabel()
        icon.setFixedSize(18, 18)
        icon.setPixmap(SvgIcons.icon(self.TYPE_ICONS.get(ntype, "info"), self._accent, 18).pixmap(18, 18))
        layout.addWidget(icon)

        # Message
        msg = QLabel(message)
        msg.setStyleSheet(f"color: {token('text')}; font-size: 10pt; background: transparent;")
        msg.setWordWrap(False)
        layout.addWidget(msg, stretch=1)

        # Close button
        close_btn = QPushButton()
        close_btn.setIcon(SvgIcons.icon("close", token("text_muted"), 12))
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; }"
            f"QPushButton:hover {{ background: {token('bg_surface1')}; border-radius: 12px; }}"
        )
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.dismiss)
        layout.addWidget(close_btn)

    def show_animated(self) -> None:
        """Show with fade-in animation."""
        self.show()
        self.raise_()

        # Fade in
        fade_in = QPropertyAnimation(self._opacity, b"opacity")
        fade_in.setDuration(300)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_in_anim = fade_in
        fade_in.start()

        # Start dismiss timer
        self._dismiss_timer.start(self._duration)

    def dismiss(self) -> None:
        """Dismiss with fade-out animation."""
        self._dismiss_timer.stop()

        fade_out = QPropertyAnimation(self._opacity, b"opacity")
        fade_out.setDuration(300)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        fade_out.finished.connect(self._on_dismissed)
        self._fade_out_anim = fade_out
        fade_out.start()

    def _on_dismissed(self) -> None:
        self.closed.emit()
        self.deleteLater()


class NotificationManager:
    """
    Manages toast notifications for a parent widget.
    Stacks multiple notifications vertically.
    """

    def __init__(self, parent: QWidget) -> None:
        self._parent = parent
        self._active: list[ToastNotification] = []
        self._y_offset = 60  # Below title bar

    def show(
        self,
        message: str,
        notification_type: NotificationType = NotificationType.INFO,
        duration_ms: int = 4000,
    ) -> None:
        """Show a toast notification."""
        toast = ToastNotification(message, notification_type, duration_ms, self._parent)

        # Position (bottom-right, stacked upwards)
        toast.adjustSize()
        x = self._parent.width() - toast.width() - 20
        y = self._parent.height() - 60 - len(self._active) * 54
        toast.move(max(10, x), max(10, y))

        toast.closed.connect(lambda t=toast: self._on_closed(t))
        self._active.append(toast)
        toast.show_animated()

        logger.debug(f"Notification: [{notification_type.value}] {message}")

    def info(self, message: str) -> None:
        self.show(message, NotificationType.INFO)

    def success(self, message: str) -> None:
        self.show(message, NotificationType.SUCCESS)

    def warning(self, message: str) -> None:
        self.show(message, NotificationType.WARNING)

    def error(self, message: str) -> None:
        self.show(message, NotificationType.ERROR)

    def _on_closed(self, toast: ToastNotification) -> None:
        if toast in self._active:
            self._active.remove(toast)
            self._reposition()

    def _reposition(self) -> None:
        """Reposition remaining notifications after one closes."""
        for i, toast in enumerate(self._active):
            x = self._parent.width() - toast.width() - 20
            y = self._parent.height() - 60 - i * 54
            toast.move(max(10, x), max(10, y))
