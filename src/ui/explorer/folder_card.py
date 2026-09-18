"""
OP(AI)UM — Folder Card Widget

Individual card representing a folder in the card/grid view.
Shows folder icon, name, item count, and access time.
Supports single-click (select/preview) and double-click (open in Explorer).
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QContextMenuEvent, QFont, QFontMetrics, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.config.constants import AppConstants
from src.core.models import RecentItem
from src.utils.time_utils import TimeUtils


class FolderCard(QFrame):
    """
    Card widget for a folder in the grid view.

    Signals:
        clicked(RecentItem): Single click — select for preview.
        double_clicked(RecentItem): Double click — open in Explorer.
        context_menu_requested(RecentItem, QPoint): Right-click context menu.
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

        self.setObjectName("folderCard")
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

        # Folder icon
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setObjectName("folderCardIcon")

        # Use Qt's built-in folder icon
        from src.utils.icon_provider import IconProvider

        provider = IconProvider.shared()
        icon = provider.get_folder_icon(self._item.path if self._item.exists else None)
        pixmap = icon.pixmap(QSize(48, 48))
        icon_label.setPixmap(pixmap)
        layout.addWidget(icon_label)

        # Folder name (elided to the card width)
        name_label = QLabel()
        name_label.setObjectName("folderCardName")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(False)
        name_font = QFont()
        name_font.setPointSize(9)
        name_font.setBold(True)
        name_label.setFont(name_font)
        metrics = QFontMetrics(name_font)
        name_label.setText(metrics.elidedText(self._item.name, Qt.TextElideMode.ElideMiddle, self.width() - 24))
        name_label.setToolTip(self._item.name)
        layout.addWidget(name_label)

        # Item count
        count_text = ""
        if self._item.item_count:
            folders, files = self._item.item_count
            parts = []
            if folders:
                parts.append(f"{folders} folder{'s' if folders != 1 else ''}")
            if files:
                parts.append(f"{files} file{'s' if files != 1 else ''}")
            count_text = ", ".join(parts) if parts else "Empty"
        else:
            count_text = "—"

        count_label = QLabel(count_text)
        count_label.setObjectName("folderCardCount")
        count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_font = QFont()
        count_font.setPointSize(7)
        count_label.setFont(count_font)
        layout.addWidget(count_label)

        # Access time
        time_label = QLabel(TimeUtils.format_relative(self._item.accessed_at))
        time_label.setObjectName("folderCardTime")
        time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_font = QFont()
        time_font.setPointSize(7)
        time_label.setFont(time_font)
        layout.addWidget(time_label)

        # Broken indicator
        if self._item.is_broken or not self._item.exists:
            broken_label = QLabel("Not Found")
            broken_label.setObjectName("folderCardBroken")
            broken_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            broken_font = QFont()
            broken_font.setPointSize(7)
            broken_font.setItalic(True)
            broken_label.setFont(broken_font)
            layout.addWidget(broken_label)

        # Tooltip with full path
        self.setToolTip(f"{self._item.path}\n{self._item.display_datetime}")

    @property
    def item(self) -> RecentItem:
        return self._item

    @property
    def is_selected(self) -> bool:
        return self._selected

    def set_selected(self, selected: bool) -> None:
        """Set the visual selection state."""
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
        # Navigation/opening is handled by the explorer panel (single source of truth).
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self._item)
