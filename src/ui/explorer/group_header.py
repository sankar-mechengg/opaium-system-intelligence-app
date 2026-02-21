"""
OP(AI)UM — Group Header Widget

Header labels for time-grouped sections (Last 2 Days, Last Week, etc.)
with item counts and expand/collapse functionality.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from src.utils.time_utils import TimeGroup


class GroupHeader(QWidget):
    """
    Section header for time-based groups.

    Signals:
        clicked(): Emitted when the header is clicked (for collapse toggle).
    """

    clicked = Signal()

    # Colors for each time group
    GROUP_COLORS = {
        TimeGroup.LAST_2_DAYS: "#4FC3F7",   # Light blue
        TimeGroup.LAST_WEEK: "#81C784",      # Light green
        TimeGroup.LAST_MONTH: "#FFB74D",     # Orange
        TimeGroup.OLDER: "#B0BEC5",          # Grey
    }

    def __init__(
        self,
        time_group: TimeGroup,
        count: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._group = time_group
        self._count = count
        self._expanded = True

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(36)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)

        color = self.GROUP_COLORS.get(self._group, "#B0BEC5")

        # Colored accent bar
        accent = QLabel()
        accent.setFixedSize(4, 20)
        accent.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
        layout.addWidget(accent)

        # Title
        self._title = QLabel(self._group.value)
        self._title.setObjectName("groupHeaderTitle")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        self._title.setFont(title_font)
        layout.addWidget(self._title)

        layout.addStretch()

        # Count
        self._count_label = QLabel(f"{self._count} items")
        self._count_label.setObjectName("groupHeaderCount")
        count_font = QFont()
        count_font.setPointSize(9)
        self._count_label.setFont(count_font)
        layout.addWidget(self._count_label)

        # Arrow
        self._arrow = QLabel("▼")
        self._arrow.setObjectName("groupHeaderArrow")
        arrow_font = QFont()
        arrow_font.setPointSize(8)
        self._arrow.setFont(arrow_font)
        self._arrow.setFixedWidth(16)
        layout.addWidget(self._arrow)

    def set_count(self, count: int) -> None:
        """Update the item count."""
        self._count = count
        self._count_label.setText(f"{count} item{'s' if count != 1 else ''}")

    def set_expanded(self, expanded: bool) -> None:
        """Update the expanded state indicator."""
        self._expanded = expanded
        self._arrow.setText("▼" if expanded else "▶")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._expanded = not self._expanded
            self._arrow.setText("▼" if self._expanded else "▶")
            self.clicked.emit()
