"""
OP(AI)UM — History Panel

Displays a list of recent AI operations with undo functionality.
Auto-refreshes and supports clearing history.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from loguru import logger

from src.undo.undo_manager import UndoManager
from src.ui.history.history_row import HistoryRow


class HistoryPanel(QWidget):
    """
    Operation history panel showing recent AI operations.

    Signals:
        undo_requested(int): Request undo for an operation.
        operation_undone(): An operation was successfully undone.
    """

    undo_requested = Signal(int)
    operation_undone = Signal()

    def __init__(
        self,
        undo_manager: UndoManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._undo_manager = undo_manager
        self._rows: list[HistoryRow] = []

        self._build_ui()
        self._connect_signals()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("Operation History")
        title.setObjectName("historyTitle")
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)

        header_layout.addStretch()

        self._count_label = QLabel("0 operations")
        self._count_label.setObjectName("historyCount")
        count_font = QFont()
        count_font.setPointSize(8)
        self._count_label.setFont(count_font)
        header_layout.addWidget(self._count_label)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("historyRefreshBtn")
        refresh_btn.setFixedHeight(28)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)

        layout.addLayout(header_layout)

        # Scroll area for rows
        scroll = QScrollArea()
        scroll.setObjectName("historyScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(8, 4, 8, 4)
        self._container_layout.setSpacing(4)
        self._container_layout.addStretch()

        scroll.setWidget(self._container)
        layout.addWidget(scroll, stretch=1)

        # Empty state
        self._empty_label = QLabel("No operations yet.\nAI operations will appear here.")
        self._empty_label.setObjectName("historyEmpty")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_font = QFont()
        empty_font.setPointSize(10)
        self._empty_label.setFont(empty_font)
        self._empty_label.setVisible(False)
        self._container_layout.insertWidget(0, self._empty_label)

    def _connect_signals(self) -> None:
        self.undo_requested.connect(self._on_undo_requested)

    def refresh(self) -> None:
        """Reload operations from the undo journal."""
        for row in self._rows:
            row.deleteLater()
        self._rows.clear()

        operations = self._undo_manager.get_recent_operations(limit=50)

        if not operations:
            self._empty_label.setVisible(True)
            self._count_label.setText("0 operations")
            return

        self._empty_label.setVisible(False)
        self._count_label.setText(f"{len(operations)} operation{'s' if len(operations) != 1 else ''}")

        for operation in operations:
            record = self._operation_to_record(operation)
            row = HistoryRow(record, operation.id or 0)
            row.undo_clicked.connect(self.undo_requested.emit)
            self._rows.append(row)
            self._container_layout.insertWidget(
                self._container_layout.count() - 1, row
            )

    @staticmethod
    def _operation_to_record(op) -> "OperationRecord":
        """Convert an undo Operation to an OperationRecord for display."""
        from src.core.models import OperationRecord
        return OperationRecord(
            id=op.id,
            timestamp=op.timestamp,
            operation_type=op.operation_type.value if hasattr(op.operation_type, 'value') else str(op.operation_type),
            description=op.description,
            source_paths=[m.source for m in op.file_mappings],
            dest_paths=[m.destination for m in op.file_mappings],
            original_names=[m.original_name for m in op.file_mappings],
            new_names=[m.new_name for m in op.file_mappings],
            is_undone=op.is_undone,
            is_undoable=op.is_undoable,
        )

    def _on_undo_requested(self, operation_id: int) -> None:
        """Handle undo request."""
        operation = self._undo_manager._journal.get_operation(operation_id)
        if operation is None:
            logger.warning(f"Operation {operation_id} not found.")
            return
        success, message = self._undo_manager.undo_operation(operation)
        if success:
            logger.info(f"Operation {operation_id} undone: {message}")
            self.operation_undone.emit()
            self.refresh()
        else:
            logger.warning(f"Failed to undo operation {operation_id}: {message}")

    def add_operation(self, operation_id: int) -> None:
        """Refresh to show a newly added operation."""
        self.refresh()
