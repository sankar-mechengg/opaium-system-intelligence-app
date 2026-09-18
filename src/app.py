"""
OP(AI)UM — Application Controller

Orchestrates the application lifecycle:
1. Theme (system / light / dark)
2. First-run wizard or lock screen
3. Main window, tray icon and services (auto-refresh, undo purge,
   idle lock, update check, Windows startup registration)
4. Lock / unlock and clean shutdown
"""

from __future__ import annotations

import contextlib
import sys

from loguru import logger
from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from src.config.config_manager import ConfigManager
from src.config.constants import AppConstants
from src.services.idle_monitor import IdleMonitor
from src.services.update_checker import UpdateChecker
from src.ui.theme import ThemeManager


class OpAIUMApp(QObject):
    """
    Main application controller.

    Manages the lifecycle: theme → auth → main window → tray → services.
    """

    def __init__(self, qt_app: QApplication, config: ConfigManager, start_minimized: bool = False) -> None:
        super().__init__(qt_app)
        self._qt_app = qt_app
        self._config = config
        self._start_minimized = start_minimized
        self._main_window = None  # MainWindow
        self._tray_icon: QSystemTrayIcon | None = None
        self._refresh_timer: QTimer | None = None
        self._first_run_setup = None
        self._auth_screen = None
        self._auto_purge = None
        self._locked = False
        self._quitting = False

        self._theme = ThemeManager.install(qt_app)
        self._idle = IdleMonitor(self)
        self._idle.idle_timeout.connect(self.lock)
        qt_app.installEventFilter(self._idle)
        self._updates = UpdateChecker(config, self)
        self._updates.update_available.connect(self._on_update_available)
        self._updates.check_finished.connect(self._on_update_check_finished)

    # === Startup ===

    def initialize(self) -> None:
        """Initialize the application — theme, auth check, then show UI."""
        logger.info("Initializing OP(AI)UM application...")
        self._theme.apply(self._config.settings.appearance.theme)

        if self._config.is_first_run():
            self._show_first_run_setup()
        elif self._config.is_auth_configured():
            self._show_auth_screen(relock=False)
        else:
            self._launch_main_app()

    def _show_first_run_setup(self) -> None:
        from src.auth.first_run_setup import FirstRunSetup

        logger.info("Showing first-run setup wizard...")
        self._first_run_setup = FirstRunSetup(self._config)
        self._first_run_setup.setup_complete.connect(self._on_first_run_complete)
        self._first_run_setup.quit_requested.connect(self.quit)
        self._first_run_setup.show()
        self._first_run_setup.raise_()
        self._first_run_setup.activateWindow()

    def _on_first_run_complete(self) -> None:
        logger.info("First-run setup complete.")
        self._config.mark_first_run_complete()
        self._first_run_setup = None
        self._launch_main_app()

    def _show_auth_screen(self, relock: bool) -> None:
        from src.auth.auth_screen import AuthScreen

        self._auth_screen = AuthScreen(self._config, is_relock=relock)
        self._auth_screen.authenticated.connect(self._on_auth_success)
        self._auth_screen.wipe_requested.connect(self.wipe_and_exit)
        self._auth_screen.quit_requested.connect(self.quit)
        self._auth_screen.show()
        self._auth_screen.raise_()
        self._auth_screen.activateWindow()

    def _on_auth_success(self) -> None:
        logger.info("Authentication successful.")
        self._auth_screen = None
        if self._main_window is None:
            self._launch_main_app()
        else:
            self._locked = False
            self._idle.reset()
            self._main_window.show_from_tray()

    # === Main window & services ===

    def _launch_main_app(self) -> None:
        from src.ui.main_window import MainWindow

        self._main_window = MainWindow(self._config)
        self._main_window.lock_requested.connect(self.lock)
        self._main_window.quit_requested.connect(self.quit)
        self._main_window.settings_changed.connect(self._apply_settings)
        self._main_window.check_updates_requested.connect(lambda: self._updates.check(force=True))
        self._main_window.wipe_requested.connect(self.wipe_and_exit)

        if self._start_minimized or self._config.settings.startup.start_minimized:
            logger.info("Starting minimized to the tray.")
        else:
            self._main_window.show()

        self._setup_tray()
        self._apply_settings()
        self._setup_auto_purge()
        QTimer.singleShot(4000, self._updates.check)

        logger.info("OP(AI)UM is ready.")

    def _apply_settings(self) -> None:
        """(Re)apply everything that depends on settings — called after Save."""
        s = self._config.settings
        self._setup_auto_refresh()
        self._idle.set_minutes(s.auth.idle_lock_minutes if s.auth.is_configured else 0)
        self._sync_startup_registration()
        if self._auto_purge is not None:
            self._auto_purge.set_purge_days(s.undo.purge_days)
        lock_action = getattr(self, "_lock_action", None)
        if lock_action is not None:
            lock_action.setVisible(s.auth.is_configured)

    def _setup_tray(self) -> None:
        if AppConstants.LOGO_ICO_PATH.exists():
            icon = QIcon(str(AppConstants.LOGO_ICO_PATH))
        elif AppConstants.LOGO_PATH.exists():
            icon = QIcon(str(AppConstants.LOGO_PATH))
        else:
            icon = QIcon()

        self._tray_icon = QSystemTrayIcon(icon, self._qt_app)
        self._tray_icon.setToolTip(f"{AppConstants.APP_NAME} v{AppConstants.APP_VERSION} — System Intelligence")

        menu = QMenu()
        menu.setObjectName("contextMenu")

        show_action = QAction("Show OP(AI)UM", menu)
        show_action.triggered.connect(self._show_main_window)
        menu.addAction(show_action)

        chat_action = QAction("Ask the AI…", menu)
        chat_action.triggered.connect(lambda: self._show_tab("chat"))
        menu.addAction(chat_action)

        refresh_action = QAction("Refresh now", menu)
        refresh_action.triggered.connect(self._manual_refresh)
        menu.addAction(refresh_action)

        menu.addSeparator()

        self._lock_action = QAction("Lock", menu)
        self._lock_action.triggered.connect(self.lock)
        self._lock_action.setVisible(self._config.is_auth_configured())
        menu.addAction(self._lock_action)

        settings_action = QAction("Settings…", menu)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)

        self._tray_icon.setContextMenu(menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()
        logger.info("System tray initialized.")

    def _setup_auto_refresh(self) -> None:
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
        settings = self._config.settings.refresh
        if not settings.auto_refresh_enabled:
            return
        interval_ms = max(AppConstants.MIN_REFRESH_INTERVAL, settings.refresh_interval_seconds) * 1000
        if self._refresh_timer is None:
            self._refresh_timer = QTimer(self)
            self._refresh_timer.timeout.connect(self._auto_refresh)
        self._refresh_timer.start(interval_ms)
        logger.info(f"Auto-refresh every {interval_ms // 1000}s")

    def _setup_auto_purge(self) -> None:
        from src.undo.auto_purge import AutoPurge

        if self._main_window is None:
            return
        journal = self._main_window.undo_manager.journal
        self._auto_purge = AutoPurge(journal, purge_days=self._config.settings.undo.purge_days, parent=self)
        self._auto_purge.start()

    def _sync_startup_registration(self) -> None:
        from src.utils.windows_api import WindowsAPI

        if self._config.settings.startup.start_with_windows:
            app_path = sys.executable if getattr(sys, "frozen", False) else sys.argv[0]
            WindowsAPI.add_to_startup(app_path, minimized=True)
        else:
            WindowsAPI.remove_from_startup()

    # === Refresh ===

    def _auto_refresh(self) -> None:
        if self._main_window is not None and not self._locked:
            self._main_window.refresh_all()

    def _manual_refresh(self) -> None:
        self._auto_refresh()
        if self._tray_icon and self._config.settings.startup.show_notifications:
            self._tray_icon.showMessage(
                AppConstants.APP_NAME, "Data refreshed.", QSystemTrayIcon.MessageIcon.Information, 2000
            )

    # === Window helpers ===

    def raise_window(self) -> None:
        """Bring the main window to the foreground (single-instance handler / hotkey)."""
        self._show_main_window()

    def _show_main_window(self) -> None:
        if self._locked:
            if self._auth_screen is not None:
                self._auth_screen.raise_()
                self._auth_screen.activateWindow()
            return
        if self._main_window is not None:
            self._main_window.show_from_tray()

    def _show_tab(self, tab: str) -> None:
        self._show_main_window()
        if self._main_window is not None and not self._locked:
            self._main_window.switch_tab(tab)

    def _open_settings(self) -> None:
        self._show_main_window()
        if self._main_window is not None and not self._locked:
            self._main_window.show_settings()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick, QSystemTrayIcon.ActivationReason.Trigger):
            self._show_main_window()

    # === Lock ===

    def lock(self) -> None:
        """Hide the main window and show the lock screen."""
        if self._locked or self._main_window is None:
            return
        if not self._config.is_auth_configured():
            logger.info("Lock requested but no PIN/password is set.")
            if self._main_window is not None:
                self._main_window.notifier.warning("Set a PIN or password in Settings → Security to enable locking.")
            return
        self._locked = True
        self._main_window.hide()
        self._show_auth_screen(relock=True)
        logger.info("Application locked.")

    # === Updates ===

    def _on_update_available(self, version: str, url: str, notes: str) -> None:
        if self._main_window is not None:
            self._main_window.show_update_available(version, url, notes)
            self._main_window.notifier.notify(f"OP(AI)UM {version} is available.", title="Update available")

    def _on_update_check_finished(self, ok: bool, message: str) -> None:
        if self._main_window is not None:
            self._main_window.report_update_status(message)

    # === Reset & quit ===

    def wipe_and_exit(self) -> None:
        """Delete all local data and exit (recovery path for forgotten credentials)."""
        removed = ConfigManager.wipe_all_user_data()
        QMessageBox.information(
            None,
            "OP(AI)UM reset",
            f"Removed {len(removed)} item(s) from {AppConstants.APPDATA_DIR}.\nOP(AI)UM will now close — start it again to set up from scratch.",
        )
        self._quitting = True
        self._qt_app.quit()

    def quit(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        with contextlib.suppress(Exception):
            self._config.auto_save_if_dirty()
        if self._refresh_timer:
            self._refresh_timer.stop()
        if self._auto_purge is not None:
            self._auto_purge.stop()
        if self._tray_icon:
            self._tray_icon.hide()
        if self._main_window is not None:
            try:
                self._main_window.shutdown()
            except Exception as e:
                logger.debug(f"Shutdown cleanup error: {e}")
            self._main_window.force_close()
        self._qt_app.quit()
