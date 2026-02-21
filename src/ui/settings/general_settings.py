"""
OP(AI)UM — General Settings Tab

Auto-refresh interval, startup behavior, undo purge,
and other general preferences.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QGroupBox, QFormLayout,
)
from PySide6.QtCore import Signal

from src.config.config_manager import ConfigManager
from src.ui.widgets.toggle_switch import ToggleSwitch


class GeneralSettings(QWidget):
    """
    General settings tab.

    Signals:
        settings_changed(): Any setting was modified.
    """

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

        # Refresh
        refresh_group = QGroupBox("Auto-Refresh")
        refresh_group.setObjectName("settingsGroup")
        refresh_form = QFormLayout(refresh_group)

        refresh_row = QHBoxLayout()
        refresh_label = QLabel("Enable Auto-Refresh")
        self._refresh_toggle = ToggleSwitch(checked=True)
        refresh_row.addWidget(refresh_label)
        refresh_row.addStretch()
        refresh_row.addWidget(self._refresh_toggle)
        refresh_form.addRow(refresh_row)

        self._refresh_interval = QSpinBox()
        self._refresh_interval.setRange(1, 60)
        self._refresh_interval.setSuffix(" minutes")
        self._refresh_interval.setMinimumHeight(32)
        refresh_form.addRow("Refresh Interval:", self._refresh_interval)

        layout.addWidget(refresh_group)

        # Startup
        startup_group = QGroupBox("Startup")
        startup_group.setObjectName("settingsGroup")
        startup_form = QFormLayout(startup_group)

        start_row = QHBoxLayout()
        start_label = QLabel("Start with Windows")
        self._startup_toggle = ToggleSwitch(checked=True)
        start_row.addWidget(start_label)
        start_row.addStretch()
        start_row.addWidget(self._startup_toggle)
        startup_form.addRow(start_row)

        minimize_row = QHBoxLayout()
        minimize_label = QLabel("Start Minimized to Tray")
        self._minimize_toggle = ToggleSwitch(checked=False)
        minimize_row.addWidget(minimize_label)
        minimize_row.addStretch()
        minimize_row.addWidget(self._minimize_toggle)
        startup_form.addRow(minimize_row)

        layout.addWidget(startup_group)

        # Undo
        undo_group = QGroupBox("Undo History")
        undo_group.setObjectName("settingsGroup")
        undo_form = QFormLayout(undo_group)

        self._purge_days = QSpinBox()
        self._purge_days.setRange(1, 30)
        self._purge_days.setSuffix(" days")
        self._purge_days.setMinimumHeight(32)
        undo_form.addRow("Auto-Purge After:", self._purge_days)

        layout.addWidget(undo_group)
        layout.addStretch()

    def _load_current(self) -> None:
        settings = self._config.settings
        self._refresh_toggle.setChecked(settings.refresh.auto_refresh_enabled, animate=False)
        # Convert seconds to minutes for display
        interval_minutes = settings.refresh.refresh_interval_seconds // 60
        self._refresh_interval.setValue(interval_minutes)
        self._startup_toggle.setChecked(settings.startup.start_with_windows, animate=False)
        self._minimize_toggle.setChecked(settings.startup.minimize_to_tray, animate=False)
        self._purge_days.setValue(settings.undo.purge_days)

    def _connect_signals(self) -> None:
        self._refresh_toggle.toggled.connect(lambda _: self.settings_changed.emit())
        self._refresh_interval.valueChanged.connect(lambda _: self.settings_changed.emit())
        self._startup_toggle.toggled.connect(lambda _: self.settings_changed.emit())
        self._minimize_toggle.toggled.connect(lambda _: self.settings_changed.emit())
        self._purge_days.valueChanged.connect(lambda _: self.settings_changed.emit())

    def save(self) -> None:
        # Convert minutes to seconds for storage
        interval_seconds = self._refresh_interval.value() * 60
        self._config.update("refresh", "auto_refresh_enabled", self._refresh_toggle.is_checked)
        self._config.update("refresh", "refresh_interval_seconds", interval_seconds)
        self._config.update("startup", "start_with_windows", self._startup_toggle.is_checked)
        self._config.update("startup", "minimize_to_tray", self._minimize_toggle.is_checked)
        self._config.update("undo", "purge_days", self._purge_days.value())
