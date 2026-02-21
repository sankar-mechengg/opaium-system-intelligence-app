"""
OP(AI)UM — Collapsible Section Widget

Expandable/collapsible container with animated height transition.
Used for "Last 2 Days", "Last Week", "Last Month" groups.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy,
)
from PySide6.QtCore import (
    Qt, Signal, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup,
)
from PySide6.QtGui import QFont, QIcon


class CollapsibleSection(QWidget):
    """
    A section with a clickable header that expands/collapses
    its content area with smooth animation.

    Signals:
        collapsed(bool): Emitted when section is collapsed/expanded.
    """

    collapsed = Signal(bool)

    def __init__(
        self,
        title: str,
        item_count: int = 0,
        expanded: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._expanded = expanded
        self._title = title
        self._item_count = item_count
        self._animation_duration = 250

        self._build_ui()
        self._content_widget.setVisible(expanded)

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === Header ===
        self._header = QFrame()
        self._header.setObjectName("collapsibleHeader")
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setFixedHeight(40)
        self._header.mousePressEvent = self._on_header_click

        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(12, 0, 12, 0)

        # Arrow indicator
        self._arrow_label = QLabel("▼" if self._expanded else "▶")
        self._arrow_label.setObjectName("collapsibleArrow")
        self._arrow_label.setFixedWidth(20)
        arrow_font = QFont()
        arrow_font.setPointSize(8)
        self._arrow_label.setFont(arrow_font)
        header_layout.addWidget(self._arrow_label)

        # Title
        self._title_label = QLabel(self._title)
        self._title_label.setObjectName("collapsibleTitle")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        self._title_label.setFont(title_font)
        header_layout.addWidget(self._title_label)

        header_layout.addStretch()

        # Count badge
        self._count_label = QLabel(str(self._item_count))
        self._count_label.setObjectName("collapsibleCount")
        self._count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._count_label.setFixedWidth(36)
        self._count_label.setFixedHeight(22)
        count_font = QFont()
        count_font.setPointSize(9)
        count_font.setBold(True)
        self._count_label.setFont(count_font)
        header_layout.addWidget(self._count_label)

        main_layout.addWidget(self._header)

        # === Content Area ===
        self._content_widget = QWidget()
        self._content_widget.setObjectName("collapsibleContent")
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(0, 4, 0, 8)
        self._content_layout.setSpacing(4)

        main_layout.addWidget(self._content_widget)

    def add_widget(self, widget: QWidget) -> None:
        """Add a widget to the content area."""
        self._content_layout.addWidget(widget)

    def clear_content(self) -> None:
        """Remove all widgets from the content area."""
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def set_count(self, count: int) -> None:
        """Update the item count badge."""
        self._item_count = count
        self._count_label.setText(str(count))

    def set_title(self, title: str) -> None:
        """Update the section title."""
        self._title = title
        self._title_label.setText(title)

    @property
    def content_layout(self) -> QVBoxLayout:
        """Get the content layout for direct manipulation."""
        return self._content_layout

    @property
    def is_expanded(self) -> bool:
        return self._expanded

    def toggle(self) -> None:
        """Toggle the expanded/collapsed state."""
        self._expanded = not self._expanded

        if self._expanded:
            self._arrow_label.setText("▼")
            self._content_widget.setVisible(True)
        else:
            self._arrow_label.setText("▶")
            self._content_widget.setVisible(False)

        self.collapsed.emit(not self._expanded)

    def expand(self) -> None:
        """Expand the section."""
        if not self._expanded:
            self.toggle()

    def collapse(self) -> None:
        """Collapse the section."""
        if self._expanded:
            self.toggle()

    def _on_header_click(self, event) -> None:
        self.toggle()
