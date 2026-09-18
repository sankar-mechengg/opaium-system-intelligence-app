"""
OP(AI)UM — File Card Widget

Individual card representing a file in the card/grid view.
Shows file icon, name, size, and access time.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QContextMenuEvent, QFont, QFontMetrics, QMouseEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from src.config.constants import AppConstants
from src.core.models import RecentItem
from src.utils.path_utils import PathUtils
from src.utils.time_utils import TimeUtils


class FileCard(QFrame):
    """
    Card widget for a file in the grid view.

    Signals:
        clicked(RecentItem): Single click — select for preview.
        double_clicked(RecentItem): Double click — open file.
        context_menu_requested(RecentItem, QPoint): Right-click.
    """

    clicked = Signal(object)
    double_clicked = Signal(object)
    context_menu_requested = Signal(object, object)

    def __init__(
        self,
        item: RecentItem,
        card_width: int = AppConstants.CARD_WIDTH,
        card_height: int = AppConstants.CARD_HEIGHT,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._item = item
        self._selected = False

        self.setObjectName("fileCard")
        self.setFixedSize(card_width, card_height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setProperty("selected", False)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 8)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # File icon
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        from src.utils.icon_provider import IconProvider

        provider = IconProvider.shared()
        icon = provider.get_file_icon(self._item.path)
        pixmap = icon.pixmap(QSize(40, 40))
        icon_label.setPixmap(pixmap)
        layout.addWidget(icon_label)

        # Extension badge
        if self._item.extension:
            ext_label = QLabel(f".{self._item.extension}")
            ext_label.setObjectName("fileCardExt")
            ext_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ext_font = QFont()
            ext_font.setPointSize(7)
            ext_font.setBold(True)
            ext_label.setFont(ext_font)
            layout.addWidget(ext_label)

        # File name (elided to the card width)
        name_label = QLabel()
        name_label.setObjectName("fileCardName")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(False)
        name_font = QFont()
        name_font.setPointSize(9)
        name_label.setFont(name_font)
        metrics = QFontMetrics(name_font)
        name_label.setText(metrics.elidedText(self._item.name, Qt.TextElideMode.ElideMiddle, self.width() - 24))
        name_label.setToolTip(self._item.name)
        layout.addWidget(name_label)

        # Size
        size_label = QLabel(PathUtils.format_size(self._item.size_bytes))
        size_label.setObjectName("fileCardSize")
        size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        size_font = QFont()
        size_font.setPointSize(7)
        size_label.setFont(size_font)
        layout.addWidget(size_label)

        # Time
        time_label = QLabel(TimeUtils.format_relative(self._item.accessed_at))
        time_label.setObjectName("fileCardTime")
        time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_font = QFont()
        time_font.setPointSize(7)
        time_label.setFont(time_font)
        layout.addWidget(time_label)

        self.setToolTip(f"{self._item.path}\n{self._item.display_size}\n{self._item.display_datetime}")

    @property
    def item(self) -> RecentItem:
        return self._item

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._item)
        elif event.button() == Qt.MouseButton.RightButton:
            self.context_menu_requested.emit(self._item, event.globalPosition().toPoint())

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        # The right-button press already opened our menu; stop the event from
        # reaching the panel's background menu.
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        # Opening is handled by the explorer panel (single source of truth).
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self._item)
