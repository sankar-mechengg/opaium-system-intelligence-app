"""
OP(AI)UM — Appearance Settings Tab

Theme (system / light / dark, previewed live), explorer defaults and
card sizing.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QSpinBox, QVBoxLayout, QWidget

from src.config.config_manager import ConfigManager, enum_value
from src.ui.theme import ThemeManager
from src.ui.widgets.toggle_switch import ToggleSwitch

THEMES = [("Follow Windows", "system"), ("Light", "light"), ("Dark", "dark")]


class AppearanceSettings(QWidget):
    """
    Signals:
        theme_changed(str): Theme mode changed (previewed immediately).
        settings_changed(): Any setting was modified.
    """

    theme_changed = Signal(str)
    settings_changed = Signal()

    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._original_theme = config.theme_value
        self._build_ui()
        self._load_current()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        theme_group = QGroupBox("Theme")
        theme_group.setObjectName("settingsGroup")
        theme_layout = QFormLayout(theme_group)
        theme_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        theme_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._theme_combo = QComboBox()
        for label, key in THEMES:
            self._theme_combo.addItem(label, key)
        self._theme_combo.setMinimumHeight(32)
        theme_layout.addRow("Color theme:", self._theme_combo)

        note = QLabel("Changes preview instantly and are kept when you press Save.")
        note.setObjectName("settingsNote")

        note.setWordWrap(True)
        theme_layout.addRow(note)

        anim_row = QHBoxLayout()
        anim_row.addWidget(QLabel("Animations and transitions"), stretch=1)
        self._anim_toggle = ToggleSwitch(checked=True)
        anim_row.addWidget(self._anim_toggle)
        theme_layout.addRow(anim_row)
        layout.addWidget(theme_group)

        explorer_group = QGroupBox("Explorer")
        explorer_group.setObjectName("settingsGroup")
        explorer_form = QFormLayout(explorer_group)
        explorer_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        explorer_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._view_combo = QComboBox()
        self._view_combo.addItem("Grid of cards", "grid")
        self._view_combo.addItem("Details list", "list")
        self._view_combo.setMinimumHeight(32)
        explorer_form.addRow("Default view:", self._view_combo)

        self._card_width = QSpinBox()
        self._card_width.setRange(120, 280)
        self._card_width.setSingleStep(10)
        self._card_width.setSuffix(" px")
        self._card_width.setMinimumHeight(32)
        explorer_form.addRow("Card width:", self._card_width)

        self._card_height = QSpinBox()
        self._card_height.setRange(100, 240)
        self._card_height.setSingleStep(10)
        self._card_height.setSuffix(" px")
        self._card_height.setMinimumHeight(32)
        explorer_form.addRow("Card height:", self._card_height)

        folders_row = QHBoxLayout()
        folders_row.addWidget(QLabel("Show folders before files"), stretch=1)
        self._folders_first = ToggleSwitch(checked=True)
        folders_row.addWidget(self._folders_first)
        explorer_form.addRow(folders_row)

        hidden_row = QHBoxLayout()
        hidden_row.addWidget(QLabel("Show hidden and system items"), stretch=1)
        self._hidden_toggle = ToggleSwitch(checked=False)
        hidden_row.addWidget(self._hidden_toggle)
        explorer_form.addRow(hidden_row)

        layout.addWidget(explorer_group)
        layout.addStretch()

    def _load_current(self) -> None:
        a = self._config.settings.appearance
        idx = self._theme_combo.findData(enum_value(a.theme))
        self._theme_combo.setCurrentIndex(max(0, idx))
        self._anim_toggle.setChecked(a.animations_enabled, animate=False)
        idx = self._view_combo.findData(enum_value(a.explorer_view))
        self._view_combo.setCurrentIndex(max(0, idx))
        self._card_width.setValue(a.card_width)
        self._card_height.setValue(a.card_height)
        self._folders_first.setChecked(a.folders_first, animate=False)
        self._hidden_toggle.setChecked(a.show_hidden_folders, animate=False)

    def _connect_signals(self) -> None:
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        for w in (self._card_width, self._card_height):
            w.valueChanged.connect(lambda _v: self.settings_changed.emit())
        self._view_combo.currentIndexChanged.connect(lambda _i: self.settings_changed.emit())
        for t in (self._anim_toggle, self._folders_first, self._hidden_toggle):
            t.toggled.connect(lambda _c: self.settings_changed.emit())

    def _on_theme_changed(self, _index: int) -> None:
        mode = str(self._theme_combo.currentData())
        mgr = ThemeManager.instance()
        if mgr is not None:
            mgr.apply(mode)
        self.theme_changed.emit(mode)
        self.settings_changed.emit()

    def revert_preview(self) -> None:
        """Restore the saved theme if the dialog is cancelled."""
        mgr = ThemeManager.instance()
        if mgr is not None and mgr.mode != self._original_theme:
            mgr.apply(self._original_theme)

    def save(self) -> None:
        from src.config.defaults import ExplorerView, ThemeMode

        self._config.update("appearance", "theme", ThemeMode(str(self._theme_combo.currentData())))
        self._config.update("appearance", "animations_enabled", self._anim_toggle.is_checked)
        self._config.update("appearance", "explorer_view", ExplorerView(str(self._view_combo.currentData())))
        self._config.update("appearance", "card_width", self._card_width.value())
        self._config.update("appearance", "card_height", self._card_height.value())
        self._config.update("appearance", "folders_first", self._folders_first.is_checked)
        self._config.update("appearance", "show_hidden_folders", self._hidden_toggle.is_checked)
