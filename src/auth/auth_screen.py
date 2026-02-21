"""
OP(AI)UM — Authentication Screen

A branded lock screen that displays the OP(AI)UM logo and
prompts for PIN or password entry. Supports keyboard shortcuts
and visual feedback for incorrect entries.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QSpacerItem,
    QSizePolicy,
    QApplication,
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QPixmap, QFont, QKeyEvent, QMouseEvent
from loguru import logger

from src.auth.auth_manager import AuthManager
from src.config.config_manager import ConfigManager
from src.config.constants import AppConstants
from src.config.defaults import PasswordType


class AuthScreen(QWidget):
    """
    Lock screen widget displayed at app launch.

    Shows OP(AI)UM branding with a password/PIN input field.
    Emits `authenticated` signal on successful login.
    """

    authenticated = Signal()

    MAX_ATTEMPTS = 10
    LOCKOUT_SECONDS = 30

    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._auth_manager = AuthManager(config)
        self._attempts = 0
        
        # For dragging window
        self._drag_position = QPoint()

        self._setup_window()
        self._build_ui()
        self._connect_signals()

    def _setup_window(self) -> None:
        """Configure window properties."""
        self.setWindowTitle(f"{AppConstants.APP_NAME} — Locked")
        self.setFixedSize(480, 620)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        
        # Center the window on screen
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - 480) // 2
        y = (screen.height() - 620) // 2
        self.move(x, y)

    def _build_ui(self) -> None:
        """Build the authentication UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 40)
        layout.setSpacing(16)

        # === Close button (top-right) ===
        from PySide6.QtWidgets import QHBoxLayout
        close_row = QHBoxLayout()
        close_row.addStretch()
        self._close_btn = QPushButton("X")
        self._close_btn.setObjectName("authCloseBtn")
        self._close_btn.setFixedSize(32, 32)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setToolTip("Close application")
        self._close_btn.clicked.connect(self._close_app)
        close_row.addWidget(self._close_btn)
        layout.addLayout(close_row)

        # === Logo ===
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_path = AppConstants.LOGO_PATH
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            scaled = pixmap.scaled(
                180, 180,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo_label.setPixmap(scaled)
        layout.addWidget(logo_label)

        # === App Name ===
        name_label = QLabel(AppConstants.APP_NAME)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_font = QFont()
        name_font.setPointSize(22)
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setObjectName("authAppName")
        layout.addWidget(name_label)

        # === Subtitle ===
        subtitle = QLabel("System Intelligence Tool")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_font = QFont()
        subtitle_font.setPointSize(10)
        subtitle.setFont(subtitle_font)
        subtitle.setObjectName("authSubtitle")
        layout.addWidget(subtitle)

        layout.addSpacerItem(QSpacerItem(0, 30, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

        # === Separator ===
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("authSeparator")
        layout.addWidget(separator)

        layout.addSpacerItem(QSpacerItem(0, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

        # === Instruction ===
        password_type = self._auth_manager.password_type
        if password_type == PasswordType.PIN:
            instruction_text = "Enter your PIN to unlock"
        else:
            instruction_text = "Enter your password to unlock"

        instruction = QLabel(instruction_text)
        instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instruction_font = QFont()
        instruction_font.setPointSize(11)
        instruction.setFont(instruction_font)
        instruction.setObjectName("authInstruction")
        layout.addWidget(instruction)

        # === Password Input ===
        self._password_input = QLineEdit()
        self._password_input.setObjectName("authInput")
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        input_font = QFont()
        input_font.setPointSize(14)
        if password_type == PasswordType.PIN:
            input_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 8)
            self._password_input.setMaxLength(AppConstants.MAX_PIN_LENGTH)
            self._password_input.setPlaceholderText("• • • •")
        else:
            self._password_input.setPlaceholderText("Password")
            self._password_input.setMaxLength(AppConstants.MAX_PASSWORD_LENGTH)

        self._password_input.setFont(input_font)
        self._password_input.setMinimumHeight(50)
        layout.addWidget(self._password_input)

        # === Error Message (hidden initially) ===
        self._error_label = QLabel("")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setObjectName("authError")
        self._error_label.setVisible(False)
        error_font = QFont()
        error_font.setPointSize(9)
        self._error_label.setFont(error_font)
        layout.addWidget(self._error_label)

        # === Unlock Button ===
        self._unlock_btn = QPushButton("Unlock")
        self._unlock_btn.setObjectName("authUnlockBtn")
        self._unlock_btn.setMinimumHeight(46)
        unlock_font = QFont()
        unlock_font.setPointSize(12)
        unlock_font.setBold(True)
        self._unlock_btn.setFont(unlock_font)
        self._unlock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self._unlock_btn)

        layout.addStretch()

        # === Attempt Counter ===
        self._attempt_label = QLabel("")
        self._attempt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._attempt_label.setObjectName("authAttempts")
        attempt_font = QFont()
        attempt_font.setPointSize(8)
        self._attempt_label.setFont(attempt_font)
        layout.addWidget(self._attempt_label)

        # Focus on input
        self._password_input.setFocus()

    def _connect_signals(self) -> None:
        """Wire up signals."""
        self._unlock_btn.clicked.connect(self._attempt_unlock)
        self._password_input.returnPressed.connect(self._attempt_unlock)

    def _attempt_unlock(self) -> None:
        """Verify the entered password/PIN."""
        password = self._password_input.text().strip()
        if not password:
            self._show_error("Please enter your PIN or password.")
            return

        if self._auth_manager.verify(password):
            logger.info("Auth screen: unlock successful.")
            self.authenticated.emit()
            self.close()
        else:
            self._attempts += 1
            remaining = self.MAX_ATTEMPTS - self._attempts

            if remaining <= 0:
                self._show_error("Too many attempts. Please restart the application.")
                self._password_input.setEnabled(False)
                self._unlock_btn.setEnabled(False)
                return

            self._show_error(f"Incorrect. {remaining} attempts remaining.")
            self._shake_animation()
            self._password_input.clear()
            self._password_input.setFocus()

    def _show_error(self, message: str) -> None:
        """Display an error message."""
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    def _shake_animation(self) -> None:
        """Shake the input field on wrong password."""
        animation = QPropertyAnimation(self._password_input, b"pos")
        animation.setDuration(300)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        start_pos = self._password_input.pos()
        animation.setKeyValueAt(0, start_pos)
        animation.setKeyValueAt(0.15, start_pos + QPoint(12, 0))
        animation.setKeyValueAt(0.3, start_pos + QPoint(-12, 0))
        animation.setKeyValueAt(0.45, start_pos + QPoint(8, 0))
        animation.setKeyValueAt(0.6, start_pos + QPoint(-8, 0))
        animation.setKeyValueAt(0.75, start_pos + QPoint(4, 0))
        animation.setKeyValueAt(0.9, start_pos + QPoint(-4, 0))
        animation.setKeyValueAt(1, start_pos)

        # Keep a reference to prevent garbage collection
        self._shake_anim = animation
        animation.start()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events."""
        if event.key() == Qt.Key.Key_Escape:
            # Don't allow escape to close the auth screen
            event.ignore()
        else:
            super().keyPressEvent(event)
    
    def _close_app(self) -> None:
        """Close the application entirely."""
        QApplication.quit()

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
