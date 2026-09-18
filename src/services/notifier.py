"""
OP(AI)UM — Notification Service

Single entry point for user notifications:
- In-app toasts when the window is visible.
- Native Windows toasts (winotify) when the window is hidden in the tray,
  honouring the "show notifications" setting.
"""

from __future__ import annotations

from collections.abc import Callable

from loguru import logger
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

from src.config.config_manager import ConfigManager
from src.config.constants import AppConstants
from src.ui.notifications.toast import NotificationManager, NotificationType
from src.utils.thread_pool import ThreadPoolManager, Worker


class NotificationService(QObject):
    def __init__(
        self,
        config: ConfigManager,
        toast_manager: NotificationManager,
        window: QWidget,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._toasts = toast_manager
        self._window = window

    # === Public API ===

    def notify(
        self,
        message: str,
        kind: NotificationType = NotificationType.INFO,
        title: str | None = None,
        force_native: bool = False,
    ) -> None:
        """Show an in-app toast, or a Windows toast when the window is hidden."""
        window_visible = self._window.isVisible() and not self._window.isMinimized()
        if window_visible and not force_native:
            self._toasts.show(message, kind)
            return
        if not self._config.settings.startup.show_notifications:
            return
        self._native(title or AppConstants.APP_NAME, message)

    def info(self, message: str) -> None:
        self.notify(message, NotificationType.INFO)

    def success(self, message: str) -> None:
        self.notify(message, NotificationType.SUCCESS)

    def warning(self, message: str) -> None:
        self.notify(message, NotificationType.WARNING)

    def error(self, message: str) -> None:
        self.notify(message, NotificationType.ERROR)

    # === Native ===

    def _native(self, title: str, message: str, on_click: Callable[[], None] | None = None) -> None:
        def _send() -> None:
            try:
                from winotify import Notification, audio

                icon = str(AppConstants.LOGO_ICO_PATH) if AppConstants.LOGO_ICO_PATH.exists() else ""
                toast = Notification(
                    app_id=AppConstants.APP_NAME,
                    title=title,
                    msg=message,
                    icon=icon,
                    duration="short",
                )
                toast.set_audio(audio.Default, loop=False)
                toast.show()
            except Exception as e:
                logger.debug(f"Native toast failed: {e}")

        ThreadPoolManager.run(Worker(_send))
