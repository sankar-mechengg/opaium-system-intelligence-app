"""
OP(AI)UM — Card Grid View

Displays files and folders as cards in a flowing grid layout,
grouped by time periods (Last 2 Days, Last Week, Last Month).
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.core.models import RecentItem
from src.ui.explorer.file_card import FileCard
from src.ui.explorer.folder_card import FolderCard
from src.ui.widgets.collapsible_section import CollapsibleSection
from src.utils.time_utils import TimeGroup, TimeUtils


class FlowLayout(QWidget):
    """Simple flow layout that wraps cards to new rows."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 8) -> None:
        super().__init__(parent)
        self._widgets: list[QWidget] = []
        self._spacing = spacing

    def add_widget(self, widget: QWidget) -> None:
        widget.setParent(self)
        self._widgets.append(widget)
        self._relayout()

    def clear(self) -> None:
        for w in self._widgets:
            w.deleteLater()
        self._widgets.clear()
        self.setFixedHeight(0)

    def _relayout(self) -> None:
        if not self._widgets:
            self.setFixedHeight(0)
            return

        visible = [w for w in self._widgets if w.isVisible()]
        if not visible:
            self.setFixedHeight(0)
            return

        x = 0
        y = 0
        row_height = 0
        pw = self.parentWidget()
        available_width = max((pw.width() - 20) if pw is not None else 800, 400)

        for widget in visible:
            w = widget.width()
            h = widget.height()

            if x + w > available_width and x > 0:
                x = 0
                y += row_height + self._spacing
                row_height = 0

            widget.move(x, y)

            x += w + self._spacing
            row_height = max(row_height, h)

        total_height = y + row_height + self._spacing
        self.setFixedHeight(total_height)

    def resizeEvent(self, event: QResizeEvent) -> None:
        self._relayout()
        super().resizeEvent(event)


class CardGridView(QWidget):
    """
    Main card/grid view displaying recent items grouped by time.

    Signals:
        item_selected(RecentItem): Card single-clicked.
        item_opened(RecentItem): Card double-clicked.
        context_menu_requested(RecentItem, QPoint): Right-click.
    """

    item_selected = Signal(object)
    item_opened = Signal(object)
    context_menu_requested = Signal(object, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sections: dict[TimeGroup, tuple[CollapsibleSection, FlowLayout]] = {}
        self._all_cards: list[FolderCard | FileCard] = []
        self._selected_card: FolderCard | FileCard | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area
        scroll = QScrollArea()
        scroll.setObjectName("cardGridScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        # Container
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(12, 8, 12, 8)
        self._container_layout.setSpacing(8)

        # Create sections for each time group
        for group in TimeUtils.group_order():
            section = CollapsibleSection(title=group.value, expanded=True)
            flow = FlowLayout(spacing=10)
            section.add_widget(flow)
            self._sections[group] = (section, flow)
            self._container_layout.addWidget(section)

        self._container_layout.addStretch()

        scroll.setWidget(self._container)
        outer_layout.addWidget(scroll)

    def set_items(self, grouped_items: dict[TimeGroup, list[RecentItem]]) -> None:
        """
        Populate the grid with grouped items.

        Args:
            grouped_items: Dict mapping TimeGroup → list of RecentItem.
        """
        self._clear_all()

        for group in TimeUtils.group_order():
            items = grouped_items.get(group, [])
            section, flow = self._sections[group]

            section.set_count(len(items))

            if not items:
                section.setVisible(False)
                continue

            section.setVisible(True)

            for item in items:
                card = self._create_card(item)
                flow.add_widget(card)
                self._all_cards.append(card)

        logger.debug(f"Card grid populated: {len(self._all_cards)} cards")

    def filter_items(self, search_text: str, type_filter: str = "All Items") -> None:
        """
        Filter visible cards by search text and type.
        """
        search_lower = search_text.lower()

        for card in self._all_cards:
            item = card.item
            visible = True

            # Text filter
            if search_lower:
                if search_lower not in item.name.lower() and search_lower not in item.path.lower():
                    visible = False

            # Type filter
            if visible and type_filter != "All Items":
                if (
                    type_filter == "Folders Only"
                    and not item.is_folder
                    or type_filter == "Files Only"
                    and not item.is_file
                ):
                    visible = False
                elif type_filter in ("Images", "Documents", "Videos", "Audio", "Archives", "Code"):
                    visible = self._matches_type_filter(item, type_filter)

            card.setVisible(visible)

        # Relayout all flow widgets and hide sections with no visible cards
        for section, flow in self._sections.values():
            has_visible = any(w.isVisible() for w in flow._widgets)
            section.setVisible(has_visible)
            flow._relayout()

    def _matches_type_filter(self, item: RecentItem, type_filter: str) -> bool:
        """Check if item matches a type filter category."""
        if item.is_folder:
            return False

        ext = item.extension.lower()
        type_map = {
            "Images": {"png", "jpg", "jpeg", "gif", "bmp", "webp", "svg", "ico", "tiff"},
            "Documents": {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "md", "csv"},
            "Videos": {"mp4", "avi", "mkv", "mov", "wmv", "flv", "webm"},
            "Audio": {"mp3", "wav", "flac", "aac", "ogg", "wma", "m4a"},
            "Archives": {"zip", "rar", "7z", "tar", "gz"},
            "Code": {"py", "js", "ts", "html", "css", "java", "cpp", "c", "json", "xml"},
        }
        return ext in type_map.get(type_filter, set())

    def _create_card(self, item: RecentItem) -> FolderCard | FileCard:
        """Create the appropriate card widget for an item."""
        card = FolderCard(item) if item.is_folder else FileCard(item)

        card.clicked.connect(self._on_card_clicked)
        card.double_clicked.connect(self.item_opened.emit)
        card.context_menu_requested.connect(self.context_menu_requested.emit)

        return card

    def _on_card_clicked(self, item: RecentItem) -> None:
        """Handle card selection."""
        # Deselect previous
        if self._selected_card:
            self._selected_card.set_selected(False)

        # Find and select new card
        for card in self._all_cards:
            if card.item.path == item.path:
                card.set_selected(True)
                self._selected_card = card
                break

        self.item_selected.emit(item)

    def _clear_all(self) -> None:
        """Remove all cards."""
        for card in self._all_cards:
            card.deleteLater()
        self._all_cards.clear()
        self._selected_card = None

        for _, flow in self._sections.values():
            flow.clear()

    def get_selected_item(self) -> RecentItem | None:
        """Get the currently selected item."""
        if self._selected_card:
            return self._selected_card.item
        return None
