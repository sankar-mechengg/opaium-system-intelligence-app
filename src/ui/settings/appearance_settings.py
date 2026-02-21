"""
OP(AI)UM — Appearance Settings Tab

Theme selection (light/dark), card size, hidden folder toggle,
and other visual preferences.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QGroupBox, QFormLayout,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from src.config.config_manager import ConfigManager
from src.ui.widgets.toggle_switch import ToggleSwitch


class AppearanceSettings(QWidget):
    """
    Appearance settings tab.

    Signals:
        theme_changed(str): Theme name changed.
        settings_changed(): Any setting was modified.
    """

    theme_changed = Signal(str)
    settings_changed = Signal()

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

        # Theme
        theme_group = QGroupBox("Theme")
        theme_group.setObjectName("settingsGroup")
        theme_layout = QFormLayout(theme_group)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["Light", "Dark"])
        self._theme_combo.setMinimumHeight(32)
        theme_layout.addRow("Color Theme:", self._theme_combo)

        layout.addWidget(theme_group)

        # Explorer Layout
        layout_group = QGroupBox("Explorer")
        layout_group.setObjectName("settingsGroup")
        layout_form = QFormLayout(layout_group)

        self._card_width = QSpinBox()
        self._card_width.setRange(120, 280)
        self._card_width.setSingleStep(10)
        self._card_width.setSuffix(" px")
        self._card_width.setMinimumHeight(32)
        layout_form.addRow("Card Width:", self._card_width)

        self._card_height = QSpinBox()
        self._card_height.setRange(100, 240)
        self._card_height.setSingleStep(10)
        self._card_height.setSuffix(" px")
        self._card_height.setMinimumHeight(32)
        layout_form.addRow("Card Height:", self._card_height)

        # Hidden folders toggle
        hidden_row = QHBoxLayout()
        hidden_label = QLabel("Show Hidden / System Folders")
        self._hidden_toggle = ToggleSwitch(checked=False)
        hidden_row.addWidget(hidden_label)
        hidden_row.addStretch()
        hidden_row.addWidget(self._hidden_toggle)
        layout_form.addRow(hidden_row)

        layout.addWidget(layout_group)
        layout.addStretch()

    def _load_current(self) -> None:
        """Load current settings into UI."""
        settings = self._config.settings.appearance
        self._theme_combo.setCurrentText(settings.theme.capitalize())
        self._card_width.setValue(settings.card_width)
        self._card_height.setValue(settings.card_height)
        self._hidden_toggle.setChecked(settings.show_hidden_folders, animate=False)

    def _connect_signals(self) -> None:
        self._theme_combo.currentTextChanged.connect(self._on_theme_changed)
        self._card_width.valueChanged.connect(self._on_changed)
        self._card_height.valueChanged.connect(self._on_changed)
        self._hidden_toggle.toggled.connect(self._on_changed)

    def _on_theme_changed(self, text: str) -> None:
        self.theme_changed.emit(text.lower())
        self._on_changed()

    def _on_changed(self) -> None:
        self.settings_changed.emit()

    def save(self) -> None:
        """Save current UI values to config."""
        self._config.update("appearance", "theme", self._theme_combo.currentText().lower())
        self._config.update("appearance", "card_width", self._card_width.value())
        self._config.update("appearance", "card_height", self._card_height.value())
        self._config.update("appearance", "show_hidden_folders", self._hidden_toggle.is_checked)
