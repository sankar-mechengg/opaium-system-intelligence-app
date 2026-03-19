"""
OP(AI)UM — Application Controller

Orchestrates the application lifecycle:
1. Show auth screen (if configured)
2. Load theme
3. Initialize main window
4. Setup system tray
5. Start auto-refresh timer
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from src.config.config_manager import ConfigManager
from src.config.constants import AppConstants


class OpAIUMApp:
    """
    Main application controller.

    Manages the lifecycle: auth → theme → main window → tray.
    """

    def __init__(self, qt_app: QApplication, config: ConfigManager) -> None:
        self._qt_app = qt_app
        self._config = config
        self._main_window: object | None = None  # Will be MainWindow
        self._tray_icon: QSystemTrayIcon | None = None
        self._refresh_timer: QTimer | None = None
        self._first_run_setup: object | None = None  # Will be FirstRunSetup
        self._auth_screen: object | None = None  # Will be AuthScreen

    def initialize(self) -> None:
        """Initialize the application — auth check, then show UI."""
        logger.info("Initializing OP(AI)UM application...")

        # Apply theme
        self._apply_theme()

        # Check if authentication is configured
        if self._config.is_auth_configured():
            self._show_auth_screen()
        elif self._config.is_first_run():
            self._show_first_run_setup()
        else:
            self._launch_main_app()

    def _apply_theme(self) -> None:
        """Apply the current theme (light or dark) stylesheet."""
        theme = self._config.settings.appearance.theme
        # Use .value to get the enum's string value ("light" or "dark")
        theme_value = theme.value if hasattr(theme, "value") else str(theme)
        theme_file = AppConstants.THEMES_DIR / f"{theme_value}.qss"

        if theme_file.exists():
            try:
                stylesheet = theme_file.read_text(encoding="utf-8")
                self._qt_app.setStyleSheet(stylesheet)
                logger.info(f"Applied theme: {theme_value}")
            except Exception as e:
                logger.warning(f"Failed to load theme {theme_value}: {e}")
        else:
            logger.warning(f"Theme file not found: {theme_file}")

    def _show_auth_screen(self) -> None:
        """Show the password/PIN entry screen."""
        from src.auth.auth_screen import AuthScreen

        self._auth_screen = AuthScreen(self._config)
        self._auth_screen.authenticated.connect(self._on_auth_success)
        self._auth_screen.show()
        self._auth_screen.raise_()
        self._auth_screen.activateWindow()

    def _show_first_run_setup(self) -> None:
        """Show the first-run password setup wizard."""
        from src.auth.first_run_setup import FirstRunSetup

        logger.info("Showing first-run setup wizard...")
        self._first_run_setup = FirstRunSetup(self._config)
        self._first_run_setup.setup_complete.connect(self._on_first_run_complete)
        self._first_run_setup.show()
        self._first_run_setup.raise_()
        self._first_run_setup.activateWindow()
        logger.info("First-run setup window displayed.")

    def _on_auth_success(self) -> None:
        """Handle successful authentication."""
        logger.info("Authentication successful.")
        self._launch_main_app()

    def _on_first_run_complete(self) -> None:
        """Handle first-run setup completion."""
        logger.info("First-run setup complete.")
        self._config.mark_first_run_complete()
        self._launch_main_app()

    def _launch_main_app(self) -> None:
        """Launch the main application window and services."""
        from src.ui.main_window import MainWindow

        self._main_window = MainWindow(self._config)
        self._main_window.show()

        # Setup system tray
        self._setup_tray()

        # Setup auto-refresh
        self._setup_auto_refresh()

        # Setup auto-start if configured
        if self._config.settings.startup.start_with_windows:
            self._register_startup()

        logger.info("OP(AI)UM is ready.")

    def _setup_tray(self) -> None:
        """Setup the system tray icon with context menu."""
        if not self._config.settings.startup.minimize_to_tray:
            return

        icon_path = AppConstants.LOGO_PATH
        icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()

        self._tray_icon = QSystemTrayIcon(icon, self._qt_app)
        self._tray_icon.setToolTip(f"{AppConstants.APP_NAME} — System Intelligence Tool")

        # Context menu
        menu = QMenu()

        show_action = QAction("Show OP(AI)UM", menu)
        show_action.triggered.connect(self._show_main_window)
        menu.addAction(show_action)

        refresh_action = QAction("Refresh Now", menu)
        refresh_action.triggered.connect(self._manual_refresh)
        menu.addAction(refresh_action)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self._tray_icon.setContextMenu(menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

        logger.info("System tray initialized.")

    def _setup_auto_refresh(self) -> None:
        """Setup the auto-refresh timer."""
        if not self._config.settings.refresh.auto_refresh_enabled:
            return

        interval_ms = self._config.settings.refresh.refresh_interval_seconds * 1000

        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._auto_refresh)
        self._refresh_timer.start(interval_ms)

        logger.info(f"Auto-refresh started: every {self._config.settings.refresh.refresh_interval_seconds}s")

    def _auto_refresh(self) -> None:
        """Trigger auto-refresh of file/folder data."""
        if self._main_window and hasattr(self._main_window, "refresh_data"):
            self._main_window.refresh_data()  # type: ignore[attr-defined]

    def _manual_refresh(self) -> None:
        """Trigger manual refresh."""
        self._auto_refresh()
        if self._tray_icon:
            self._tray_icon.showMessage(
                AppConstants.APP_NAME,
                "Data refreshed.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )

    def _show_main_window(self) -> None:
        """Restore the main window from tray."""
        if self._main_window:
            self._main_window.show()  # type: ignore[attr-defined]
            self._main_window.raise_()  # type: ignore[attr-defined]
            self._main_window.activateWindow()  # type: ignore[attr-defined]

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon double-click."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_main_window()

    def _register_startup(self) -> None:
        """Register app in Windows startup."""
        import sys

        app_path = sys.executable if getattr(sys, "frozen", False) else sys.argv[0]

        from src.utils.windows_api import WindowsAPI

        WindowsAPI.add_to_startup(app_path)

    def _quit(self) -> None:
        """Quit the application."""
        self._config.auto_save_if_dirty()
        if self._refresh_timer:
            self._refresh_timer.stop()
        if self._tray_icon:
            self._tray_icon.hide()
        self._qt_app.quit()
