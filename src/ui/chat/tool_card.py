"""
OP(AI)UM — Tool Activity Card

Inline chat card showing a tool call: spinner while running, then the
outcome (success / failed / cancelled), the tool's message, a compact
summary of its data and a one-click Undo when the operation is reversible.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from src.ui.widgets.loading_spinner import LoadingSpinner
from src.utils.icon_provider import SvgIcons

TOOL_LABELS: dict[str, str] = {
    "count_files": "Counting files",
    "get_file_sizes": "Measuring sizes",
    "summarize_file_types": "Summarizing file types",
    "find_large_files": "Finding large files",
    "find_duplicates": "Finding duplicates",
    "analyze_file_ages": "Analyzing file ages",
    "read_metadata": "Reading metadata",
    "disk_usage": "Checking disk usage",
    "startup_programs": "Listing startup programs",
    "recycle_bin": "Recycle Bin",
    "rename_files": "Renaming files",
    "regex_rename": "Regex rename",
    "change_extensions": "Changing extensions",
    "move_files": "Moving files",
    "copy_files": "Copying files",
    "delete_files": "Deleting files",
    "organize_by_type": "Organizing by type",
    "organize_by_date": "Organizing by date",
    "flatten_folder": "Flattening folder",
    "clean_empty_folders": "Cleaning empty folders",
    "folder_operations": "Folder operation",
    "file_content": "File content",
}

TOOL_ICONS: dict[str, str] = {
    "count_files": "chart",
    "get_file_sizes": "chart",
    "summarize_file_types": "chart",
    "find_large_files": "search",
    "find_duplicates": "duplicate",
    "analyze_file_ages": "clock",
    "read_metadata": "info",
    "disk_usage": "disk",
    "startup_programs": "rocket",
    "recycle_bin": "recycle",
    "rename_files": "rename",
    "regex_rename": "rename",
    "change_extensions": "rename",
    "move_files": "folder",
    "copy_files": "copy",
    "delete_files": "trash",
    "organize_by_type": "folder-open",
    "organize_by_date": "clock",
    "flatten_folder": "folder-open",
    "clean_empty_folders": "broom",
    "folder_operations": "folder",
    "file_content": "file",
}


def pretty_tool_name(name: str) -> str:
    return TOOL_LABELS.get(name, name.replace("_", " ").capitalize())


class ToolCard(QFrame):
    """
    Signals:
        undo_requested(int): operation id to undo.
    """

    undo_requested = Signal(int)

    def __init__(self, tool_name: str, arguments: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tool_name = tool_name
        self._arguments = arguments
        self._operation_id: int | None = None
        self._finished = False

        self.setObjectName("toolCard")
        self.setProperty("status", "running")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMaximumWidth(760)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(8)

        self._icon = QLabel()
        self._icon.setFixedSize(18, 18)
        self._icon.setPixmap(SvgIcons.themed(TOOL_ICONS.get(self._tool_name, "sparkle"), "accent", 18).pixmap(18, 18))
        header.addWidget(self._icon)

        self._name = QLabel(pretty_tool_name(self._tool_name))
        self._name.setObjectName("toolCardName")
        header.addWidget(self._name)

        self._target = QLabel(self._describe_target())
        self._target.setObjectName("toolCardStatus")
        header.addWidget(self._target, stretch=1)

        self._spinner = LoadingSpinner(self, size=16, line_width=2)
        self._spinner.start()
        header.addWidget(self._spinner)

        self._status = QLabel("Running")
        self._status.setObjectName("toolCardStatus")
        header.addWidget(self._status)

        layout.addLayout(header)

        self._message = QLabel("")
        self._message.setObjectName("toolCardMessage")
        self._message.setWordWrap(True)
        self._message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._message.hide()
        layout.addWidget(self._message)

        self._actions = QHBoxLayout()
        self._actions.addStretch()
        self._undo_btn = QPushButton("Undo")
        self._undo_btn.setObjectName("toolCardUndoBtn")
        self._undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._undo_btn.setFixedHeight(26)
        self._undo_btn.clicked.connect(self._on_undo)
        self._undo_btn.hide()
        self._actions.addWidget(self._undo_btn)
        layout.addLayout(self._actions)

    def _describe_target(self) -> str:
        for key in ("directory", "path", "source", "folder"):
            value = self._arguments.get(key)
            if isinstance(value, str) and value:
                return value if len(value) <= 60 else "…" + value[-57:]
        return ""

    # === Updates ===

    @property
    def tool_name(self) -> str:
        return self._tool_name

    @property
    def is_finished(self) -> bool:
        return self._finished

    @property
    def operation_id(self) -> int | None:
        return self._operation_id

    def set_result(self, result: dict[str, Any]) -> None:
        """Apply the tool result dict (from ToolResult.to_dict())."""
        self._finished = True
        self._spinner.stop()
        success = bool(result.get("success"))
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        cancelled = bool(data.get("cancelled")) if data else False
        message = str(result.get("message") or result.get("error") or "")

        if cancelled:
            status, label, color = "cancelled", "Cancelled", "peach"
        elif success:
            status, label, color = "ok", "Done", "green"
        else:
            status, label, color = "err", "Failed", "red"

        self.setProperty("status", status)
        self._status.setText(label)
        self._icon.setPixmap(SvgIcons.themed(TOOL_ICONS.get(self._tool_name, "sparkle"), color, 18).pixmap(18, 18))
        if message:
            first_line = message.strip().split("\n", 1)[0]
            self._message.setText(first_line if len(first_line) <= 400 else first_line[:400] + "…")
            self._message.show()

        summary = self._summarize(data)
        if summary:
            self._target.setText(summary)

        op_id = result.get("operation_id")
        if success and isinstance(op_id, int) and result.get("undoable"):
            self._operation_id = op_id
            self._undo_btn.show()

        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    @staticmethod
    def _summarize(data: dict[str, Any]) -> str:
        if not data:
            return ""
        parts: list[str] = []
        for key, label in (
            ("count", "items"),
            ("total_files", "files"),
            ("succeeded", "succeeded"),
            ("failed", "failed"),
            ("removed", "removed"),
            ("duplicate_groups", "duplicate groups"),
        ):
            value = data.get(key)
            if isinstance(value, int) and (value or key == "count"):
                parts.append(f"{value} {label}")
        for key in ("display_size", "total_display", "wasted_display"):
            value = data.get(key)
            if isinstance(value, str) and value:
                parts.append(value)
        return " · ".join(parts[:3])

    def mark_undone(self) -> None:
        self._undo_btn.setEnabled(False)
        self._undo_btn.setText("Undone")

    def _on_undo(self) -> None:
        if self._operation_id is not None:
            self.undo_requested.emit(self._operation_id)
