"""
OP(AI)UM — Main Window

The primary application window that combines:
- Custom title bar with navigation tabs
- Explorer panel (default view)
- AI Chat panel
- Operation History panel
- Notification system
- Settings dialog access
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QStackedWidget,
    QApplication,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from loguru import logger

from src.config.config_manager import ConfigManager
from src.config.constants import AppConstants
from src.undo.undo_manager import UndoManager
from src.undo.operation_journal import OperationJournal
from src.ui.title_bar import TitleBar
from src.ui.explorer.explorer_panel import ExplorerPanel
from src.ui.chat.chat_panel import ChatPanel
from src.ui.history.history_panel import HistoryPanel
from src.ui.settings.settings_dialog import SettingsDialog
from src.ui.notifications.toast import NotificationManager, NotificationType


class MainWindow(QMainWindow):
    """
    OP(AI)UM main application window.

    Frameless window with custom title bar, stacked panels,
    and notification overlay.
    """

    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._operation_journal = OperationJournal()
        self._undo_manager = UndoManager(self._operation_journal)
        self._is_maximized = False

        self._setup_window()
        self._build_ui()
        self._connect_signals()

        logger.info("Main window initialized.")

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.setWindowTitle(AppConstants.APP_NAME)
        self.setMinimumSize(1000, 650)
        self.resize(1280, 800)

        # Frameless
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # Icon
        if AppConstants.LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(AppConstants.LOGO_PATH)))

    def _build_ui(self) -> None:
        # Central widget
        central = QWidget()
        central.setObjectName("mainCentral")
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title bar
        self._title_bar = TitleBar()
        main_layout.addWidget(self._title_bar)

        # Stacked panels
        self._stack = QStackedWidget()
        self._stack.setObjectName("mainStack")

        # Explorer panel (index 0)
        self._explorer = ExplorerPanel(self._config)
        self._stack.addWidget(self._explorer)

        # Chat panel (index 1)
        self._chat = ChatPanel(self._config, self._undo_manager)
        self._stack.addWidget(self._chat)

        # History panel (index 2)
        self._history = HistoryPanel(self._undo_manager)
        self._stack.addWidget(self._history)

        self._stack.setCurrentIndex(0)
        main_layout.addWidget(self._stack, stretch=1)

        # Notification manager (overlay)
        self._notifications = NotificationManager(central)

    def _connect_signals(self) -> None:
        # Title bar
        self._title_bar.tab_changed.connect(self._on_tab_changed)
        self._title_bar.settings_clicked.connect(self._show_settings)
        self._title_bar.minimize_clicked.connect(self._on_minimize)
        self._title_bar.maximize_clicked.connect(self._on_maximize)
        self._title_bar.close_clicked.connect(self._on_close)

        # Explorer → Chat context
        self._explorer.item_selected.connect(self._on_item_selected)
        self._explorer.ask_ai_requested.connect(self._on_ask_ai)

        # Chat → Explorer refresh
        self._chat.operation_completed.connect(self._on_operation_completed)
        self._chat.undo_requested.connect(self._on_undo_requested)

        # History → Refresh
        self._history.operation_undone.connect(self._on_operation_undone)

    # === Navigation ===

    def _on_tab_changed(self, tab_id: str) -> None:
        """Switch between panels."""
        tab_map = {"explorer": 0, "chat": 1, "history": 2}
        index = tab_map.get(tab_id, 0)
        self._stack.setCurrentIndex(index)

        if tab_id == "chat":
            self._chat.focus_input()
        elif tab_id == "history":
            self._history.refresh()

        logger.debug(f"Switched to tab: {tab_id}")

    # === Settings ===

    def _show_settings(self) -> None:
        dialog = SettingsDialog(self._config, self)
        dialog.theme_changed.connect(self._apply_theme)
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()

    def _apply_theme(self, theme_name: str) -> None:
        """Apply a theme stylesheet."""
        theme_file = AppConstants.THEMES_DIR / f"{theme_name}.qss"
        if theme_file.exists():
            try:
                stylesheet = theme_file.read_text(encoding="utf-8")
                QApplication.instance().setStyleSheet(stylesheet)
                logger.info(f"Theme applied: {theme_name}")
            except Exception as e:
                logger.error(f"Failed to apply theme: {e}")
        else:
            logger.warning(f"Theme file not found: {theme_file}")

    def _on_settings_saved(self) -> None:
        self._notifications.success("Settings saved successfully.")
        # Re-apply theme
        theme = self._config.settings.appearance.theme
        self._apply_theme(theme)

    # === Item Selection ===

    def _on_item_selected(self, item) -> None:
        """Pass selected item context to chat panel."""
        if item.is_folder:
            self._chat.set_folder_context(item.path)

    def _on_ask_ai(self, question: str, path: str) -> None:
        """Handle AI question from context menu — switch to chat."""
        self._title_bar.set_active_tab("chat")
        self._stack.setCurrentIndex(1)
        self._chat.inject_ai_question(question, path)

    # === Operations ===

    def _on_operation_completed(self) -> None:
        """Refresh explorer after an AI operation."""
        self._explorer.refresh_data()
        self._notifications.success("Operation completed.")

    def _on_undo_requested(self, operation_id: int) -> None:
        """Handle undo from chat."""
        success = self._undo_manager.undo(operation_id)
        if success:
            self._notifications.info("Operation undone.")
            self._explorer.refresh_data()
        else:
            self._notifications.error("Failed to undo operation.")

    def _on_operation_undone(self) -> None:
        """Handle undo from history panel."""
        self._explorer.refresh_data()
        self._notifications.info("Operation undone.")

    # === Window Controls ===

    def _on_minimize(self) -> None:
        if self._config.settings.startup.minimize_to_tray:
            self.hide()
        else:
            self.showMinimized()

    def _on_maximize(self) -> None:
        if self._is_maximized:
            self.showNormal()
            self._is_maximized = False
        else:
            self.showMaximized()
            self._is_maximized = True

    def _on_close(self) -> None:
        """Close or minimize to tray."""
        if self._config.settings.startup.close_to_tray:
            self.hide()
        else:
            self.close()

    def show_from_tray(self) -> None:
        """Restore window from system tray."""
        self.show()
        self.activateWindow()
        self.raise_()
        if self._is_maximized:
            self.showMaximized()
        else:
            self.showNormal()

    def refresh_all(self) -> None:
        """Refresh all data (called by auto-refresh timer)."""
        self._explorer.refresh_data()

    def closeEvent(self, event) -> None:
        """Handle window close."""
        logger.info("Main window closing.")
        event.accept()
