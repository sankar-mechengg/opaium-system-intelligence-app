"""
OP(AI)UM — Security Settings Tab

Change password/PIN and manage authentication settings.
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from src.auth.auth_manager import AuthManager
from src.config.config_manager import ConfigManager
from src.config.defaults import PasswordType


class SecuritySettings(QWidget):
    """
    Security settings tab for password management.

    Signals:
        settings_changed(): Settings modified.
    """

    settings_changed = Signal()

    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._auth = AuthManager(config)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        # Current status
        status_group = QGroupBox("Authentication Status")
        status_group.setObjectName("settingsGroup")
        status_layout = QVBoxLayout(status_group)

        current_type = self._auth.password_type.value.upper()
        status_label = QLabel(f"Current method: {current_type}")
        status_label.setObjectName("settingsStatus")
        status_font = QFont()
        status_font.setPointSize(10)
        status_label.setFont(status_font)
        status_layout.addWidget(status_label)

        layout.addWidget(status_group)

        # Change password
        change_group = QGroupBox("Change Password / PIN")
        change_group.setObjectName("settingsGroup")
        change_form = QFormLayout(change_group)

        self._current_pwd = QLineEdit()
        self._current_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self._current_pwd.setPlaceholderText("Current PIN / password")
        self._current_pwd.setMinimumHeight(36)
        change_form.addRow("Current:", self._current_pwd)

        # Type selection
        self._type_group = QButtonGroup(self)
        self._pin_radio = QRadioButton("PIN (4-8 digits)")
        self._pwd_radio = QRadioButton("Password (6+ characters)")
        self._type_group.addButton(self._pin_radio, 0)
        self._type_group.addButton(self._pwd_radio, 1)

        if self._auth.password_type == PasswordType.PIN:
            self._pin_radio.setChecked(True)
        else:
            self._pwd_radio.setChecked(True)

        change_form.addRow("New Type:", self._pin_radio)
        change_form.addRow("", self._pwd_radio)

        self._new_pwd = QLineEdit()
        self._new_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_pwd.setPlaceholderText("New PIN / password")
        self._new_pwd.setMinimumHeight(36)
        change_form.addRow("New:", self._new_pwd)

        self._confirm_pwd = QLineEdit()
        self._confirm_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_pwd.setPlaceholderText("Confirm new PIN / password")
        self._confirm_pwd.setMinimumHeight(36)
        change_form.addRow("Confirm:", self._confirm_pwd)

        self._error_label = QLabel("")
        self._error_label.setObjectName("settingsError")
        self._error_label.setVisible(False)
        change_form.addRow(self._error_label)

        self._change_btn = QPushButton("Change Password")
        self._change_btn.setObjectName("settingsActionBtn")
        self._change_btn.setMinimumHeight(38)
        self._change_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        change_font = QFont()
        change_font.setBold(True)
        self._change_btn.setFont(change_font)
        self._change_btn.clicked.connect(self._on_change_password)
        change_form.addRow(self._change_btn)

        layout.addWidget(change_group)
        layout.addStretch()

    def _on_change_password(self) -> None:
        current = self._current_pwd.text()
        new_pwd = self._new_pwd.text()
        confirm = self._confirm_pwd.text()

        if not current:
            self._show_error("Please enter your current password.")
            return

        if not new_pwd:
            self._show_error("Please enter a new password.")
            return

        if new_pwd != confirm:
            self._show_error("New passwords do not match.")
            return

        new_type = PasswordType.PIN if self._pin_radio.isChecked() else PasswordType.PASSWORD

        try:
            success = self._auth.change_password(current, new_pwd, new_type)
            if success:
                self._error_label.setVisible(False)
                self._current_pwd.clear()
                self._new_pwd.clear()
                self._confirm_pwd.clear()
                QMessageBox.information(self, "Success", "Password changed successfully.")
                self.settings_changed.emit()
                logger.info("Password changed via settings.")
            else:
                self._show_error("Current password is incorrect.")
        except ValueError as e:
            self._show_error(str(e))

    def _show_error(self, msg: str) -> None:
        self._error_label.setText(msg)
        self._error_label.setVisible(True)

    def save(self) -> None:
        pass  # Password changes are saved immediately
