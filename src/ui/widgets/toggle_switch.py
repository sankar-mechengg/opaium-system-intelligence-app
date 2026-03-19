"""
OP(AI)UM — Animated Toggle Switch Widget

A custom toggle switch with smooth animation, used for
theme toggle (light/dark), recursive scan toggle, etc.
"""

from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QBrush, QColor, QMouseEvent, QPainter
from PySide6.QtWidgets import QWidget


class ToggleSwitch(QWidget):
    """
    Animated toggle switch with customizable colors.

    Signals:
        toggled(bool): Emitted when state changes.
    """

    toggled = Signal(bool)

    def __init__(
        self,
        parent: QWidget | None = None,
        checked: bool = False,
        bar_color_on: str = "#4FC3F7",
        bar_color_off: str = "#B0BEC5",
        handle_color: str = "#FFFFFF",
        width: int = 52,
        height: int = 28,
    ) -> None:
        super().__init__(parent)
        self._checked = checked
        self._bar_color_on = QColor(bar_color_on)
        self._bar_color_off = QColor(bar_color_off)
        self._handle_color = QColor(handle_color)
        self._width = width
        self._height = height
        self._handle_radius = (height - 6) // 2
        self._margin = 3

        self._handle_position = float(self._width - self._margin * 2 - self._handle_radius * 2) if checked else 0.0

        self.setFixedSize(width, height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._animation = QPropertyAnimation(self, b"handle_pos")
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

    def _get_handle_pos(self) -> float:
        return self._handle_position

    def _set_handle_pos(self, pos: float) -> None:
        self._handle_position = pos
        self.update()

    handle_pos = Property(float, _get_handle_pos, _set_handle_pos)

    @property
    def is_checked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, animate: bool = True) -> None:
        """Set the toggle state."""
        if self._checked == checked:
            return

        self._checked = checked
        end_pos = float(self._width - self._margin * 2 - self._handle_radius * 2) if checked else 0.0

        if animate:
            self._animation.stop()
            self._animation.setStartValue(self._handle_position)
            self._animation.setEndValue(end_pos)
            self._animation.start()
        else:
            self._handle_position = end_pos
            self.update()

        self.toggled.emit(checked)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw bar
        bar_color = self._bar_color_on if self._checked else self._bar_color_off
        bar_rect = QRectF(0, 0, self._width, self._height)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bar_color))
        painter.drawRoundedRect(bar_rect, self._height / 2, self._height / 2)

        # Draw handle
        handle_x = self._margin + self._handle_position
        handle_y = self._margin
        handle_diameter = self._handle_radius * 2

        # Shadow
        shadow_color = QColor(0, 0, 0, 40)
        painter.setBrush(QBrush(shadow_color))
        painter.drawEllipse(QRectF(handle_x + 1, handle_y + 1, handle_diameter, handle_diameter))

        # Handle
        painter.setBrush(QBrush(self._handle_color))
        painter.drawEllipse(QRectF(handle_x, handle_y, handle_diameter, handle_diameter))

        painter.end()

    def sizeHint(self) -> QSize:
        return QSize(self._width, self._height)
