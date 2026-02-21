"""
OP(AI)UM — Status Badge Widget

Small badge indicators for file counts, folder status,
and notification counts.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QBrush


class Badge(QLabel):
    """
    Small rounded badge for displaying counts or status.

    Usage:
        badge = Badge("12", color="#4FC3F7")
        badge = Badge("!", color="#F44336")  # Error
    """

    def __init__(
        self,
        text: str = "",
        color: str = "#4FC3F7",
        text_color: str = "#FFFFFF",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._bg_color = QColor(color)
        self._text_color = QColor(text_color)

        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        self.setFont(font)

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumWidth(22)
        self.setFixedHeight(20)

        self._update_style()

    def _update_style(self) -> None:
        self.setStyleSheet(
            f"QLabel {{"
            f"  background-color: {self._bg_color.name()};"
            f"  color: {self._text_color.name()};"
            f"  border-radius: 10px;"
            f"  padding: 2px 6px;"
            f"  font-size: 9px;"
            f"  font-weight: bold;"
            f"}}"
        )

    def set_value(self, text: str) -> None:
        """Update badge text."""
        self.setText(text)
        # Auto-hide if empty or zero
        self.setVisible(bool(text) and text != "0")

    def set_color(self, color: str) -> None:
        """Change badge background color."""
        self._bg_color = QColor(color)
        self._update_style()


class StatusDot(QWidget):
    """
    Small colored dot indicator.

    Usage:
        dot = StatusDot(color="green")  # Online/Active
        dot = StatusDot(color="red")    # Error
        dot = StatusDot(color="orange") # Warning
    """

    COLORS = {
        "green": "#4CAF50",
        "red": "#F44336",
        "orange": "#FF9800",
        "blue": "#2196F3",
        "grey": "#9E9E9E",
    }

    def __init__(
        self,
        color: str = "green",
        size: int = 10,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._color = QColor(self.COLORS.get(color, color))
        self._size = size
        self.setFixedSize(size, size)

    def set_status(self, color: str) -> None:
        """Change the dot color."""
        self._color = QColor(self.COLORS.get(color, color))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._color))
        painter.drawEllipse(1, 1, self._size - 2, self._size - 2)
        painter.end()

    def sizeHint(self) -> QSize:
        return QSize(self._size, self._size)
