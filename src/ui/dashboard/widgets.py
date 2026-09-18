"""
OP(AI)UM — Dashboard Widgets

Reusable, theme-aware building blocks for the dashboard: cards, ring gauges,
horizontal usage bars, stat tiles and compact list rows.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from src.ui.theme import token
from src.utils.icon_provider import SvgIcons


class DashCard(QFrame):
    """Rounded card with a title row, optional subtitle and a content layout."""

    def __init__(self, title: str, icon: str = "", subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dashCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 16)
        outer.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        if icon:
            self._icon = QLabel()
            self._icon.setFixedSize(20, 20)
            self._icon.setPixmap(SvgIcons.themed(icon, "accent", 20).pixmap(20, 20))
            header.addWidget(self._icon)
        self._title = QLabel(title)
        self._title.setObjectName("dashCardTitle")
        header.addWidget(self._title)
        header.addStretch()
        self._subtitle = QLabel(subtitle)
        self._subtitle.setObjectName("dashCardSubtitle")
        header.addWidget(self._subtitle)
        outer.addLayout(header)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(8)
        outer.addLayout(self.body)
        # Keep content top-aligned when a neighbouring card makes the grid row taller.
        outer.addStretch(1)

    def set_subtitle(self, text: str) -> None:
        self._subtitle.setText(text)

    def clear_body(self) -> None:
        while self.body.count():
            item = self.body.takeAt(0)
            w = item.widget() if item is not None else None
            if w is not None:
                w.deleteLater()
            sub = item.layout() if item is not None else None
            if sub is not None:
                while sub.count():
                    inner = sub.takeAt(0)
                    iw = inner.widget() if inner is not None else None
                    if iw is not None:
                        iw.deleteLater()


class RingGauge(QWidget):
    """Circular percentage gauge with a centered value label."""

    def __init__(self, size: int = 96, thickness: int = 9, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = 0.0
        self._label = ""
        self._sub = ""
        self._thickness = thickness
        self.setFixedSize(size, size)

    def set_value(self, percent: float, label: str = "", sub: str = "") -> None:
        self._value = max(0.0, min(100.0, percent))
        self._label = label or f"{int(round(self._value))}%"
        self._sub = sub
        self.update()

    def _color(self) -> QColor:
        if self._value >= 90:
            return QColor(token("red"))
        if self._value >= 75:
            return QColor(token("peach"))
        return QColor(token("accent"))

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = self._thickness
        rect = QRectF(t / 2 + 1, t / 2 + 1, self.width() - t - 2, self.height() - t - 2)

        track = QPen(QColor(token("bg_surface2")), t)
        track.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track)
        painter.drawArc(rect, 0, 360 * 16)

        pen = QPen(self._color(), t)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        span = int(-360 * 16 * (self._value / 100.0))
        painter.drawArc(rect, 90 * 16, span)

        painter.setPen(QColor(token("text")))
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect.adjusted(0, -6, 0, -6), Qt.AlignmentFlag.AlignCenter, self._label)
        if self._sub:
            painter.setPen(QColor(token("text_faint")))
            small = QFont()
            small.setPointSize(7)
            painter.setFont(small)
            painter.drawText(rect.adjusted(0, 16, 0, 16), Qt.AlignmentFlag.AlignCenter, self._sub)
        painter.end()


class UsageBar(QWidget):
    """Labelled horizontal bar: title left, detail right, colored fill below."""

    clicked = Signal()

    def __init__(self, title: str, detail: str = "", percent: float = 0.0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._percent = max(0.0, min(100.0, percent))
        self.setMinimumHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)
        row = QHBoxLayout()
        self._title = QLabel(title)
        self._title.setObjectName("dashListItemName")
        self._title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._title.setMinimumWidth(80)
        row.addWidget(self._title, stretch=1)
        self._detail = QLabel(detail)
        self._detail.setObjectName("dashListItemMeta")
        self._detail.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._detail.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._detail.setMinimumWidth(80)
        row.addWidget(self._detail, stretch=2)
        layout.addLayout(row)
        self._bar = _Bar(self._percent)
        layout.addWidget(self._bar)

    def set_values(self, detail: str, percent: float) -> None:
        self._detail.setText(detail)
        self._bar.set_percent(percent)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class _Bar(QWidget):
    def __init__(self, percent: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._percent = percent
        self.setFixedHeight(8)

    def set_percent(self, percent: float) -> None:
        self._percent = max(0.0, min(100.0, percent))
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(token("bg_surface2")))
        painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 4, 4)
        if self._percent >= 90:
            color = QColor(token("red"))
        elif self._percent >= 75:
            color = QColor(token("peach"))
        else:
            color = QColor(token("accent"))
        painter.setBrush(color)
        w = max(8.0, self.width() * self._percent / 100.0) if self._percent > 0 else 0
        painter.drawRoundedRect(QRectF(0, 0, w, self.height()), 4, 4)
        painter.end()


class StatTile(QWidget):
    """Big number with a small label underneath."""

    def __init__(self, label: str, value: str = "—", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._value = QLabel(value)
        self._value.setObjectName("dashValue")
        self._value.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._value.setMinimumWidth(60)
        layout.addWidget(self._value)
        self._label = QLabel(label)
        self._label.setObjectName("dashLabel")
        self._label.setWordWrap(True)
        layout.addWidget(self._label)

    def set_value(self, value: str) -> None:
        self._value.setText(value)


class ListRow(QFrame):
    """Compact clickable row with icon, name and meta text."""

    clicked = Signal(str)

    def __init__(self, name: str, meta: str, payload: str, icon: str = "file", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._payload = payload
        self.setObjectName("dashListItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(payload)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(10)
        icon_label = QLabel()
        icon_label.setFixedSize(16, 16)
        icon_label.setPixmap(SvgIcons.themed(icon, "text_muted", 16).pixmap(16, 16))
        layout.addWidget(icon_label)
        name_label = QLabel(name)
        name_label.setObjectName("dashListItemName")
        name_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        name_label.setMinimumWidth(60)
        layout.addWidget(name_label, stretch=1)
        meta_label = QLabel(meta)
        meta_label.setObjectName("dashListItemMeta")
        meta_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(meta_label)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._payload)
        super().mousePressEvent(event)
