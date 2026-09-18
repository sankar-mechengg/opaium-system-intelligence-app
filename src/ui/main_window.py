"""
OP(AI)UM — Main Window

The primary application window that combines:
- Native frameless chrome with a custom title bar (snap, shadow, Win+Arrow)
- Dashboard, Explorer, AI Chat and History panels
- Update banner, status bar and toast notifications
- Global hotkey handling and keyboard shortcuts
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import QByteArray, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices, QIcon, QKeySequence, QShortcut, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.config.config_manager import ConfigManager
from src.config.constants import AppConstants
from src.core.models import RecentItem
from src.services.hotkey import GlobalHotkey
from src.services.notifier import NotificationService
from src.ui.chat.chat_panel import ChatPanel
from src.ui.dashboard.dashboard_panel import DashboardPanel
from src.ui.explorer.explorer_panel import ExplorerPanel
from src.ui.history.history_panel import HistoryPanel
from src.ui.native_window import (
    HTCLIENT,
    HTCLOSE,
    HTMAXBUTTON,
    HTMINBUTTON,
    SC_MAXIMIZE,
    SC_MINIMIZE,
    SC_RESTORE,
    NativeFramelessMixin,
    system_menu_command,
)
from src.ui.notifications.toast import NotificationManager
from src.ui.settings.settings_dialog import SettingsDialog
from src.ui.theme import ThemeManager
from src.ui.title_bar import TitleBar
from src.undo.operation_journal import OperationJournal
from src.undo.undo_manager import UndoManager

TAB_INDEX = {"dashboard": 0, "explorer": 1, "chat": 2, "history": 3}


class MainWindow(NativeFramelessMixin, QMainWindow):
    """
    OP(AI)UM main application window.

    Signals:
        lock_requested(): user asked to lock the app.
        quit_requested(): user asked to quit from the window.
        settings_changed(): settings dialog saved.
    """

    lock_requested = Signal()
    quit_requested = Signal()
    settings_changed = Signal()
    check_updates_requested = Signal()
    wipe_requested = Signal()

    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._operation_journal = OperationJournal()
        self._undo_manager = UndoManager(self._operation_journal)
        self._force_close = False
        self._closing = False
        self._geometry_restored = False
        self._tray_hint_shown = False

        self._setup_window()
        self._build_ui()
        self._connect_signals()
        self._setup_shortcuts()

        self._hotkey = GlobalHotkey(self, self)
        self._hotkey.activated.connect(self.toggle_visibility)

        mgr = ThemeManager.instance()
        if mgr is not None:
            mgr.theme_applied.connect(self._on_theme_applied)

        logger.info("Main window initialized.")

    # === Setup ===

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.setWindowTitle(AppConstants.APP_NAME)
        self.setMinimumSize(AppConstants.MIN_WINDOW_WIDTH, AppConstants.MIN_WINDOW_HEIGHT)
        # Frameless via native hit-testing; keeping the normal Window type preserves
        # taskbar preview, Alt+Tab, Snap Layouts and DWM shadow.
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        icon_path = AppConstants.LOGO_ICO_PATH if AppConstants.LOGO_ICO_PATH.exists() else AppConstants.LOGO_PATH
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._restore_geometry()

    def _restore_geometry(self) -> None:
        a = self._config.settings.appearance
        w = max(AppConstants.MIN_WINDOW_WIDTH, int(a.window_width or AppConstants.DEFAULT_WINDOW_WIDTH))
        h = max(AppConstants.MIN_WINDOW_HEIGHT, int(a.window_height or AppConstants.DEFAULT_WINDOW_HEIGHT))
        self.resize(w, h)

        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        if a.window_x is not None and a.window_y is not None and avail is not None:
            # Only reuse the saved position when it is still on a visible screen.
            for s in QApplication.screens():
                if s.availableGeometry().contains(QPoint(a.window_x + 50, a.window_y + 50)):
                    self.move(a.window_x, a.window_y)
                    self._geometry_restored = True
                    break
        if not self._geometry_restored and avail is not None:
            self.move(avail.center().x() - w // 2, avail.center().y() - h // 2)
            self._geometry_restored = True

    def _save_geometry(self) -> None:
        try:
            a = self._config.settings.appearance
            if not self.isMaximized() and not self.isMinimized():
                a.window_width = self.width()
                a.window_height = self.height()
                a.window_x = self.x()
                a.window_y = self.y()
            self._config.settings.was_maximized = self.isMaximized()
            self._config.save()
        except Exception as e:
            logger.debug(f"Could not persist window geometry: {e}")

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("mainCentral")
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Title bar
        self._title_bar = TitleBar()
        self._title_bar.set_lock_visible(self._config.is_auth_configured())
        main_layout.addWidget(self._title_bar)

        # Update banner (hidden until an update is found)
        self._update_banner = self._build_update_banner()
        main_layout.addWidget(self._update_banner)

        # Stacked panels
        self._stack = QStackedWidget()
        self._stack.setObjectName("mainStack")

        self._dashboard = DashboardPanel(self._config, self._undo_manager)
        self._stack.addWidget(self._dashboard)

        self._explorer = ExplorerPanel(self._config, self._operation_journal)
        self._stack.addWidget(self._explorer)

        self._chat = ChatPanel(self._config, self._undo_manager, self._operation_journal)
        self._stack.addWidget(self._chat)

        self._history = HistoryPanel(self._undo_manager)
        self._stack.addWidget(self._history)

        self._stack.setCurrentIndex(TAB_INDEX["explorer"])
        main_layout.addWidget(self._stack, stretch=1)

        # Status bar
        status = QWidget()
        status.setObjectName("statusBar")
        status.setFixedHeight(24)
        status_layout = QHBoxLayout(status)
        status_layout.setContentsMargins(12, 0, 12, 0)
        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("statusLabel")
        status_layout.addWidget(self._status_label)
        status_layout.addStretch()
        self._status_right = QLabel(f"v{AppConstants.APP_VERSION}")
        self._status_right.setObjectName("statusLabel")
        status_layout.addWidget(self._status_right)
        main_layout.addWidget(status)

        # Notifications (overlay) + service
        self._toasts = NotificationManager(central)
        self._notifier = NotificationService(self._config, self._toasts, self, self)

    def _build_update_banner(self) -> QWidget:
        banner = QWidget()
        banner.setObjectName("updateBanner")
        banner.setFixedHeight(38)
        banner.hide()
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(16, 0, 8, 0)
        layout.setSpacing(10)

        self._update_text = QLabel("")
        self._update_text.setObjectName("updateBannerText")
        layout.addWidget(self._update_text, stretch=1)

        get_btn = QPushButton("Download")
        get_btn.setObjectName("updateBannerBtn")
        get_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        get_btn.clicked.connect(self._open_release_page)
        layout.addWidget(get_btn)

        skip_btn = QPushButton("Skip this version")
        skip_btn.setObjectName("updateBannerClose")
        skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        skip_btn.clicked.connect(self._skip_update)
        layout.addWidget(skip_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("updateBannerClose")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(banner.hide)
        layout.addWidget(close_btn)

        self._update_url = AppConstants.RELEASES_URL
        self._update_version = ""
        return banner

    def _connect_signals(self) -> None:
        # Title bar
        self._title_bar.tab_changed.connect(self._on_tab_changed)
        self._title_bar.settings_clicked.connect(self.show_settings)
        self._title_bar.lock_clicked.connect(self.lock_requested.emit)
        self._title_bar.minimize_clicked.connect(self._on_minimize)
        self._title_bar.maximize_clicked.connect(self.toggle_maximize)
        self._title_bar.close_clicked.connect(self._on_close)

        # Explorer → Chat context
        self._explorer.item_selected.connect(self._on_item_selected)
        self._explorer.ask_ai_requested.connect(self._on_ask_ai)
        self._explorer.status_message.connect(self.set_status)
        self._explorer.operation_recorded.connect(self._on_explorer_operation)

        # Chat → Explorer refresh
        self._chat.operation_completed.connect(self._on_operation_completed)
        self._chat.undo_requested.connect(self._on_undo_requested)
        self._chat.status_message.connect(self.set_status)
        self._chat.notify.connect(self._on_chat_notify)

        # History → Refresh
        self._history.operation_undone.connect(self._on_operation_undone)

        # Dashboard → navigation
        self._dashboard.open_folder_requested.connect(self.navigate_to)
        self._dashboard.ask_ai_requested.connect(self._on_ask_ai)
        self._dashboard.switch_tab_requested.connect(self.switch_tab)

    def _setup_shortcuts(self) -> None:
        def sc(seq: str, slot: object) -> None:
            shortcut = QShortcut(QKeySequence(seq), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
            shortcut.activated.connect(slot)  # type: ignore[arg-type]

        sc("Ctrl+1", lambda: self.switch_tab("dashboard"))
        sc("Ctrl+2", lambda: self.switch_tab("explorer"))
        sc("Ctrl+3", lambda: self.switch_tab("chat"))
        sc("Ctrl+4", lambda: self.switch_tab("history"))
        sc("Ctrl+L", self.lock_requested.emit)
        sc("Ctrl+,", self.show_settings)
        sc("F5", self.refresh_all)
        sc("Ctrl+K", self._focus_chat)
        sc("Ctrl+Shift+Z", self._undo_last)
        sc("Ctrl+Q", self.quit_requested.emit)

    # === Native frame integration ===

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._init_native_frame()
        mgr = ThemeManager.instance()
        if mgr is not None:
            self.set_dark_titlebar_hint(mgr.is_dark)
        self.apply_hotkey_setting()
        QTimer.singleShot(0, self._sync_maximize_icon)

    def nativeEvent(self, event_type: QByteArray, message: int) -> tuple[bool, int]:  # type: ignore[override]
        try:
            from src.ui.native_window import MSG

            msg = MSG.from_address(int(message))
            if self._hotkey.handle_native(int(msg.message), int(msg.wParam)):
                return True, 0
        except Exception:
            pass
        handled = self.native_event(event_type, message)
        if handled is not None:
            return handled
        return super().nativeEvent(event_type, message)

    def hit_test_widget(self, pos: QPoint) -> int:
        tb_pos = self._title_bar.mapFrom(self, pos)
        if self._title_bar.rect().contains(tb_pos):
            return self._title_bar.hit_test(tb_pos)
        return HTCLIENT

    def on_caption_button_hover(self, ht: int) -> None:
        self._title_bar.set_control_hover(ht)

    def on_caption_button_click(self, ht: int) -> None:
        self._title_bar.set_control_hover(0)
        if ht == HTMINBUTTON:
            self._on_minimize()
        elif ht == HTMAXBUTTON:
            self.toggle_maximize()
        elif ht == HTCLOSE:
            self._on_close()

    def changeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            QTimer.singleShot(0, self._sync_maximize_icon)

    def _sync_maximize_icon(self) -> None:
        self._title_bar.update_maximize_icon(self.isMaximized())

    # === Navigation ===

    def _on_tab_changed(self, tab_id: str) -> None:
        index = TAB_INDEX.get(tab_id, 1)
        self._stack.setCurrentIndex(index)
        if tab_id == "chat":
            self._chat.focus_input()
        elif tab_id == "history":
            self._history.refresh()
        elif tab_id == "dashboard":
            self._dashboard.refresh()
        logger.debug(f"Switched to tab: {tab_id}")

    def switch_tab(self, tab_id: str) -> None:
        self._title_bar.set_active_tab(tab_id)
        self._on_tab_changed(tab_id)

    def navigate_to(self, path: str) -> None:
        """Open a folder in the explorer tab."""
        self.switch_tab("explorer")
        self._explorer.navigate_to(path)

    def _focus_chat(self) -> None:
        self.switch_tab("chat")

    # === Settings ===

    def show_settings(self) -> None:
        dialog = SettingsDialog(self._config, self)
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.api_key_changed.connect(self._chat.reinitialize_ai)
        dialog.check_updates_requested.connect(self.check_updates_requested.emit)
        dialog.wipe_requested.connect(self.wipe_requested.emit)
        self._settings_dialog = dialog
        dialog.exec()
        self._settings_dialog = None

    def report_update_status(self, text: str) -> None:
        dialog = getattr(self, "_settings_dialog", None)
        if dialog is not None:
            dialog.set_update_status(text)
        self.set_status(text)

    def _on_settings_saved(self) -> None:
        mgr = ThemeManager.instance()
        if mgr is not None:
            mgr.apply(self._config.settings.appearance.theme)
        self._explorer.apply_settings()
        self._chat.reinitialize_ai()
        self._title_bar.set_lock_visible(self._config.is_auth_configured())
        self.apply_hotkey_setting()
        self._toasts.success("Settings saved.")
        self.settings_changed.emit()

    def apply_hotkey_setting(self) -> None:
        s = self._config.settings.startup
        if s.global_hotkey_enabled and s.global_hotkey:
            if self._hotkey.sequence != s.global_hotkey or not self._hotkey.is_registered:
                self._hotkey.register(s.global_hotkey)
        else:
            self._hotkey.unregister()

    def _on_theme_applied(self, effective: str) -> None:
        self.set_dark_titlebar_hint(effective == "dark")

    # === Item Selection ===

    def _on_item_selected(self, item: RecentItem) -> None:
        """Pass selected item context to chat panel."""
        self._chat.set_folder_context(item.path if item.is_folder else str(item.parent_path or item.path))

    def _on_ask_ai(self, question: str, path: str) -> None:
        """Handle AI question from context menu — switch to chat."""
        self.switch_tab("chat")
        self._chat.inject_ai_question(question, path)

    # === Operations ===

    def _on_operation_completed(self, description: str) -> None:
        """Refresh explorer after an AI operation."""
        self._explorer.refresh_data()
        self._dashboard.mark_dirty()
        self._notifier.success(description or "Operation completed.")

    def _on_explorer_operation(self, description: str) -> None:
        self._dashboard.mark_dirty()
        self._toasts.success(description)

    def _on_undo_requested(self, operation_id: int) -> None:
        """Handle undo from chat."""
        success, message = self._undo_manager.undo_by_id(operation_id)
        if success:
            self._toasts.info(message)
            self._explorer.refresh_data()
            self._history.refresh()
        else:
            self._toasts.error(message)

    def _undo_last(self) -> None:
        success, message = self._undo_manager.undo_last()
        (self._toasts.info if success else self._toasts.warning)(message)
        if success:
            self._explorer.refresh_data()
            self._history.refresh()

    def _on_operation_undone(self, message: str) -> None:
        """Handle undo from history panel."""
        self._explorer.refresh_data()
        self._toasts.info(message or "Operation undone.")

    def _on_chat_notify(self, kind: str, message: str) -> None:
        getattr(self._notifier, kind, self._notifier.info)(message)

    # === Updates ===

    def show_update_available(self, version: str, url: str, _notes: str) -> None:
        self._update_url = url or AppConstants.RELEASES_URL
        self._update_version = version
        self._update_text.setText(f"OP(AI)UM {version} is available — you are on {AppConstants.APP_VERSION}.")
        self._update_banner.show()

    def _open_release_page(self) -> None:
        QDesktopServices.openUrl(self._update_url)

    def _skip_update(self) -> None:
        if self._update_version:
            self._config.settings.updates.skipped_version = self._update_version
            self._config.save()
        self._update_banner.hide()

    # === Window Controls ===

    def set_status(self, text: str) -> None:
        self._status_label.setText(text or "Ready")

    def _on_minimize(self) -> None:
        system_menu_command(self, SC_MINIMIZE)

    def toggle_maximize(self) -> None:
        system_menu_command(self, SC_RESTORE if self.isMaximized() else SC_MAXIMIZE)

    def _on_close(self) -> None:
        """Close or minimize to tray."""
        self.close()

    def toggle_visibility(self) -> None:
        """Global hotkey: bring to front, or hide when already active."""
        if self.isVisible() and self.isActiveWindow() and not self.isMinimized():
            if self._config.settings.startup.minimize_to_tray:
                self.hide()
            else:
                self._on_minimize()
        else:
            self.show_from_tray()

    def show_from_tray(self) -> None:
        """Restore window from system tray / minimized state."""
        if self._config.settings.was_maximized and not self.isVisible():
            self.showMaximized()
        else:
            self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.raise_()
        self.activateWindow()

    def refresh_all(self) -> None:
        """Refresh all data (called by auto-refresh timer and F5)."""
        self._explorer.refresh_data()
        self._dashboard.refresh()
        if self._stack.currentIndex() == TAB_INDEX["history"]:
            self._history.refresh()

    def refresh_data(self) -> None:
        self.refresh_all()

    @property
    def explorer(self) -> ExplorerPanel:
        return self._explorer

    @property
    def undo_manager(self) -> UndoManager:
        return self._undo_manager

    @property
    def chat(self) -> ChatPanel:
        return self._chat

    @property
    def notifier(self) -> NotificationService:
        return self._notifier

    def shutdown(self) -> None:
        """Release native resources before the app exits."""
        self._hotkey.unregister()
        self._explorer.shutdown()
        self._chat.shutdown()
        self._save_geometry()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Intercept close to minimize to tray when configured."""
        if self._config.settings.startup.minimize_to_tray and not self._force_close:
            event.ignore()
            self._save_geometry()
            self.hide()
            if not self._tray_hint_shown:
                self._tray_hint_shown = True
                hotkey = self._config.settings.startup.global_hotkey or "the tray icon"
                self._notifier.notify(f"OP(AI)UM keeps running in the tray. Press {hotkey} to bring it back.")
        else:
            logger.info("Main window closing.")
            self._closing = True
            self.shutdown()
            event.accept()
            self.quit_requested.emit()

    @property
    def is_closing(self) -> bool:
        return self._closing

    def force_close(self) -> None:
        """Actually close the window (called from tray Quit action)."""
        if self._closing:
            return
        self._force_close = True
        self.close()
