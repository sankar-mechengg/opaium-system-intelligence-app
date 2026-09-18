"""
OP(AI)UM — General Settings Tab

Auto-refresh, startup & tray behaviour, notifications, global hotkey,
update checks and undo retention.
"""

from __future__ import annotations

import os
import subprocess

from loguru import logger
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.config.config_manager import ConfigManager
from src.config.constants import AppConstants
from src.services.hotkey import parse_hotkey
from src.ui.widgets.toggle_switch import ToggleSwitch
from src.undo.backup_store import BackupStore
from src.utils.path_utils import PathUtils


class GeneralSettings(QWidget):
    """
    Signals:
        settings_changed(): Any setting was modified.
        check_updates_requested(): User pressed "Check now".
    """

    settings_changed = Signal()
    check_updates_requested = Signal()

    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._build_ui()
        self._load_current()
        self._connect_signals()

    def _toggle_row(self, form: QFormLayout, label: str, checked: bool = False) -> ToggleSwitch:
        row = QHBoxLayout()
        text = QLabel(label)
        text.setWordWrap(True)
        text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(text, stretch=1)
        toggle = ToggleSwitch(checked=checked)
        row.addWidget(toggle, alignment=Qt.AlignmentFlag.AlignVCenter)
        form.addRow(row)
        return toggle

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        # Refresh
        refresh_group = QGroupBox("Auto-refresh")
        refresh_group.setObjectName("settingsGroup")
        refresh_form = QFormLayout(refresh_group)
        refresh_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        refresh_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._refresh_toggle = self._toggle_row(refresh_form, "Refresh recent items automatically", True)
        self._refresh_interval = QSpinBox()
        self._refresh_interval.setRange(1, 60)
        self._refresh_interval.setSuffix(" minutes")
        self._refresh_interval.setMinimumHeight(32)
        refresh_form.addRow("Refresh every:", self._refresh_interval)
        layout.addWidget(refresh_group)

        # Startup & tray
        startup_group = QGroupBox("Startup and tray")
        startup_group.setObjectName("settingsGroup")
        startup_form = QFormLayout(startup_group)
        startup_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        startup_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._startup_toggle = self._toggle_row(startup_form, "Start OP(AI)UM when Windows starts", False)
        self._start_min_toggle = self._toggle_row(startup_form, "Start minimized to the tray", False)
        self._tray_toggle = self._toggle_row(startup_form, "Closing the window keeps OP(AI)UM in the tray", True)
        self._notify_toggle = self._toggle_row(startup_form, "Windows notifications while hidden in the tray", True)
        layout.addWidget(startup_group)

        # Hotkey
        hotkey_group = QGroupBox("Global hotkey")
        hotkey_group.setObjectName("settingsGroup")
        hotkey_form = QFormLayout(hotkey_group)
        hotkey_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        hotkey_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._hotkey_toggle = self._toggle_row(hotkey_form, "Summon OP(AI)UM from anywhere", True)
        hotkey_row = QHBoxLayout()
        self._hotkey_edit = QKeySequenceEdit()
        self._hotkey_edit.setMinimumHeight(32)
        hotkey_row.addWidget(self._hotkey_edit, stretch=1)
        reset_btn = QPushButton("Default")
        reset_btn.setMinimumHeight(32)
        reset_btn.clicked.connect(
            lambda: self._hotkey_edit.setKeySequence(QKeySequence(AppConstants.DEFAULT_GLOBAL_HOTKEY))
        )
        hotkey_row.addWidget(reset_btn)
        hotkey_form.addRow("Shortcut:", hotkey_row)
        self._hotkey_note = QLabel("Use at least one modifier (Ctrl, Alt, Shift or Win).")
        self._hotkey_note.setObjectName("settingsNote")

        self._hotkey_note.setWordWrap(True)
        hotkey_form.addRow(self._hotkey_note)
        layout.addWidget(hotkey_group)

        # Updates
        updates_group = QGroupBox("Updates")
        updates_group.setObjectName("settingsGroup")
        updates_form = QFormLayout(updates_group)
        updates_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        updates_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._updates_toggle = self._toggle_row(updates_form, "Check GitHub Releases for new versions daily", True)
        updates_row = QHBoxLayout()
        self._update_status = QLabel("")
        self._update_status.setObjectName("settingsNote")

        self._update_status.setWordWrap(True)
        updates_row.addWidget(self._update_status, stretch=1)
        check_btn = QPushButton("Check now")
        check_btn.setObjectName("settingsActionBtn")
        check_btn.setMinimumHeight(32)
        check_btn.clicked.connect(self.check_updates_requested.emit)
        updates_row.addWidget(check_btn)
        updates_form.addRow(updates_row)
        layout.addWidget(updates_group)

        # Undo
        undo_group = QGroupBox("Undo history")
        undo_group.setObjectName("settingsGroup")
        undo_form = QFormLayout(undo_group)
        undo_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        undo_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._purge_days = QSpinBox()
        self._purge_days.setRange(1, 90)
        self._purge_days.setSuffix(" days")
        self._purge_days.setMinimumHeight(32)
        undo_form.addRow("Keep operations for:", self._purge_days)
        self._backups_toggle = self._toggle_row(undo_form, "Back up file contents before the AI overwrites them", True)
        data_row = QHBoxLayout()
        self._backup_size = QLabel("")
        self._backup_size.setObjectName("settingsNote")

        self._backup_size.setWordWrap(True)
        data_row.addWidget(self._backup_size, stretch=1)
        open_btn = QPushButton("Open data folder")
        open_btn.setMinimumHeight(32)
        open_btn.clicked.connect(self._open_data_folder)
        data_row.addWidget(open_btn)
        undo_form.addRow(data_row)
        layout.addWidget(undo_group)

        layout.addStretch()

    def _load_current(self) -> None:
        s = self._config.settings
        self._refresh_toggle.setChecked(s.refresh.auto_refresh_enabled, animate=False)
        self._refresh_interval.setValue(max(1, s.refresh.refresh_interval_seconds // 60))
        self._startup_toggle.setChecked(s.startup.start_with_windows, animate=False)
        self._start_min_toggle.setChecked(s.startup.start_minimized, animate=False)
        self._tray_toggle.setChecked(s.startup.minimize_to_tray, animate=False)
        self._notify_toggle.setChecked(s.startup.show_notifications, animate=False)
        self._hotkey_toggle.setChecked(s.startup.global_hotkey_enabled, animate=False)
        self._hotkey_edit.setKeySequence(QKeySequence(s.startup.global_hotkey or AppConstants.DEFAULT_GLOBAL_HOTKEY))
        self._updates_toggle.setChecked(s.updates.check_for_updates, animate=False)
        last = s.updates.last_check_iso
        self._update_status.setText(f"Last checked: {last[:16].replace('T', ' ')}" if last else "Never checked yet.")
        self._purge_days.setValue(s.undo.purge_days)
        self._backups_toggle.setChecked(s.undo.keep_content_backups, animate=False)
        try:
            size = BackupStore().total_size()
            self._backup_size.setText(
                f"Data folder: {AppConstants.APPDATA_DIR}  ·  backups {PathUtils.format_size(size)}"
            )
        except Exception:
            self._backup_size.setText(f"Data folder: {AppConstants.APPDATA_DIR}")

    def _connect_signals(self) -> None:
        for t in (
            self._refresh_toggle,
            self._startup_toggle,
            self._start_min_toggle,
            self._tray_toggle,
            self._notify_toggle,
            self._hotkey_toggle,
            self._updates_toggle,
            self._backups_toggle,
        ):
            t.toggled.connect(lambda _c: self.settings_changed.emit())
        self._refresh_interval.valueChanged.connect(lambda _v: self.settings_changed.emit())
        self._purge_days.valueChanged.connect(lambda _v: self.settings_changed.emit())
        self._hotkey_edit.keySequenceChanged.connect(self._on_hotkey_edited)

    def _on_hotkey_edited(self, seq: QKeySequence) -> None:
        text = seq.toString(QKeySequence.SequenceFormat.PortableText)
        if text and parse_hotkey(text) is None:
            self._hotkey_note.setText("This shortcut is invalid — include Ctrl, Alt, Shift or Win.")
            self._hotkey_note.setProperty("state", "warn")
        else:
            self._hotkey_note.setText("Use at least one modifier (Ctrl, Alt, Shift or Win).")
        self.settings_changed.emit()

    def set_update_status(self, text: str) -> None:
        self._update_status.setText(text)

    @staticmethod
    def _open_data_folder() -> None:
        try:
            os.makedirs(AppConstants.APPDATA_DIR, exist_ok=True)
            subprocess.Popen(["explorer", str(AppConstants.APPDATA_DIR)])
        except Exception as e:
            logger.error(f"Could not open data folder: {e}")

    def save(self) -> None:
        c = self._config
        c.update("refresh", "auto_refresh_enabled", self._refresh_toggle.is_checked)
        c.update("refresh", "refresh_interval_seconds", self._refresh_interval.value() * 60)
        c.update("startup", "start_with_windows", self._startup_toggle.is_checked)
        c.update("startup", "start_minimized", self._start_min_toggle.is_checked)
        c.update("startup", "minimize_to_tray", self._tray_toggle.is_checked)
        c.update("startup", "show_notifications", self._notify_toggle.is_checked)
        c.update("startup", "global_hotkey_enabled", self._hotkey_toggle.is_checked)
        seq = self._hotkey_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        if seq and parse_hotkey(seq) is not None:
            c.update("startup", "global_hotkey", seq)
        c.update("updates", "check_for_updates", self._updates_toggle.is_checked)
        c.update("undo", "purge_days", self._purge_days.value())
        c.update("undo", "keep_content_backups", self._backups_toggle.is_checked)
