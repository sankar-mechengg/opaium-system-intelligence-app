"""
OP(AI)UM — Tool Result Display Widget

Displays the result of an AI tool operation in the chat view.
Shows success/failure status, details, and undo button if applicable.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from src.ai.tools.base_tool import ToolResult


class ToolResultWidget(QFrame):
    """
    Displays the result of a tool execution in the chat.

    Shows status icon, message, and an undo button if the
    operation is undoable.

    Signals:
        undo_requested(int): Request undo for an operation (operation_id).
    """

    undo_requested = Signal(int)

    def __init__(
        self,
        tool_name: str,
        result: ToolResult,
        operation_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tool_name = tool_name
        self._result = result
        self._operation_id = operation_id

        self.setObjectName("toolResult")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header row: icon + tool name + status
        header_layout = QHBoxLayout()

        status_icon = "✅" if self._result.success else "❌"
        icon_label = QLabel(status_icon)
        icon_font = QFont()
        icon_font.setPointSize(12)
        icon_label.setFont(icon_font)
        header_layout.addWidget(icon_label)

        name_label = QLabel(self._tool_name.replace("_", " ").title())
        name_label.setObjectName("toolResultName")
        name_font = QFont()
        name_font.setPointSize(10)
        name_font.setBold(True)
        name_label.setFont(name_font)
        header_layout.addWidget(name_label)

        header_layout.addStretch()

        status_text = "Success" if self._result.success else "Failed"
        status_label = QLabel(status_text)
        status_label.setObjectName(f"toolResultStatus_{'ok' if self._result.success else 'err'}")
        status_font = QFont()
        status_font.setPointSize(8)
        status_font.setBold(True)
        status_label.setFont(status_font)
        header_layout.addWidget(status_label)

        layout.addLayout(header_layout)

        # Message
        msg_label = QLabel(self._result.message)
        msg_label.setObjectName("toolResultMessage")
        msg_label.setWordWrap(True)
        msg_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        msg_font = QFont()
        msg_font.setPointSize(9)
        msg_label.setFont(msg_font)
        layout.addWidget(msg_label)

        # Data summary (if available)
        if self._result.data and isinstance(self._result.data, dict):
            data = self._result.data
            summary_parts = []
            if "succeeded" in data:
                summary_parts.append(f"{data['succeeded']} succeeded")
            if "failed" in data and data["failed"]:
                summary_parts.append(f"{data['failed']} failed")
            if "count" in data:
                summary_parts.append(f"{data['count']} items")
            if "wasted_display" in data:
                summary_parts.append(f"{data['wasted_display']} wasted")

            if summary_parts:
                summary = QLabel(" • ".join(summary_parts))
                summary.setObjectName("toolResultSummary")
                summary_font = QFont()
                summary_font.setPointSize(8)
                summary.setFont(summary_font)
                layout.addWidget(summary)

        # Undo button (if operation is undoable)
        if (
            self._result.operation
            and self._result.operation.is_undoable
            and self._result.success
            and self._operation_id is not None
        ):
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()

            undo_btn = QPushButton("↩ Undo")
            undo_btn.setObjectName("toolResultUndoBtn")
            undo_btn.setFixedHeight(30)
            undo_btn.setMinimumWidth(80)
            undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            undo_btn.clicked.connect(
                lambda: self.undo_requested.emit(self._operation_id)
            )
            btn_layout.addWidget(undo_btn)

            layout.addLayout(btn_layout)
