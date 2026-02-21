"""
OP(AI)UM — Operation Approval Dialog

Displays a preview of what an AI operation will do and
requires explicit user approval before execution.
Used for all destructive operations (rename, delete, move, etc.).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFrame, QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from src.ai.tools.base_tool import ToolResult


class ApprovalDialog(QDialog):
    """
    Modal dialog for approving destructive AI operations.

    Shows:
    - Operation description
    - Preview of changes
    - Approve / Reject buttons

    Returns QDialog.DialogCode.Accepted or .Rejected.
    """

    def __init__(
        self,
        tool_name: str,
        result: ToolResult,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tool_name = tool_name
        self._result = result

        self.setWindowTitle(f"Confirm Operation — {tool_name}")
        self.setMinimumSize(500, 400)
        self.setMaximumSize(700, 600)
        self.setModal(True)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Header
        header = QLabel(f"⚠️  {self._tool_name}")
        header.setObjectName("approvalHeader")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        # Description
        desc = QLabel(self._result.message)
        desc.setObjectName("approvalDescription")
        desc.setWordWrap(True)
        desc_font = QFont()
        desc_font.setPointSize(10)
        desc.setFont(desc_font)
        layout.addWidget(desc)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # Preview details
        preview_label = QLabel("Preview of changes:")
        preview_label.setObjectName("approvalPreviewLabel")
        preview_font = QFont()
        preview_font.setPointSize(9)
        preview_font.setBold(True)
        preview_label.setFont(preview_font)
        layout.addWidget(preview_label)

        preview_text = QTextEdit()
        preview_text.setObjectName("approvalPreview")
        preview_text.setReadOnly(True)
        preview_text.setFont(QFont("Consolas", 9))
        preview_text.setMinimumHeight(150)

        if self._result.preview:
            preview_text.setPlainText("\n".join(self._result.preview))
        else:
            preview_text.setPlainText("No preview available.")

        layout.addWidget(preview_text, stretch=1)

        # Warning
        warning = QLabel("This operation cannot be fully undone. Please review carefully.")
        warning.setObjectName("approvalWarning")
        warning.setWordWrap(True)
        warning_font = QFont()
        warning_font.setPointSize(9)
        warning_font.setItalic(True)
        warning.setFont(warning_font)
        layout.addWidget(warning)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        reject_btn = QPushButton("Cancel")
        reject_btn.setObjectName("approvalRejectBtn")
        reject_btn.setMinimumHeight(38)
        reject_btn.setMinimumWidth(100)
        reject_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reject_btn.clicked.connect(self.reject)
        btn_layout.addWidget(reject_btn)

        approve_btn = QPushButton("Approve && Execute")
        approve_btn.setObjectName("approvalApproveBtn")
        approve_btn.setMinimumHeight(38)
        approve_btn.setMinimumWidth(160)
        approve_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        approve_font = QFont()
        approve_font.setBold(True)
        approve_btn.setFont(approve_font)
        approve_btn.clicked.connect(self.accept)
        approve_btn.setDefault(True)
        btn_layout.addWidget(approve_btn)

        layout.addLayout(btn_layout)
