"""
OP(AI)UM — Security Settings Tab

Set up, change or remove the PIN / password lock, idle auto-lock, and the
documented reset path that wipes all local OP(AI)UM data.
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
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
from src.ui.widgets.toggle_switch import ToggleSwitch

IDLE_OPTIONS = [
    ("Never", 0),
    ("5 minutes", 5),
    ("10 minutes", 10),
    ("15 minutes", 15),
    ("30 minutes", 30),
    ("1 hour", 60),
]


class SecuritySettings(QWidget):
    """
    Signals:
        settings_changed(): Settings modified.
        auth_changed(): Lock was set up, changed or removed.
        wipe_requested(): User confirmed a full data reset (app should restart).
    """

    settings_changed = Signal()
    auth_changed = Signal()
    wipe_requested = Signal()

    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._auth = AuthManager(config)
        self._build_ui()
        self._load_current()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        # Status + lock set-up / change
        self._lock_group = QGroupBox("App lock")
        self._lock_group.setObjectName("settingsGroup")
        form = QFormLayout(self._lock_group)

        self._status_label = QLabel("")
        self._status_label.setObjectName("settingsStatus")

        self._status_label.setWordWrap(True)
        form.addRow(self._status_label)

        self._current_pwd = QLineEdit()
        self._current_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self._current_pwd.setPlaceholderText("Current PIN / password")
        self._current_pwd.setMinimumHeight(34)
        self._current_row_label = QLabel("Current:")
        form.addRow(self._current_row_label, self._current_pwd)

        self._type_group = QButtonGroup(self)
        self._pin_radio = QRadioButton("PIN (4–8 digits)")
        self._pwd_radio = QRadioButton("Password (6+ characters)")
        self._type_group.addButton(self._pin_radio, 0)
        self._type_group.addButton(self._pwd_radio, 1)
        self._pin_radio.setChecked(True)
        type_row = QHBoxLayout()
        type_row.addWidget(self._pin_radio)
        type_row.addWidget(self._pwd_radio)
        type_row.addStretch()
        form.addRow("Type:", type_row)

        self._new_pwd = QLineEdit()
        self._new_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_pwd.setPlaceholderText("New PIN / password")
        self._new_pwd.setMinimumHeight(34)
        form.addRow("New:", self._new_pwd)

        self._confirm_pwd = QLineEdit()
        self._confirm_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_pwd.setPlaceholderText("Confirm")
        self._confirm_pwd.setMinimumHeight(34)
        form.addRow("Confirm:", self._confirm_pwd)

        self._error_label = QLabel("")
        self._error_label.setObjectName("settingsError")

        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        form.addRow(self._error_label)

        btn_row = QHBoxLayout()
        self._apply_btn = QPushButton("Set up lock")
        self._apply_btn.setObjectName("settingsActionBtn")
        self._apply_btn.setMinimumHeight(36)
        self._apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(self._apply_btn)
        self._remove_btn = QPushButton("Remove lock")
        self._remove_btn.setObjectName("settingsDangerBtn")
        self._remove_btn.setMinimumHeight(36)
        self._remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remove_btn.clicked.connect(self._on_remove)
        btn_row.addWidget(self._remove_btn)
        btn_row.addStretch()
        form.addRow(btn_row)
        layout.addWidget(self._lock_group)

        # Auto-lock
        auto_group = QGroupBox("Automatic locking")
        auto_group.setObjectName("settingsGroup")
        auto_form = QFormLayout(auto_group)
        auto_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        auto_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._idle_combo = QComboBox()
        for label, minutes in IDLE_OPTIONS:
            self._idle_combo.addItem(label, minutes)
        self._idle_combo.setMinimumHeight(32)
        auto_form.addRow("Lock after inactivity:", self._idle_combo)
        tray_row = QHBoxLayout()
        tray_row.addWidget(QLabel("Lock when hidden to the tray"), stretch=1)
        self._lock_tray_toggle = ToggleSwitch(checked=False)
        tray_row.addWidget(self._lock_tray_toggle)
        auto_form.addRow(tray_row)
        self._auto_note = QLabel(
            "Automatic locking only applies while a PIN or password is set. Ctrl+L locks immediately."
        )
        self._auto_note.setObjectName("settingsNote")

        self._auto_note.setWordWrap(True)
        auto_form.addRow(self._auto_note)
        layout.addWidget(auto_group)

        # Danger zone
        danger_group = QGroupBox("Reset")
        danger_group.setObjectName("settingsGroup")
        danger_layout = QVBoxLayout(danger_group)
        danger_text = QLabel(
            "Forgot your PIN? Deleting all OP(AI)UM data (settings, API key, conversations, undo history and backups) "
            "removes the lock. Your files are never touched."
        )
        danger_text.setObjectName("settingsNote")

        danger_text.setWordWrap(True)
        danger_layout.addWidget(danger_text)
        wipe_btn = QPushButton("Delete all OP(AI)UM data…")
        wipe_btn.setObjectName("settingsDangerBtn")
        wipe_btn.setMinimumHeight(34)
        wipe_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        wipe_btn.clicked.connect(self._on_wipe)
        danger_layout.addWidget(wipe_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(danger_group)

        layout.addStretch()

        self._idle_combo.currentIndexChanged.connect(lambda _i: self.settings_changed.emit())
        self._lock_tray_toggle.toggled.connect(lambda _c: self.settings_changed.emit())

    def _load_current(self) -> None:
        configured = self._auth.is_configured
        if configured:
            self._status_label.setText(f"Lock is ON — {self._auth.password_type.value.upper()} required at launch.")
            self._status_label.setProperty("state", "ok")
            self._apply_btn.setText("Change PIN / password")
            self._pin_radio.setChecked(self._auth.password_type == PasswordType.PIN)
            self._pwd_radio.setChecked(self._auth.password_type != PasswordType.PIN)
        else:
            self._status_label.setText("Lock is OFF — anyone using this Windows account can open OP(AI)UM.")
            self._status_label.setProperty("state", "warn")
            self._apply_btn.setText("Set up lock")
        self._status_label.style().unpolish(self._status_label)
        self._status_label.style().polish(self._status_label)
        self._current_pwd.setVisible(configured)
        self._current_row_label.setVisible(configured)
        self._remove_btn.setVisible(configured)

        auth = self._config.settings.auth
        idx = self._idle_combo.findData(int(auth.idle_lock_minutes))
        self._idle_combo.setCurrentIndex(max(0, idx))
        self._lock_tray_toggle.setChecked(auth.lock_on_minimize_to_tray, animate=False)

    # === Actions ===

    def _on_apply(self) -> None:
        new_pwd = self._new_pwd.text()
        confirm = self._confirm_pwd.text()
        if not new_pwd:
            return self._show_error("Enter a new PIN or password.")
        if new_pwd != confirm:
            return self._show_error("The entries do not match.")
        new_type = PasswordType.PIN if self._pin_radio.isChecked() else PasswordType.PASSWORD

        try:
            if self._auth.is_configured:
                current = self._current_pwd.text()
                if not current:
                    return self._show_error("Enter your current PIN / password first.")
                ok = self._auth.change_password(current, new_pwd, new_type)
                if not ok:
                    return self._show_error("Current PIN / password is incorrect.")
            else:
                ok = self._auth.setup_password(new_pwd, new_type)
                if not ok:
                    return self._show_error("Could not set up the lock.")
        except ValueError as e:
            return self._show_error(str(e))

        self._error_label.setVisible(False)
        for field in (self._current_pwd, self._new_pwd, self._confirm_pwd):
            field.clear()
        self._load_current()
        QMessageBox.information(self, "Lock updated", "Your PIN / password has been saved.")
        logger.info("Auth updated via settings.")
        self.auth_changed.emit()
        return None

    def _on_remove(self) -> None:
        current = self._current_pwd.text()
        if not current:
            return self._show_error("Enter your current PIN / password to remove the lock.")
        if not self._auth.verify(current):
            return self._show_error("Current PIN / password is incorrect.")
        reply = QMessageBox.question(
            self,
            "Remove lock",
            "OP(AI)UM will open without asking for a PIN or password. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return None
        self._auth.reset_auth()
        self._current_pwd.clear()
        self._error_label.setVisible(False)
        self._load_current()
        self.auth_changed.emit()
        return None

    def _on_wipe(self) -> None:
        text, ok = QInputDialog.getText(
            self,
            "Delete all OP(AI)UM data",
            "This removes settings, the API key, conversations, undo history and content backups.\n"
            "OP(AI)UM will close and start fresh next time.\n\nType RESET to confirm:",
        )
        if not ok or text.strip().upper() != "RESET":
            return
        self.wipe_requested.emit()

    def _show_error(self, msg: str) -> None:
        self._error_label.setText(msg)
        self._error_label.setVisible(True)

    def save(self) -> None:
        self._config.update("auth", "idle_lock_minutes", int(self._idle_combo.currentData()))
        self._config.update("auth", "lock_on_minimize_to_tray", self._lock_tray_toggle.is_checked)
