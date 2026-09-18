"""
OP(AI)UM — AI Settings Tab

API key, endpoint (OpenAI or any OpenAI-compatible server), model selection,
connection test, streaming / confirmation behaviour and voice options.
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.config.config_manager import ConfigManager, enum_value
from src.config.constants import AppConstants
from src.ui.widgets.toggle_switch import ToggleSwitch
from src.utils.thread_pool import ThreadPoolManager, Worker

ENDPOINT_PRESETS: list[tuple[str, str, str]] = [
    # label, base_url, suggested model
    ("OpenAI (default)", "", AppConstants.DEFAULT_AI_MODEL),
    ("Ollama (local)", "http://localhost:11434/v1", "llama3.1"),
    ("LM Studio (local)", "http://localhost:1234/v1", "local-model"),
    ("OpenRouter", "https://openrouter.ai/api/v1", "openai/gpt-4.1-mini"),
    ("Groq", "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    ("Custom…", "", ""),
]


class AISettings(QWidget):
    """
    Signals:
        settings_changed(): Any setting was modified.
        api_key_changed(): API key / endpoint was saved.
    """

    settings_changed = Signal()
    api_key_changed = Signal()

    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._testing = False
        self._build_ui()
        self._load_current()
        self._connect_signals()

    def _toggle_row(self, form: QFormLayout, label: str, checked: bool = False) -> ToggleSwitch:
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        row.addStretch()
        toggle = ToggleSwitch(checked=checked)
        row.addWidget(toggle)
        form.addRow(row)
        return toggle

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        # Endpoint + key
        api_group = QGroupBox("Provider")
        api_group.setObjectName("settingsGroup")
        api_form = QFormLayout(api_group)

        self._preset_combo = QComboBox()
        for label, _url, _model in ENDPOINT_PRESETS:
            self._preset_combo.addItem(label)
        self._preset_combo.setMinimumHeight(32)
        api_form.addRow("Endpoint:", self._preset_combo)

        self._base_url = QLineEdit()
        self._base_url.setPlaceholderText("Leave empty for api.openai.com — or http://localhost:11434/v1 for Ollama")
        self._base_url.setMinimumHeight(32)
        api_form.addRow("Base URL:", self._base_url)

        key_row = QHBoxLayout()
        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setPlaceholderText("sk-…  (optional for local servers)")
        self._api_key_input.setMinimumHeight(32)
        key_row.addWidget(self._api_key_input, stretch=1)
        self._show_key_btn = QPushButton("Show")
        self._show_key_btn.setCheckable(True)
        self._show_key_btn.setMinimumHeight(32)
        self._show_key_btn.clicked.connect(self._toggle_key_visibility)
        key_row.addWidget(self._show_key_btn)
        api_form.addRow("API key:", key_row)

        note = QLabel(
            "Your key is encrypted with a machine-bound key and never leaves this PC except to call the provider."
        )
        note.setObjectName("settingsNote")
        note.setWordWrap(True)
        api_form.addRow(note)

        test_row = QHBoxLayout()
        self._key_status = QLabel("")
        self._key_status.setObjectName("settingsStatus")
        self._key_status.setWordWrap(True)
        test_row.addWidget(self._key_status, stretch=1)
        self._test_btn = QPushButton("Save && test connection")
        self._test_btn.setObjectName("settingsActionBtn")
        self._test_btn.setMinimumHeight(32)
        self._test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._test_btn.clicked.connect(self._save_and_test)
        test_row.addWidget(self._test_btn)
        api_form.addRow(test_row)
        layout.addWidget(api_group)

        # Model
        model_group = QGroupBox("Model")
        model_group.setObjectName("settingsGroup")
        model_form = QFormLayout(model_group)

        model_row = QHBoxLayout()
        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        self._model_combo.addItems(AppConstants.AVAILABLE_AI_MODELS)
        self._model_combo.setMinimumHeight(32)
        model_row.addWidget(self._model_combo, stretch=1)
        self._fetch_btn = QPushButton("Fetch models")
        self._fetch_btn.setMinimumHeight(32)
        self._fetch_btn.setToolTip("Ask the endpoint for its available models")
        self._fetch_btn.clicked.connect(self._fetch_models)
        model_row.addWidget(self._fetch_btn)
        model_form.addRow("Chat model:", model_row)

        self._speech_model = QComboBox()
        self._speech_model.addItems(AppConstants.AVAILABLE_TRANSCRIPTION_MODELS)
        self._speech_model.setMinimumHeight(32)
        model_form.addRow("Speech model:", self._speech_model)

        self._timeout = QSpinBox()
        self._timeout.setRange(15, 600)
        self._timeout.setSuffix(" s")
        self._timeout.setMinimumHeight(32)
        model_form.addRow("Request timeout:", self._timeout)

        self._max_rounds = QSpinBox()
        self._max_rounds.setRange(1, 20)
        self._max_rounds.setMinimumHeight(32)
        model_form.addRow("Max tool calls per turn:", self._max_rounds)
        layout.addWidget(model_group)

        # Behaviour
        behaviour_group = QGroupBox("Behaviour")
        behaviour_group.setObjectName("settingsGroup")
        behaviour_form = QFormLayout(behaviour_group)
        self._streaming_toggle = self._toggle_row(behaviour_form, "Stream answers as they are generated", True)
        self._confirm_toggle = self._toggle_row(behaviour_form, "Ask before destructive operations (recommended)", True)
        self._voice_send_toggle = self._toggle_row(
            behaviour_form, "Send voice input automatically after transcription", False
        )
        warn = QLabel(
            "Turning confirmation off lets the AI rename, move, delete (to Recycle Bin) and write files without a preview."
        )
        warn.setObjectName("settingsNote")
        warn.setWordWrap(True)
        behaviour_form.addRow(warn)
        layout.addWidget(behaviour_group)

        layout.addStretch()

    def _load_current(self) -> None:
        ai = self._config.settings.ai
        api_key = self._config.get_api_key()
        self._api_key_input.setText(api_key)
        self._base_url.setText(ai.api_base_url)
        self._sync_preset_from_url(ai.api_base_url)
        self._model_combo.setCurrentText(ai.ai_model)
        idx = self._speech_model.findText(enum_value(ai.transcription_model))
        if idx >= 0:
            self._speech_model.setCurrentIndex(idx)
        self._timeout.setValue(ai.request_timeout)
        self._max_rounds.setValue(ai.max_tool_rounds)
        self._streaming_toggle.setChecked(ai.streaming, animate=False)
        self._confirm_toggle.setChecked(ai.confirm_destructive, animate=False)
        self._voice_send_toggle.setChecked(ai.voice_auto_send, animate=False)
        if api_key or ai.api_base_url:
            self._set_status("Configured. Press “Save & test connection” to verify.", "ok")
        else:
            self._set_status("No API key set — AI features are disabled until you add one.", "warn")

    def _connect_signals(self) -> None:
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        self._base_url.textEdited.connect(lambda _t: self.settings_changed.emit())
        self._model_combo.currentTextChanged.connect(lambda _t: self.settings_changed.emit())
        self._speech_model.currentTextChanged.connect(lambda _t: self.settings_changed.emit())
        self._timeout.valueChanged.connect(lambda _v: self.settings_changed.emit())
        self._max_rounds.valueChanged.connect(lambda _v: self.settings_changed.emit())
        for t in (self._streaming_toggle, self._confirm_toggle, self._voice_send_toggle):
            t.toggled.connect(lambda _c: self.settings_changed.emit())

    # === Helpers ===

    def _set_status(self, text: str, state: str = "") -> None:
        self._key_status.setText(text)
        self._key_status.setProperty("state", state)
        self._key_status.style().unpolish(self._key_status)
        self._key_status.style().polish(self._key_status)

    def _sync_preset_from_url(self, url: str) -> None:
        for i, (_label, preset_url, _model) in enumerate(ENDPOINT_PRESETS):
            if preset_url == url and (url or i == 0):
                self._preset_combo.blockSignals(True)
                self._preset_combo.setCurrentIndex(i)
                self._preset_combo.blockSignals(False)
                return
        self._preset_combo.blockSignals(True)
        self._preset_combo.setCurrentIndex(len(ENDPOINT_PRESETS) - 1)
        self._preset_combo.blockSignals(False)

    def _on_preset_changed(self, index: int) -> None:
        _label, url, model = ENDPOINT_PRESETS[index]
        if index == len(ENDPOINT_PRESETS) - 1:
            self._base_url.setFocus()
        else:
            self._base_url.setText(url)
            if model:
                self._model_combo.setCurrentText(model)
        self.settings_changed.emit()

    def _toggle_key_visibility(self, checked: bool) -> None:
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
        self._show_key_btn.setText("Hide" if checked else "Show")

    def _persist_provider(self) -> None:
        """Save key, base URL and model immediately (they are needed for testing)."""
        self._config.update("ai", "api_base_url", self._base_url.text().strip())
        self._config.update("ai", "ai_model", self._model_combo.currentText().strip() or AppConstants.DEFAULT_AI_MODEL)
        self._config.update("ai", "request_timeout", self._timeout.value())
        self._config.set_api_key(self._api_key_input.text().strip())  # saves
        self.api_key_changed.emit()

    def _save_and_test(self) -> None:
        if self._testing:
            return
        self._persist_provider()
        self._testing = True
        self._test_btn.setEnabled(False)
        self._set_status("Testing connection…", "")

        from src.ai.openai_client import OpenAIClient

        client = OpenAIClient(self._config)
        worker = Worker(client.test_connection)
        worker.signals.result.connect(self._on_test_result)
        worker.signals.error.connect(lambda err: self._on_test_result((False, str(err))))
        worker.signals.finished.connect(self._on_test_done)
        ThreadPoolManager.run(worker)

    def _on_test_result(self, result: object) -> None:
        ok, message = result if isinstance(result, tuple) else (False, str(result))
        self._set_status(message, "ok" if ok else "err")
        logger.info(f"Connection test: {ok} — {message}")

    def _on_test_done(self) -> None:
        self._testing = False
        self._test_btn.setEnabled(True)

    def _fetch_models(self) -> None:
        self._persist_provider()
        self._fetch_btn.setEnabled(False)
        self._set_status("Fetching models…", "")

        from src.ai.openai_client import OpenAIClient

        client = OpenAIClient(self._config)
        worker = Worker(client.list_models)
        worker.signals.result.connect(self._on_models)
        worker.signals.error.connect(lambda err: self._set_status(f"Could not list models: {err}", "err"))
        worker.signals.finished.connect(lambda: self._fetch_btn.setEnabled(True))
        ThreadPoolManager.run(worker)

    def _on_models(self, models: object) -> None:
        ids = [m for m in models if isinstance(m, str)] if isinstance(models, list) else []
        if not ids:
            self._set_status("The endpoint returned no models (it may not support listing).", "warn")
            return
        current = self._model_combo.currentText()
        self._model_combo.clear()
        self._model_combo.addItems(ids)
        self._model_combo.setCurrentText(current if current in ids else ids[0])
        self._set_status(f"{len(ids)} models available on this endpoint.", "ok")

    def save(self) -> None:
        from src.config.defaults import TranscriptionModel

        self._config.update("ai", "api_base_url", self._base_url.text().strip())
        self._config.update("ai", "ai_model", self._model_combo.currentText().strip() or AppConstants.DEFAULT_AI_MODEL)
        speech = self._speech_model.currentText()
        self._config.update(
            "ai",
            "transcription_model",
            TranscriptionModel(speech)
            if speech in [m.value for m in TranscriptionModel]
            else TranscriptionModel.GPT_4O_TRANSCRIBE,
        )
        self._config.update("ai", "request_timeout", self._timeout.value())
        self._config.update("ai", "max_tool_rounds", self._max_rounds.value())
        self._config.update("ai", "streaming", self._streaming_toggle.is_checked)
        self._config.update("ai", "confirm_destructive", self._confirm_toggle.is_checked)
        self._config.update("ai", "voice_auto_send", self._voice_send_toggle.is_checked)
        key = self._api_key_input.text().strip()
        if key != self._config.get_api_key():
            self._config.set_api_key(key)
