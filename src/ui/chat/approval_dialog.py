"""
OP(AI)UM — Operation Approval Dialog

Shown by the chat panel when the AI wants to run a destructive tool. Displays
the tool's real preview (exact files, sizes, before → after) and only lets the
operation proceed on an explicit Approve. Optionally trusts the tool for the
rest of the session.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.ai.safety import ApprovalRequest
from src.ui.chat.tool_card import pretty_tool_name
from src.utils.icon_provider import SvgIcons


class ApprovalDialog(QDialog):
    """
    Modal dialog for approving destructive AI operations.
    Result: Accepted = approved, Rejected = cancelled. `remember` tells whether
    the user asked to trust this tool for the session.
    """

    def __init__(self, request: ApprovalRequest, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._request = request
        self.remember = False

        self.setWindowTitle(f"Confirm — {pretty_tool_name(request.tool_name)}")
        self.setMinimumSize(560, 420)
        self.resize(640, 520)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        header_row.setSpacing(10)
        icon = QLabel()
        icon.setPixmap(SvgIcons.themed("warning", "peach", 26).pixmap(26, 26))
        header_row.addWidget(icon)
        header = QLabel(f"{pretty_tool_name(self._request.tool_name)} needs your approval")
        header.setObjectName("approvalHeader")
        header_font = QFont()
        header_font.setPointSize(13)
        header_font.setBold(True)
        header.setFont(header_font)
        header_row.addWidget(header, stretch=1)
        layout.addLayout(header_row)

        desc = QLabel(self._request.title or "Review the changes below before they are applied.")
        desc.setObjectName("approvalDescription")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setProperty("role", "separator")
        layout.addWidget(sep)

        count = self._request.affected_count
        suffix = f" ({count} item{'s' if count != 1 else ''})" if count else ""
        preview_label = QLabel(f"What will change{suffix}:")
        preview_label.setObjectName("approvalPreviewLabel")
        preview_font = QFont()
        preview_font.setPointSize(9)
        preview_font.setBold(True)
        preview_label.setFont(preview_font)
        layout.addWidget(preview_label)

        preview_text = QTextEdit()
        preview_text.setObjectName("approvalPreview")
        preview_text.setReadOnly(True)
        preview_text.setMinimumHeight(180)
        preview_text.setPlainText("\n".join(self._request.preview_lines) or "No preview available.")
        layout.addWidget(preview_text, stretch=1)

        if self._request.arguments:
            args_line = ", ".join(f"{k}={self._short(v)}" for k, v in self._request.arguments.items())
            args_label = QLabel(f"Arguments: {args_line}")
            args_label.setObjectName("settingsNote")
            args_label.setWordWrap(True)
            layout.addWidget(args_label)

        warning = QLabel("Deletions go to the Recycle Bin and most operations can be undone from History.")
        warning.setObjectName("approvalWarning")
        warning.setWordWrap(True)
        warning_font = QFont()
        warning_font.setPointSize(9)
        warning_font.setItalic(True)
        warning.setFont(warning_font)
        layout.addWidget(warning)

        self._remember = QCheckBox("Don't ask again for this tool during this session")
        self._remember.setObjectName("approvalRemember")
        layout.addWidget(self._remember)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        reject_btn = QPushButton("Cancel")
        reject_btn.setObjectName("approvalRejectBtn")
        reject_btn.setMinimumHeight(38)
        reject_btn.setMinimumWidth(100)
        reject_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reject_btn.clicked.connect(self.reject)
        btn_layout.addWidget(reject_btn)

        approve_btn = QPushButton("Approve && Run")
        approve_btn.setObjectName("approvalApproveBtn")
        approve_btn.setMinimumHeight(38)
        approve_btn.setMinimumWidth(150)
        approve_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        approve_font = QFont()
        approve_font.setBold(True)
        approve_btn.setFont(approve_font)
        approve_btn.clicked.connect(self._approve)
        approve_btn.setDefault(True)
        btn_layout.addWidget(approve_btn)

        layout.addLayout(btn_layout)

    @staticmethod
    def _short(value: object) -> str:
        text = str(value)
        return text if len(text) <= 48 else text[:45] + "…"

    def _approve(self) -> None:
        self.remember = self._remember.isChecked()
        self.accept()
