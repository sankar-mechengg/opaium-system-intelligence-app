"""
OP(AI)UM — Authentication Screen

A branded lock screen that prompts for the PIN or password. Failed attempts
trigger a progressive lockout (30 s, 60 s, 120 s…) instead of disabling the
app, and a documented reset path is offered for forgotten credentials.
"""

from __future__ import annotations

import time

from loguru import logger
from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QKeyEvent, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from src.auth.auth_manager import AuthManager
from src.config.config_manager import ConfigManager
from src.config.constants import AppConstants
from src.config.defaults import PasswordType

# Process-wide so re-locking (Ctrl+L) does not reset the lockout clock.
_FAILED_ATTEMPTS = 0
_LOCKED_UNTIL = 0.0


class AuthScreen(QWidget):
    """
    Lock screen shown at launch and whenever the app is locked.

    Signals:
        authenticated(): correct credentials entered.
        wipe_requested(): user chose to delete all data (forgot credentials).
        quit_requested(): user closed the lock screen.
    """

    authenticated = Signal()
    wipe_requested = Signal()
    quit_requested = Signal()

    def __init__(self, config: ConfigManager, parent: QWidget | None = None, is_relock: bool = False) -> None:
        super().__init__(parent)
        self._config = config
        self._auth_manager = AuthManager(config)
        self._is_relock = is_relock
        self._drag_position = QPoint()

        self._countdown = QTimer(self)
        self._countdown.setInterval(500)
        self._countdown.timeout.connect(self._update_lockout)

        self._setup_window()
        self._build_ui()
        self._connect_signals()
        self._update_lockout()

    def _setup_window(self) -> None:
        self.setObjectName("authWindow")
        self.setWindowTitle(f"{AppConstants.APP_NAME} — Locked")
        self.setFixedSize(460, 640)
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.center().x() - 230, geo.center().y() - 320)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 16, 40, 32)
        layout.setSpacing(14)

        close_row = QHBoxLayout()
        close_row.addStretch()
        self._close_btn = QPushButton("✕")
        self._close_btn.setObjectName("authCloseBtn")
        self._close_btn.setFixedSize(32, 32)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setToolTip("Quit OP(AI)UM")
        close_row.addWidget(self._close_btn)
        layout.addLayout(close_row)

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if AppConstants.LOGO_PATH.exists():
            pixmap = QPixmap(str(AppConstants.LOGO_PATH))
            logo_label.setPixmap(
                pixmap.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        layout.addWidget(logo_label)

        name_label = QLabel(AppConstants.APP_NAME)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_font = QFont()
        name_font.setPointSize(22)
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setObjectName("authAppName")
        layout.addWidget(name_label)

        full_name = QLabel(AppConstants.APP_FULL_NAME)
        full_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        full_name.setWordWrap(True)
        full_name.setObjectName("authSubtitle")
        layout.addWidget(full_name)

        layout.addSpacerItem(QSpacerItem(0, 16, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("authSeparator")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        password_type = self._auth_manager.password_type
        instruction = QLabel(
            ("Welcome back — " if self._is_relock else "")
            + ("enter your PIN to unlock" if password_type == PasswordType.PIN else "enter your password to unlock")
        )
        instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instruction_font = QFont()
        instruction_font.setPointSize(11)
        instruction.setFont(instruction_font)
        instruction.setObjectName("authInstruction")
        layout.addWidget(instruction)

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

        self._error_label = QLabel("")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setObjectName("authError")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

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

        self._attempt_label = QLabel("")
        self._attempt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._attempt_label.setObjectName("authAttempts")
        layout.addWidget(self._attempt_label)

        self._forgot_btn = QPushButton("Forgot your PIN or password?")
        self._forgot_btn.setObjectName("authLinkBtn")
        self._forgot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._forgot_btn.setFlat(True)
        layout.addWidget(self._forgot_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self._password_input.setFocus()

    def _connect_signals(self) -> None:
        self._unlock_btn.clicked.connect(self._attempt_unlock)
        self._password_input.returnPressed.connect(self._attempt_unlock)
        self._close_btn.clicked.connect(self._on_close)
        self._forgot_btn.clicked.connect(self._on_forgot)

    # === Lockout ===

    def _remaining_lockout(self) -> float:
        return max(0.0, _LOCKED_UNTIL - time.monotonic())

    def _update_lockout(self) -> None:
        remaining = self._remaining_lockout()
        if remaining > 0:
            self._password_input.setEnabled(False)
            self._unlock_btn.setEnabled(False)
            self._unlock_btn.setText(f"Try again in {int(remaining) + 1}s")
            if not self._countdown.isActive():
                self._countdown.start()
        else:
            if self._countdown.isActive():
                self._countdown.stop()
            self._password_input.setEnabled(True)
            self._unlock_btn.setEnabled(True)
            self._unlock_btn.setText("Unlock")
            if _FAILED_ATTEMPTS:
                self._attempt_label.setText(f"{_FAILED_ATTEMPTS} failed attempt{'s' if _FAILED_ATTEMPTS != 1 else ''}")

    def _register_failure(self) -> None:
        global _FAILED_ATTEMPTS, _LOCKED_UNTIL
        _FAILED_ATTEMPTS += 1
        over = _FAILED_ATTEMPTS - AppConstants.AUTH_FREE_ATTEMPTS
        if over >= 0:
            delay = AppConstants.AUTH_LOCKOUT_BASE_SECONDS * (2 ** min(over, 4))
            _LOCKED_UNTIL = time.monotonic() + delay
            self._show_error(f"Too many attempts. Locked for {delay} seconds.")
            logger.warning(f"Auth lockout for {delay}s after {_FAILED_ATTEMPTS} failures.")
        else:
            left = AppConstants.AUTH_FREE_ATTEMPTS - _FAILED_ATTEMPTS
            self._show_error(f"Incorrect. {left} attempt{'s' if left != 1 else ''} before a temporary lockout.")
        self._update_lockout()

    # === Actions ===

    def _attempt_unlock(self) -> None:
        global _FAILED_ATTEMPTS
        if self._remaining_lockout() > 0:
            return
        password = self._password_input.text().strip()
        if not password:
            self._show_error("Please enter your PIN or password.")
            return

        if self._auth_manager.verify(password):
            logger.info("Auth screen: unlock successful.")
            _FAILED_ATTEMPTS = 0
            self.authenticated.emit()
            self.close()
        else:
            self._register_failure()
            self._shake_animation()
            self._password_input.clear()
            self._password_input.setFocus()

    def _on_forgot(self) -> None:
        reply = QMessageBox.warning(
            self,
            "Reset OP(AI)UM",
            "There is no way to recover a lost PIN or password: the settings file is encrypted with it in mind.\n\n"
            "You can delete all OP(AI)UM data (settings, API key, conversations, undo history and backups) to start "
            "fresh. Your documents and files are never touched.\n\nDelete all OP(AI)UM data now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.wipe_requested.emit()

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    def _shake_animation(self) -> None:
        animation = QPropertyAnimation(self._password_input, b"pos")
        animation.setDuration(300)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        start_pos = self._password_input.pos()
        for t, dx in ((0, 0), (0.15, 12), (0.3, -12), (0.45, 8), (0.6, -8), (0.75, 4), (0.9, -4), (1, 0)):
            animation.setKeyValueAt(t, start_pos + QPoint(dx, 0))
        self._shake_anim = animation
        animation.start()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            event.ignore()
        else:
            super().keyPressEvent(event)

    def _on_close(self) -> None:
        self.quit_requested.emit()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
