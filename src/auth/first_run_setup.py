"""
OP(AI)UM — First Run Setup Wizard

Shown on the very first launch. Three steps:
1. Welcome & privacy summary
2. Optional PIN / password lock (can be skipped and enabled later)
3. Optional AI provider set-up (OpenAI key or a local endpoint)
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QFont, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.auth.auth_manager import AuthManager
from src.config.config_manager import ConfigManager
from src.config.constants import AppConstants
from src.config.defaults import PasswordType

STEPS = 3


class FirstRunSetup(QWidget):
    """
    Signals:
        setup_complete(): wizard finished.
        quit_requested(): user closed the wizard.
    """

    setup_complete = Signal()
    quit_requested = Signal()

    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._auth_manager = AuthManager(config)
        self._step = 0
        self._drag_position = QPoint()

        self._setup_window()
        self._build_ui()
        self._connect_signals()
        self._update_nav()

    def _setup_window(self) -> None:
        self.setObjectName("setupWindow")
        self.setWindowTitle(f"{AppConstants.APP_NAME} — Setup")
        self.setFixedSize(560, 700)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.center().x() - 280, geo.center().y() - 350)

    # === UI ===

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 16, 40, 28)
        main_layout.setSpacing(10)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setObjectName("authCloseBtn")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.quit_requested.emit)
        close_row.addWidget(close_btn)
        main_layout.addLayout(close_row)

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if AppConstants.LOGO_PATH.exists():
            pixmap = QPixmap(str(AppConstants.LOGO_PATH))
            logo_label.setPixmap(
                pixmap.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        main_layout.addWidget(logo_label)

        welcome = QLabel(f"Welcome to {AppConstants.APP_NAME}")
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_font = QFont()
        welcome_font.setPointSize(18)
        welcome_font.setBold(True)
        welcome.setFont(welcome_font)
        welcome.setObjectName("setupWelcome")
        main_layout.addWidget(welcome)

        full_name = QLabel(AppConstants.APP_FULL_NAME)
        full_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        full_name.setWordWrap(True)
        full_name.setObjectName("setupFullName")
        main_layout.addWidget(full_name)

        self._stack = QStackedWidget()
        main_layout.addWidget(self._stack, stretch=1)
        self._build_welcome_page()
        self._build_password_page()
        self._build_api_key_page()

        nav = QHBoxLayout()
        self._back_btn = QPushButton("Back")
        self._back_btn.setObjectName("setupBackBtn")
        self._back_btn.setMinimumHeight(40)
        nav.addWidget(self._back_btn)
        nav.addStretch()
        self._skip_btn = QPushButton("Skip for now")
        self._skip_btn.setObjectName("setupSkipBtn")
        self._skip_btn.setMinimumHeight(40)
        nav.addWidget(self._skip_btn)
        self._next_btn = QPushButton("Next")
        self._next_btn.setObjectName("setupNextBtn")
        self._next_btn.setMinimumHeight(40)
        self._next_btn.setMinimumWidth(130)
        next_font = QFont()
        next_font.setBold(True)
        self._next_btn.setFont(next_font)
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        nav.addWidget(self._next_btn)
        main_layout.addLayout(nav)

        self._step_label = QLabel("")
        self._step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._step_label.setObjectName("setupStep")
        main_layout.addWidget(self._step_label)

    def _build_welcome_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)
        title = QLabel("Your files, intelligently managed.")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        for text in (
            "•  A fast file explorer with a Recent view, breadcrumbs and live folder updates.",
            "•  An AI assistant that counts, finds, organizes, renames, moves and cleans up files on request.",
            "•  Every destructive change is previewed first and can be undone from History.",
            "•  A dashboard with drives, largest folders, startup programs and live system stats.",
            "",
            "Privacy: settings and your API key stay on this PC, encrypted. Nothing is uploaded except the requests you "
            "send to your chosen AI provider.",
        ):
            label = QLabel(text)
            label.setWordWrap(True)
            label.setObjectName("setupDescription")
            layout.addWidget(label)
        layout.addStretch()
        self._stack.addWidget(page)

    def _build_password_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        title = QLabel("Protect OP(AI)UM with a PIN or password?")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        desc = QLabel(
            "Optional. When enabled, the lock screen appears at launch, after inactivity (configurable) and on Ctrl+L. "
            "You can turn it on or off later in Settings → Security."
        )
        desc.setWordWrap(True)
        desc.setObjectName("setupDescription")
        layout.addWidget(desc)

        self._type_group = QButtonGroup(self)
        self._pin_radio = QRadioButton("Numeric PIN (4–8 digits)")
        self._pin_radio.setChecked(True)
        self._type_group.addButton(self._pin_radio, 0)
        layout.addWidget(self._pin_radio)
        self._password_radio = QRadioButton("Password (6+ characters)")
        self._type_group.addButton(self._password_radio, 1)
        layout.addWidget(self._password_radio)

        self._pwd_input = QLineEdit()
        self._pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pwd_input.setMinimumHeight(42)
        self._pwd_input.setPlaceholderText("Enter PIN (4–8 digits)")
        self._pwd_input.setObjectName("setupInput")
        layout.addWidget(self._pwd_input)

        self._confirm_input = QLineEdit()
        self._confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_input.setMinimumHeight(42)
        self._confirm_input.setPlaceholderText("Re-enter PIN")
        self._confirm_input.setObjectName("setupInput")
        layout.addWidget(self._confirm_input)

        self._pwd_error = QLabel("")
        self._pwd_error.setObjectName("setupError")
        self._pwd_error.setVisible(False)
        self._pwd_error.setWordWrap(True)
        layout.addWidget(self._pwd_error)

        warn = QLabel("Forgotten credentials cannot be recovered — only a full data reset removes the lock.")
        warn.setWordWrap(True)
        warn.setObjectName("setupNote")
        layout.addWidget(warn)
        layout.addStretch()
        self._stack.addWidget(page)

    def _build_api_key_page(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        title = QLabel("Connect an AI provider")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        desc = QLabel(
            "OP(AI)UM uses OpenAI models for chat, file operations and voice input. Paste your OpenAI API key below, "
            "or skip and point it at a local OpenAI-compatible server (Ollama, LM Studio) in Settings → AI."
        )
        desc.setWordWrap(True)
        desc.setObjectName("setupDescription")
        layout.addWidget(desc)

        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setMinimumHeight(42)
        self._api_key_input.setPlaceholderText("sk-…")
        self._api_key_input.setObjectName("setupInput")
        layout.addWidget(self._api_key_input)

        self._show_key_btn = QPushButton("Show key")
        self._show_key_btn.setCheckable(True)
        self._show_key_btn.setObjectName("setupShowKeyBtn")
        self._show_key_btn.clicked.connect(self._toggle_key_visibility)
        layout.addWidget(self._show_key_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        note = QLabel("The key is encrypted with a machine-bound key and stored only in your AppData folder.")
        note.setWordWrap(True)
        note.setObjectName("setupNote")
        layout.addWidget(note)

        self._api_error = QLabel("")
        self._api_error.setObjectName("setupError")
        self._api_error.setVisible(False)
        layout.addWidget(self._api_error)
        layout.addStretch()
        self._stack.addWidget(page)

    # === Navigation ===

    def _connect_signals(self) -> None:
        self._next_btn.clicked.connect(self._on_next)
        self._back_btn.clicked.connect(self._on_back)
        self._skip_btn.clicked.connect(self._on_skip)
        self._type_group.idToggled.connect(self._on_type_changed)

    def _update_nav(self) -> None:
        self._stack.setCurrentIndex(self._step)
        self._back_btn.setVisible(self._step > 0)
        self._skip_btn.setVisible(self._step in (1, 2))
        self._next_btn.setText("Get started" if self._step == 0 else "Finish" if self._step == STEPS - 1 else "Next")
        self._step_label.setText(f"Step {self._step + 1} of {STEPS}")

    def _on_type_changed(self, id: int, checked: bool) -> None:
        if not checked:
            return
        if id == 0:
            self._pwd_input.setPlaceholderText("Enter PIN (4–8 digits)")
            self._confirm_input.setPlaceholderText("Re-enter PIN")
        else:
            self._pwd_input.setPlaceholderText("Enter password (6+ characters)")
            self._confirm_input.setPlaceholderText("Re-enter password")

    def _on_next(self) -> None:
        if self._step == 1:
            if self._pwd_input.text() or self._confirm_input.text():
                if not self._validate_password_step():
                    return
            # Empty fields on "Next" behave like skip (lock stays off)
        if self._step == STEPS - 1:
            self._finish_setup()
            return
        self._step += 1
        self._update_nav()

    def _on_back(self) -> None:
        if self._step > 0:
            self._step -= 1
            self._update_nav()

    def _on_skip(self) -> None:
        if self._step == STEPS - 1:
            self._finish_setup(skip_key=True)
            return
        self._step += 1
        self._update_nav()

    def _validate_password_step(self) -> bool:
        password = self._pwd_input.text()
        confirm = self._confirm_input.text()
        if password != confirm:
            self._show_pwd_error("Entries do not match. Please try again.")
            return False
        password_type = PasswordType.PIN if self._pin_radio.isChecked() else PasswordType.PASSWORD
        try:
            if self._auth_manager.setup_password(password, password_type):
                self._pwd_error.setVisible(False)
                return True
            self._show_pwd_error("Failed to set up the lock.")
            return False
        except ValueError as e:
            self._show_pwd_error(str(e))
            return False

    def _finish_setup(self, skip_key: bool = False) -> None:
        api_key = "" if skip_key else self._api_key_input.text().strip()
        if api_key:
            if len(api_key) < 20:
                self._api_error.setText("That does not look like a valid API key.")
                self._api_error.setVisible(True)
                return
            self._config.set_api_key(api_key)
            logger.info("API key saved during setup.")
        logger.info("First-run setup completed.")
        self.setup_complete.emit()
        self.close()

    def _show_pwd_error(self, message: str) -> None:
        self._pwd_error.setText(message)
        self._pwd_error.setVisible(True)

    def _toggle_key_visibility(self, checked: bool) -> None:
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
        self._show_key_btn.setText("Hide key" if checked else "Show key")

    # === Window dragging ===

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
