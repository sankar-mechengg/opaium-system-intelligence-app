"""
OP(AI)UM — Settings Dialog

Tabbed dialog containing all settings pages:
Appearance, General, AI, and Security.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QPushButton,
    QWidget, QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from loguru import logger

from src.config.config_manager import ConfigManager
from src.ui.settings.appearance_settings import AppearanceSettings
from src.ui.settings.general_settings import GeneralSettings
from src.ui.settings.ai_settings import AISettings
from src.ui.settings.security_settings import SecuritySettings


class SettingsDialog(QDialog):
    """
    Main settings dialog with tabs.

    Signals:
        theme_changed(str): Theme was changed.
        settings_saved(): All settings were saved.
    """

    theme_changed = Signal(str)
    settings_saved = Signal()

    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config

        self.setWindowTitle("OP(AI)UM — Settings")
        self.setMinimumSize(560, 520)
        self.setMaximumSize(700, 650)
        self.setModal(True)

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Tabs
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

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(36)
        cancel_btn.setMinimumWidth(90)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("settingsSaveBtn")
        save_btn.setMinimumHeight(36)
        save_btn.setMinimumWidth(90)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_font = QFont()
        save_font.setBold(True)
        save_btn.setFont(save_font)
        save_btn.clicked.connect(self._on_save)
        save_btn.setDefault(True)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _connect_signals(self) -> None:
        self._appearance.theme_changed.connect(self.theme_changed.emit)
        self._ai.api_key_changed.connect(lambda: self.settings_saved.emit())

    def _on_save(self) -> None:
        """Save all settings tabs."""
        try:
            self._appearance.save()
            self._general.save()
            self._ai.save()
            self._security.save()
            self._config.save()

            logger.info("Settings saved.")
            self.settings_saved.emit()
            self.accept()
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            QMessageBox.warning(self, "Error", f"Failed to save settings: {e}")
