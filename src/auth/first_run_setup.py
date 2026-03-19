"""
OP(AI)UM — First Run Setup Wizard

Displayed on the very first launch. Forces the user to set up
a PIN or password before accessing the application.
Also collects the OpenAI API key for AI features.
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QFont, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.auth.auth_manager import AuthManager
from src.config.config_manager import ConfigManager
from src.config.constants import AppConstants
from src.config.defaults import PasswordType


class FirstRunSetup(QWidget):
    """
    First-run wizard with two steps:
    1. Choose PIN or password, then set it
    2. Optionally enter OpenAI API key

    Emits `setup_complete` when finished.
    """

    setup_complete = Signal()

    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._auth_manager = AuthManager(config)
        self._current_step = 0

        # For dragging window
        self._drag_position = QPoint()

        self._setup_window()
        self._build_ui()
        self._connect_signals()

    def _setup_window(self) -> None:
        """Configure window."""
        self.setWindowTitle(f"{AppConstants.APP_NAME} — Setup")
        self.setFixedSize(520, 680)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)

        # Center the window on screen
        from PySide6.QtWidgets import QApplication

        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - 520) // 2
        y = (screen.height() - 680) // 2
        self.move(x, y)

    def _build_ui(self) -> None:
        """Build the wizard UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 30, 40, 30)
        main_layout.setSpacing(12)

        # === Logo + Welcome ===
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if AppConstants.LOGO_PATH.exists():
            pixmap = QPixmap(str(AppConstants.LOGO_PATH))
            scaled = pixmap.scaled(
                120,
                120,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo_label.setPixmap(scaled)
        main_layout.addWidget(logo_label)

        welcome_label = QLabel(f"Welcome to {AppConstants.APP_NAME}")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_font = QFont()
        welcome_font.setPointSize(18)
        welcome_font.setBold(True)
        welcome_label.setFont(welcome_font)
        welcome_label.setObjectName("setupWelcome")
        main_layout.addWidget(welcome_label)

        full_name_label = QLabel(AppConstants.APP_FULL_NAME)
        full_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        full_name_label.setWordWrap(True)
        fn_font = QFont()
        fn_font.setPointSize(9)
        full_name_label.setFont(fn_font)
        full_name_label.setObjectName("setupFullName")
        main_layout.addWidget(full_name_label)

        desc_label = QLabel("Let's set up your security and AI features.")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setObjectName("setupDescription")
        main_layout.addWidget(desc_label)

        main_layout.addSpacerItem(QSpacerItem(0, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

        # === Stacked Pages ===
        self._stack = QStackedWidget()
        main_layout.addWidget(self._stack, stretch=1)

        # Page 1: Password Setup
        self._build_password_page()

        # Page 2: API Key Setup
        self._build_api_key_page()

        # === Navigation Buttons ===
        nav_layout = QHBoxLayout()

        self._back_btn = QPushButton("Back")
        self._back_btn.setObjectName("setupBackBtn")
        self._back_btn.setMinimumHeight(40)
        self._back_btn.setVisible(False)
        nav_layout.addWidget(self._back_btn)

        nav_layout.addStretch()

        self._next_btn = QPushButton("Next")
        self._next_btn.setObjectName("setupNextBtn")
        self._next_btn.setMinimumHeight(40)
        self._next_btn.setMinimumWidth(120)
        next_font = QFont()
        next_font.setBold(True)
        self._next_btn.setFont(next_font)
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        nav_layout.addWidget(self._next_btn)

        main_layout.addLayout(nav_layout)

        # === Step Indicator ===
        self._step_label = QLabel("Step 1 of 2")
        self._step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._step_label.setObjectName("setupStep")
        main_layout.addWidget(self._step_label)

    def _build_password_page(self) -> None:
        """Build the password setup page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        # Auth type selection
        type_label = QLabel("Choose your security type:")
        type_font = QFont()
        type_font.setPointSize(11)
        type_font.setBold(True)
        type_label.setFont(type_font)
        layout.addWidget(type_label)

        self._type_group = QButtonGroup(self)

        self._pin_radio = QRadioButton("Numeric PIN (4-8 digits)")
        self._pin_radio.setChecked(True)
        self._type_group.addButton(self._pin_radio, 0)
        layout.addWidget(self._pin_radio)

        self._password_radio = QRadioButton("Alphanumeric Password (6+ characters)")
        self._type_group.addButton(self._password_radio, 1)
        layout.addWidget(self._password_radio)

        layout.addSpacerItem(QSpacerItem(0, 16, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

        # Password input
        pwd_label = QLabel("Enter your PIN / Password:")
        pwd_label.setObjectName("setupFieldLabel")
        layout.addWidget(pwd_label)

        self._pwd_input = QLineEdit()
        self._pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pwd_input.setMinimumHeight(44)
        self._pwd_input.setPlaceholderText("Enter PIN or password")
        self._pwd_input.setObjectName("setupInput")
        layout.addWidget(self._pwd_input)

        # Confirm input
        confirm_label = QLabel("Confirm:")
        confirm_label.setObjectName("setupFieldLabel")
        layout.addWidget(confirm_label)

        self._confirm_input = QLineEdit()
        self._confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_input.setMinimumHeight(44)
        self._confirm_input.setPlaceholderText("Re-enter PIN or password")
        self._confirm_input.setObjectName("setupInput")
        layout.addWidget(self._confirm_input)

        # Error label
        self._pwd_error = QLabel("")
        self._pwd_error.setObjectName("setupError")
        self._pwd_error.setVisible(False)
        layout.addWidget(self._pwd_error)

        layout.addStretch()
        self._stack.addWidget(page)

    def _build_api_key_page(self) -> None:
        """Build the API key setup page."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        api_title = QLabel("OpenAI API Key")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        api_title.setFont(title_font)
        layout.addWidget(api_title)

        api_desc = QLabel(
            "OP(AI)UM uses OpenAI's GPT models for intelligent file operations "
            "and voice commands. Enter your API key below.\n\n"
            "Your key is encrypted and stored locally on this machine only."
        )
        api_desc.setWordWrap(True)
        api_desc.setObjectName("setupDescription")
        layout.addWidget(api_desc)

        layout.addSpacerItem(QSpacerItem(0, 12, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

        key_label = QLabel("API Key:")
        key_label.setObjectName("setupFieldLabel")
        layout.addWidget(key_label)

        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setMinimumHeight(44)
        self._api_key_input.setPlaceholderText("sk-...")
        self._api_key_input.setObjectName("setupInput")
        layout.addWidget(self._api_key_input)

        # Show/hide toggle
        self._show_key_btn = QPushButton("Show Key")
        self._show_key_btn.setCheckable(True)
        self._show_key_btn.setObjectName("setupShowKeyBtn")
        self._show_key_btn.clicked.connect(self._toggle_key_visibility)
        layout.addWidget(self._show_key_btn)

        api_note = QLabel("You can skip this step and add the API key later in Settings.")
        api_note.setWordWrap(True)
        api_note.setObjectName("setupNote")
        layout.addWidget(api_note)

        self._api_error = QLabel("")
        self._api_error.setObjectName("setupError")
        self._api_error.setVisible(False)
        layout.addWidget(self._api_error)

        layout.addStretch()
        self._stack.addWidget(page)

    def _connect_signals(self) -> None:
        """Connect button signals."""
        self._next_btn.clicked.connect(self._on_next)
        self._back_btn.clicked.connect(self._on_back)
        self._type_group.idToggled.connect(self._on_type_changed)

    def _on_type_changed(self, id: int, checked: bool) -> None:
        """Update placeholder when type changes."""
        if not checked:
            return
        if id == 0:  # PIN
            self._pwd_input.setPlaceholderText("Enter PIN (4-8 digits)")
            self._confirm_input.setPlaceholderText("Re-enter PIN")
        else:  # Password
            self._pwd_input.setPlaceholderText("Enter password (6+ characters)")
            self._confirm_input.setPlaceholderText("Re-enter password")

    def _on_next(self) -> None:
        """Handle next button click."""
        if self._current_step == 0:
            if self._validate_password_step():
                self._current_step = 1
                self._stack.setCurrentIndex(1)
                self._back_btn.setVisible(True)
                self._next_btn.setText("Finish")
                self._step_label.setText("Step 2 of 2")
        elif self._current_step == 1:
            self._finish_setup()

    def _on_back(self) -> None:
        """Handle back button click."""
        if self._current_step == 1:
            self._current_step = 0
            self._stack.setCurrentIndex(0)
            self._back_btn.setVisible(False)
            self._next_btn.setText("Next")
            self._step_label.setText("Step 1 of 2")

    def _validate_password_step(self) -> bool:
        """Validate the password/PIN setup."""
        password = self._pwd_input.text()
        confirm = self._confirm_input.text()

        if not password:
            self._show_pwd_error("Please enter a PIN or password.")
            return False

        if password != confirm:
            self._show_pwd_error("Entries do not match. Please try again.")
            return False

        password_type = PasswordType.PIN if self._pin_radio.isChecked() else PasswordType.PASSWORD

        try:
            success = self._auth_manager.setup_password(password, password_type)
            if success:
                self._pwd_error.setVisible(False)
                return True
            else:
                self._show_pwd_error("Failed to set up authentication.")
                return False
        except ValueError as e:
            self._show_pwd_error(str(e))
            return False

    def _finish_setup(self) -> None:
        """Complete the setup wizard."""
        # Save API key if provided
        api_key = self._api_key_input.text().strip()
        if api_key:
            if not api_key.startswith("sk-"):
                self._api_error.setText("API key should start with 'sk-'. Please check.")
                self._api_error.setVisible(True)
                return
            self._config.set_api_key(api_key)
            logger.info("API key saved during setup.")

        logger.info("First-run setup completed.")
        self.setup_complete.emit()
        self.close()

    def _show_pwd_error(self, message: str) -> None:
        """Show password error."""
        self._pwd_error.setText(message)
        self._pwd_error.setVisible(True)

    def _toggle_key_visibility(self, checked: bool) -> None:
        """Toggle API key visibility."""
        if checked:
            self._api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._show_key_btn.setText("Hide Key")
        else:
            self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._show_key_btn.setText("Show Key")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Record position for window dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Move window when dragging."""
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
