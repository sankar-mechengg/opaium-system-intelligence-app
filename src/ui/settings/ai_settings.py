"""
OP(AI)UM — AI Settings Tab

OpenAI API key management, model selection,
and speech transcription settings.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QGroupBox, QFormLayout,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from loguru import logger

from src.config.config_manager import ConfigManager


class AISettings(QWidget):
    """
    AI configuration settings tab.

    Signals:
        settings_changed(): Any setting was modified.
        api_key_changed(): API key was updated.
    """

    settings_changed = Signal()
    api_key_changed = Signal()

    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._build_ui()
        self._load_current()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        # API Key
        api_group = QGroupBox("OpenAI API Key")
        api_group.setObjectName("settingsGroup")
        api_layout = QVBoxLayout(api_group)

        key_row = QHBoxLayout()
        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setPlaceholderText("sk-...")
        self._api_key_input.setMinimumHeight(36)
        key_row.addWidget(self._api_key_input, stretch=1)

        self._show_key_btn = QPushButton("Show")
        self._show_key_btn.setCheckable(True)
        self._show_key_btn.setFixedHeight(36)
        self._show_key_btn.setMinimumWidth(60)
        self._show_key_btn.clicked.connect(self._toggle_key_visibility)
        key_row.addWidget(self._show_key_btn)

        self._save_key_btn = QPushButton("Save Key")
        self._save_key_btn.setFixedHeight(36)
        self._save_key_btn.setMinimumWidth(80)
        self._save_key_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_key_btn.clicked.connect(self._save_api_key)
        key_row.addWidget(self._save_key_btn)

        api_layout.addLayout(key_row)

        api_note = QLabel("Your key is encrypted and stored locally. Never shared.")
        api_note.setObjectName("settingsNote")
        note_font = QFont()
        note_font.setPointSize(8)
        note_font.setItalic(True)
        api_note.setFont(note_font)
        api_layout.addWidget(api_note)

        self._key_status = QLabel("")
        self._key_status.setObjectName("settingsStatus")
        api_layout.addWidget(self._key_status)

        layout.addWidget(api_group)

        # Model
        model_group = QGroupBox("AI Model")
        model_group.setObjectName("settingsGroup")
        model_form = QFormLayout(model_group)

        self._model_combo = QComboBox()
        self._model_combo.addItems([
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4.1-nano",
            "gpt-4o",
            "gpt-4o-mini",
            "o4-mini",
        ])
        self._model_combo.setMinimumHeight(32)
        model_form.addRow("Chat Model:", self._model_combo)

        self._speech_model = QComboBox()
        self._speech_model.addItems(["gpt-4o-transcribe", "whisper-1"])
        self._speech_model.setMinimumHeight(32)
        model_form.addRow("Speech Model:", self._speech_model)

        layout.addWidget(model_group)
        layout.addStretch()

    def _load_current(self) -> None:
        settings = self._config.settings.ai
        # Show masked key
        api_key = self._config.get_api_key()
        if api_key:
            self._api_key_input.setText(api_key)
            self._key_status.setText("✅ API key is configured")
            self._key_status.setStyleSheet("color: #4CAF50;")
        else:
            self._key_status.setText("⚠️ No API key set")
            self._key_status.setStyleSheet("color: #FF9800;")

        # Model
        idx = self._model_combo.findText(settings.model)
        if idx >= 0:
            self._model_combo.setCurrentIndex(idx)

        idx = self._speech_model.findText(settings.speech_model)
        if idx >= 0:
            self._speech_model.setCurrentIndex(idx)

    def _connect_signals(self) -> None:
        self._model_combo.currentTextChanged.connect(lambda _: self.settings_changed.emit())
        self._speech_model.currentTextChanged.connect(lambda _: self.settings_changed.emit())

    def _toggle_key_visibility(self, checked: bool) -> None:
        if checked:
            self._api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._show_key_btn.setText("Hide")
        else:
            self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._show_key_btn.setText("Show")

    def _save_api_key(self) -> None:
        key = self._api_key_input.text().strip()
        if key:
            self._config.set_api_key(key)
            self._key_status.setText("✅ API key saved")
            self._key_status.setStyleSheet("color: #4CAF50;")
            self.api_key_changed.emit()
            logger.info("API key updated in settings.")
        else:
            self._key_status.setText("⚠️ Please enter a valid key")
            self._key_status.setStyleSheet("color: #FF9800;")

    def save(self) -> None:
        self._config.update("ai", "model", self._model_combo.currentText())
        self._config.update("ai", "speech_model", self._speech_model.currentText())
