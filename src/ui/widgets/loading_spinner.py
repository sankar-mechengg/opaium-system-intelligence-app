"""
OP(AI)UM — Loading Spinner Widget

Animated circular loading indicator used during
scanning, API calls, and other async operations.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QConicalGradient, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget


class LoadingSpinner(QWidget):
    """
    Circular loading spinner with smooth rotation animation.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        size: int = 32,
        color: str = "#4FC3F7",
        line_width: int = 3,
    ) -> None:
        super().__init__(parent)
        self._size = size
        self._color = QColor(color)
        self._line_width = line_width
        self._angle = 0
        self._is_spinning = False

        self.setFixedSize(size, size)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)

    def start(self) -> None:
        """Start the spinning animation."""
        self._is_spinning = True
        self._timer.start(16)  # ~60 FPS
        self.show()

    def stop(self) -> None:
        """Stop the spinning animation."""
        self._is_spinning = False
        self._timer.stop()
        self.hide()

    @property
    def is_spinning(self) -> bool:
        return self._is_spinning

    def _rotate(self) -> None:
        self._angle = (self._angle + 5) % 360
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        if not self._is_spinning:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Calculate dimensions
        side = min(self.width(), self.height())
        margin = self._line_width + 2
        rect = QRectF(margin, margin, side - 2 * margin, side - 2 * margin)

        # Create gradient for the arc
        gradient = QConicalGradient(rect.center(), -self._angle)
        gradient.setColorAt(0, self._color)
        gradient.setColorAt(0.6, self._color)
        transparent = QColor(self._color)
        transparent.setAlpha(0)
        gradient.setColorAt(1, transparent)

        pen = QPen()
        pen.setWidth(self._line_width)
        pen.setBrush(gradient)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)

        painter.setPen(pen)
        painter.drawArc(rect, int(self._angle * 16), int(270 * 16))

        painter.end()

    def sizeHint(self) -> QSize:
        return QSize(self._size, self._size)

    def set_color(self, color: str) -> None:
        """Change the spinner color."""
        self._color = QColor(color)
