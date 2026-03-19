"""
OP(AI)UM — Typing Indicator

Animated "AI is thinking..." widget shown while waiting
for GPT response.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


class TypingDot(QWidget):
    """A single animated dot."""

    def __init__(self, color: str = "#4FC3F7", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self._opacity = 0.3
        self.setFixedSize(8, 8)

    def set_opacity(self, opacity: float) -> None:
        self._opacity = opacity
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self._color)
        color.setAlphaF(self._opacity)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(0, 0, 8, 8)
        painter.end()


class TypingIndicator(QWidget):
    """
    Animated typing indicator with bouncing dots.
    Shows "OP(AI)UM is thinking..." with three dots.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._active = False
        self._frame = 0

        self._build_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(6)

        label = QLabel("OP(AI)UM is thinking")
        label.setObjectName("typingLabel")
        label_font = QFont()
        label_font.setPointSize(9)
        label_font.setItalic(True)
        label.setFont(label_font)
        layout.addWidget(label)

        self._dots: list[TypingDot] = []
        for _ in range(3):
            dot = TypingDot()
            self._dots.append(dot)
            layout.addWidget(dot)

        layout.addStretch()
        self.hide()

    def start(self) -> None:
        """Show and start the animation."""
        self._active = True
        self._frame = 0
        self._timer.start(200)
        self.show()

    def stop(self) -> None:
        """Stop and hide the animation."""
        self._active = False
        self._timer.stop()
        self.hide()

    def _animate(self) -> None:
        """Cycle through dot opacities."""
        for i, dot in enumerate(self._dots):
            phase = (self._frame + i) % 4
            if phase == 0:
                dot.set_opacity(1.0)
            elif phase == 1:
                dot.set_opacity(0.7)
            elif phase == 2:
                dot.set_opacity(0.4)
            else:
                dot.set_opacity(0.2)
        self._frame += 1
