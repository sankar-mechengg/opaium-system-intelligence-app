"""
OP(AI)UM — Notification Manager

Handles in-app toast notifications and Windows system
tray balloon notifications.
"""

from __future__ import annotations

from enum import StrEnum

from loguru import logger
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QFont
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

    TYPE_COLORS = {
        NotificationType.INFO: "#2196F3",
        NotificationType.SUCCESS: "#4CAF50",
        NotificationType.WARNING: "#FF9800",
        NotificationType.ERROR: "#F44336",
    }

    TYPE_ICONS = {
        NotificationType.INFO: "ℹ️",
        NotificationType.SUCCESS: "✅",
        NotificationType.WARNING: "⚠️",
        NotificationType.ERROR: "❌",
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
        self.setFixedHeight(48)
        self.setMinimumWidth(300)
        self.setMaximumWidth(600)

        color = self.TYPE_COLORS.get(notification_type, "#2196F3")
        self.setStyleSheet(
            f"#toastNotification {{  background-color: {color};  border-radius: 8px;  padding: 4px 12px;}}"
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

        # Icon
        icon = QLabel(self.TYPE_ICONS.get(ntype, "ℹ️"))
        icon_font = QFont()
        icon_font.setPointSize(12)
        icon.setFont(icon_font)
        layout.addWidget(icon)

        # Message
        msg = QLabel(message)
        msg.setStyleSheet("color: white; font-size: 10pt;")
        msg.setWordWrap(False)
        layout.addWidget(msg, stretch=1)

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton { color: white; background: transparent; border: none; font-size: 12px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.2); border-radius: 12px; }"
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

        # Position
        x = (self._parent.width() - toast.width()) // 2
        y = self._y_offset + len(self._active) * 56
        toast.move(x, y)

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
            x = (self._parent.width() - toast.width()) // 2
            y = self._y_offset + i * 56
            toast.move(x, y)
