"""
OP(AI)UM — History Row Widget

A single row in the operation history list showing
operation type, description, timestamp, and undo button.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.models import OperationRecord
from src.utils.time_utils import TimeUtils


class HistoryRow(QFrame):
    """
    Single operation row in the history panel.

    Signals:
        undo_clicked(int): Request undo for operation ID.
    """

    undo_clicked = Signal(int)
    delete_clicked = Signal(int)

    # Operation type icons
    TYPE_ICONS = {
        "rename": "✏️",
        "regex_rename": "✏️",
        "extension_change": "✏️",
        "move": "📦",
        "copy": "📋",
        "delete": "🗑️",
        "organize": "📁",
        "organize_date": "📅",
        "flatten": "📂",
        "clean_empty": "🧹",
        "create_file": "📄",
        "write_file": "✍️",
        "append_file": "➕",
    }

    def __init__(
        self,
        operation: OperationRecord,
        operation_id: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._operation = operation
        self._operation_id = operation_id

        self.setObjectName("historyRow")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFixedHeight(64)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        # Icon
        icon_text = self.TYPE_ICONS.get(self._operation.operation_type, "⚙️")
        icon_label = QLabel(icon_text)
        icon_font = QFont()
        icon_font.setPointSize(16)
        icon_label.setFont(icon_font)
        icon_label.setFixedWidth(28)
        layout.addWidget(icon_label)

        # Details
        details_layout = QVBoxLayout()
        details_layout.setSpacing(2)

        desc_label = QLabel(self._operation.description)
        desc_label.setObjectName("historyDesc")
        desc_font = QFont()
        desc_font.setPointSize(9)
        desc_font.setBold(True)
        desc_label.setFont(desc_font)
        desc_label.setWordWrap(False)
        details_layout.addWidget(desc_label)

        # Timestamp + file count
        meta_parts = [
            TimeUtils.format_relative(self._operation.timestamp),
        ]
        if self._operation.source_paths:
            meta_parts.append(f"{len(self._operation.source_paths)} items")

        meta_label = QLabel(" • ".join(meta_parts))
        meta_label.setObjectName("historyMeta")
        meta_font = QFont()
        meta_font.setPointSize(8)
        meta_label.setFont(meta_font)
        details_layout.addWidget(meta_label)

        layout.addLayout(details_layout, stretch=1)

        # Status / Undo
        if self._operation.is_undone:
            undone_label = QLabel("Undone")
            undone_label.setObjectName("historyUndone")
            undone_font = QFont()
            undone_font.setPointSize(8)
            undone_font.setItalic(True)
            undone_label.setFont(undone_font)
            layout.addWidget(undone_label)
        elif self._operation.is_undoable:
            undo_btn = QPushButton("↩ Undo")
            undo_btn.setObjectName("historyUndoBtn")
            undo_btn.setFixedHeight(28)
            undo_btn.setMinimumWidth(70)
            undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            undo_btn.clicked.connect(lambda: self.undo_clicked.emit(self._operation_id))
            layout.addWidget(undo_btn)
        else:
            no_undo = QLabel("—")
            no_undo.setObjectName("historyNoUndo")
            no_undo.setFixedWidth(30)
            no_undo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_undo)

        delete_btn = QPushButton("✕")
        delete_btn.setObjectName("historyDeleteBtn")
        delete_btn.setFixedSize(28, 28)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setToolTip("Delete this entry")
        delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self._operation_id))
        layout.addWidget(delete_btn)
