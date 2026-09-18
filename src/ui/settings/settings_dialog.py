"""
OP(AI)UM — Settings Dialog

Tabbed dialog containing all settings pages: Appearance, General, AI and
Security. Theme changes preview live and are reverted on Cancel.
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget

from src.config.config_manager import ConfigManager
from src.config.constants import AppConstants
from src.ui.settings.ai_settings import AISettings
from src.ui.settings.appearance_settings import AppearanceSettings
from src.ui.settings.general_settings import GeneralSettings
from src.ui.settings.security_settings import SecuritySettings


class SettingsDialog(QDialog):
    """
    Signals:
        settings_saved(): All settings were saved.
        api_key_changed(): API key / endpoint changed (AI engine should reconfigure).
        check_updates_requested(): Manual update check.
        wipe_requested(): User confirmed a full data reset.
    """

    settings_saved = Signal()
    api_key_changed = Signal()
    check_updates_requested = Signal()
    wipe_requested = Signal()

    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._saved = False

        self.setWindowTitle(f"{AppConstants.APP_NAME} — Settings")
        self.setMinimumSize(640, 620)
        self.resize(700, 700)
        self.setModal(True)

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("settingsTabs")

        self._appearance = AppearanceSettings(self._config)
        self._tabs.addTab(self._appearance, "Appearance")

        self._general = GeneralSettings(self._config)
        self._tabs.addTab(self._general, "General")

        self._ai = AISettings(self._config)
        self._tabs.addTab(self._ai, "AI")

        self._security = SecuritySettings(self._config)
        self._tabs.addTab(self._security, "Security")

        layout.addWidget(self._tabs, stretch=1)

        footer = QHBoxLayout()
        version = QLabel(f"OP(AI)UM v{AppConstants.APP_VERSION}")
        version.setObjectName("settingsNote")
        footer.addWidget(version)
        footer.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(36)
        cancel_btn.setMinimumWidth(90)
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("settingsSaveBtn")
        save_btn.setMinimumHeight(36)
        save_btn.setMinimumWidth(100)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_font = QFont()
        save_font.setBold(True)
        save_btn.setFont(save_font)
        save_btn.clicked.connect(self._on_save)
        save_btn.setDefault(True)
        footer.addWidget(save_btn)

        layout.addLayout(footer)

    def _connect_signals(self) -> None:
        self._ai.api_key_changed.connect(self.api_key_changed.emit)
        self._general.check_updates_requested.connect(self.check_updates_requested.emit)
        self._security.wipe_requested.connect(self._on_wipe)

    def set_update_status(self, text: str) -> None:
        self._general.set_update_status(text)

    def _on_wipe(self) -> None:
        self.wipe_requested.emit()
        self.reject()

    def _on_save(self) -> None:
        try:
            self._appearance.save()
            self._general.save()
            self._ai.save()
            self._security.save()
            self._config.save()
            self._saved = True
            logger.info("Settings saved.")
            self.settings_saved.emit()
            self.accept()
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            QMessageBox.warning(self, "Error", f"Failed to save settings: {e}")

    def reject(self) -> None:
        if not self._saved:
            self._appearance.revert_preview()
        super().reject()
