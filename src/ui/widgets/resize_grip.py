"""
OP(AI)UM — Resize Grip

Invisible edge widgets that enable resizing frameless windows.
Placed at window edges/corners, they change cursor and handle resize drag.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QWidget


class ResizeGrip(QWidget):
    """
    Invisible grip at a window edge or corner.
    On mouse drag, resizes the top-level window.
    """

    def __init__(
        self,
        edge: str,  # "left", "right", "top", "bottom", "tl", "tr", "bl", "br"
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._edge = edge
        self._pressed = False
        self._start_pos: QPoint | None = None
        self._start_geo: QRect | None = None
        self._min_width = 900
        self._min_height = 600
        self.setCursor(self._cursor_for_edge(edge))

    @staticmethod
    def _cursor_for_edge(edge: str) -> Qt.CursorShape:
        cursors = {
            "left": Qt.CursorShape.SizeHorCursor,
            "right": Qt.CursorShape.SizeHorCursor,
            "top": Qt.CursorShape.SizeVerCursor,
            "bottom": Qt.CursorShape.SizeVerCursor,
            "tl": Qt.CursorShape.SizeFDiagCursor,
            "tr": Qt.CursorShape.SizeBDiagCursor,
            "bl": Qt.CursorShape.SizeBDiagCursor,
            "br": Qt.CursorShape.SizeFDiagCursor,
        }
        return cursors.get(edge, Qt.CursorShape.ArrowCursor)

    def set_minimum_size(self, w: int, h: int) -> None:
        self._min_width = w
        self._min_height = h

    def _window(self) -> QWidget | None:
        w = self.window()
        return w if w and w != self else None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self._start_pos = event.globalPosition().toPoint()
            win = self._window()
            if win:
                self._start_geo = QRect(win.geometry())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._pressed and self._start_pos and self._start_geo:
            win = self._window()
            if not win:
                return
            delta = event.globalPosition().toPoint() - self._start_pos
            x, y, w, h = (
                self._start_geo.x(),
                self._start_geo.y(),
                self._start_geo.width(),
                self._start_geo.height(),
            )

            if "left" in self._edge:
                x += delta.x()
                w -= delta.x()
            if "right" in self._edge:
                w += delta.x()
            if "top" in self._edge:
                y += delta.y()
                h -= delta.y()
            if "bottom" in self._edge:
                h += delta.y()

            w = max(w, self._min_width)
            h = max(h, self._min_height)
            if "left" in self._edge:
                x = self._start_geo.right() - w
            if "top" in self._edge:
                y = self._start_geo.bottom() - h

            win.setGeometry(QRect(x, y, w, h))
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = False
            self._start_pos = None
            self._start_geo = None
        super().mouseReleaseEvent(event)
