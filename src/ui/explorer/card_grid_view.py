"""
OP(AI)UM — Card Grid View

Displays files and folders as cards in a flowing grid, organised in named
collapsible groups (time buckets on the Home view, Folders / Files when
browsing a directory). Supports keyboard navigation and an empty state.
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent, QResizeEvent
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from src.core.models import RecentItem
from src.ui.explorer.file_card import FileCard
from src.ui.explorer.folder_card import FolderCard
from src.ui.widgets.collapsible_section import CollapsibleSection
from src.utils.icon_provider import SvgIcons

TYPE_FILTER_MAP: dict[str, set[str]] = {
    "Images": {"png", "jpg", "jpeg", "gif", "bmp", "webp", "svg", "ico", "tiff", "heic", "avif"},
    "Documents": {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "md", "csv", "rtf", "odt", "tex"},
    "Videos": {"mp4", "avi", "mkv", "mov", "wmv", "flv", "webm", "m4v"},
    "Audio": {"mp3", "wav", "flac", "aac", "ogg", "wma", "m4a", "opus"},
    "Archives": {"zip", "rar", "7z", "tar", "gz", "bz2", "xz", "iso"},
    "Code": {
        "py",
        "js",
        "ts",
        "tsx",
        "jsx",
        "html",
        "css",
        "java",
        "cpp",
        "c",
        "h",
        "cs",
        "go",
        "rs",
        "json",
        "xml",
        "yaml",
        "yml",
        "toml",
        "sh",
        "ps1",
        "bat",
    },
}


def item_matches(item: RecentItem, search_lower: str, type_filter: str) -> bool:
    """Shared filter predicate for grid and list views."""
    if search_lower and search_lower not in item.name.lower() and search_lower not in item.path.lower():
        return False
    if type_filter == "All Items" or not type_filter:
        return True
    if type_filter == "Folders Only":
        return item.is_folder
    if type_filter == "Files Only":
        return item.is_file
    if item.is_folder:
        return False
    return item.extension.lower() in TYPE_FILTER_MAP.get(type_filter, set())


class FlowLayout(QWidget):
    """Simple flow layout that wraps cards to new rows."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 10) -> None:
        super().__init__(parent)
        self._widgets: list[QWidget] = []
        self._spacing = spacing

    @property
    def widgets(self) -> list[QWidget]:
        return self._widgets

    def add_widget(self, widget: QWidget) -> None:
        widget.setParent(self)
        widget.show()
        self._widgets.append(widget)

    def clear(self) -> None:
        for w in self._widgets:
            w.setParent(None)
            w.deleteLater()
        self._widgets.clear()
        self.setFixedHeight(0)

    def relayout(self) -> None:
        visible = [w for w in self._widgets if not w.isHidden()]
        if not visible:
            self.setFixedHeight(0)
            return

        x = 0
        y = 0
        row_height = 0
        pw = self.parentWidget()
        available_width = max((pw.width() - 8) if pw is not None else 800, 200)

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

        self.setFixedHeight(y + row_height + self._spacing)

    def resizeEvent(self, event: QResizeEvent) -> None:
        self.relayout()
        super().resizeEvent(event)


class CardGridView(QWidget):
    """
    Signals:
        item_selected(RecentItem): Card single-clicked / keyboard focused.
        item_opened(RecentItem): Card double-clicked or Enter.
        context_menu_requested(RecentItem, QPoint): Right-click.
        selection_cleared(): Background clicked.
    """

    item_selected = Signal(object)
    item_opened = Signal(object)
    context_menu_requested = Signal(object, object)
    selection_cleared = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sections: dict[str, tuple[CollapsibleSection, FlowLayout]] = {}
        self._all_cards: list[FolderCard | FileCard] = []
        self._selected_card: FolderCard | FileCard | None = None
        self._card_width = 160
        self._card_height = 140
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._build_ui()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("cardGridScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.viewport().installEventFilter(self)

        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(12, 8, 12, 8)
        self._container_layout.setSpacing(6)

        # Empty state
        self._empty = QWidget()
        self._empty.setObjectName("emptyState")
        empty_layout = QVBoxLayout(self._empty)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(6)
        self._empty_icon = QLabel()
        self._empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_title = QLabel("Nothing here yet")
        self._empty_title.setObjectName("emptyStateTitle")
        self._empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_text = QLabel("")
        self._empty_text.setObjectName("emptyStateText")
        self._empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_text.setWordWrap(True)
        empty_layout.addStretch()
        empty_layout.addWidget(self._empty_icon)
        empty_layout.addWidget(self._empty_title)
        empty_layout.addWidget(self._empty_text)
        empty_layout.addStretch()
        self._empty.hide()
        self._container_layout.addWidget(self._empty)

        self._container_layout.addStretch()
        self._scroll.setWidget(self._container)
        outer_layout.addWidget(self._scroll)

    # === Configuration ===

    def set_card_size(self, width: int, height: int) -> None:
        self._card_width = max(120, width)
        self._card_height = max(100, height)

    # === Population ===

    def set_groups(self, groups: list[tuple[str, list[RecentItem]]], collapsed_when_empty: bool = True) -> None:
        """Populate the grid with ordered (title, items) groups."""
        self._clear_all()

        total = 0
        for title, items in groups:
            section = CollapsibleSection(title=title, expanded=True)
            flow = FlowLayout(spacing=10)
            section.add_widget(flow)
            section.set_count(len(items))
            self._sections[title] = (section, flow)
            self._container_layout.insertWidget(self._container_layout.count() - 1, section)
            if not items and collapsed_when_empty:
                section.setVisible(False)
                continue
            for item in items:
                card = self._create_card(item)
                flow.add_widget(card)
                self._all_cards.append(card)
                total += 1
            flow.relayout()

        self._empty.setVisible(total == 0)
        logger.debug(f"Card grid populated: {total} cards in {len(groups)} groups")

    def set_empty_state(self, title: str, text: str, icon: str = "folder-open") -> None:
        self._empty_title.setText(title)
        self._empty_text.setText(text)
        self._empty_icon.setPixmap(SvgIcons.pixmap(icon, self._empty_color(), 56))

    @staticmethod
    def _empty_color() -> str:
        from src.ui.theme import token

        return token("text_faint")

    def filter_items(self, search_text: str, type_filter: str = "All Items") -> int:
        """Filter visible cards by search text and type. Returns the visible count."""
        search_lower = search_text.lower()
        visible_total = 0
        for card in self._all_cards:
            visible = item_matches(card.item, search_lower, type_filter)
            card.setVisible(visible)
            visible_total += int(visible)

        for section, flow in self._sections.values():
            has_visible = any(not w.isHidden() for w in flow.widgets)
            section.setVisible(has_visible)
            flow.relayout()

        if self._all_cards:
            self._empty.setVisible(visible_total == 0)
        return visible_total

    def relayout(self) -> None:
        for _section, flow in self._sections.values():
            flow.relayout()

    def _create_card(self, item: RecentItem) -> FolderCard | FileCard:
        card: FolderCard | FileCard
        if item.is_folder:
            card = FolderCard(item, card_width=self._card_width, card_height=self._card_height)
        else:
            card = FileCard(item, card_width=self._card_width, card_height=self._card_height)
        card.clicked.connect(self._on_card_clicked)
        card.double_clicked.connect(self.item_opened.emit)
        card.context_menu_requested.connect(self._on_card_context_menu)
        return card

    # === Selection ===

    def _on_card_clicked(self, item: RecentItem) -> None:
        self.setFocus()
        self._select_card_for(item)
        self.item_selected.emit(item)

    def _on_card_context_menu(self, item: RecentItem, pos: object) -> None:
        self._select_card_for(item)
        self.item_selected.emit(item)
        self.context_menu_requested.emit(item, pos)

    def _select_card_for(self, item: RecentItem) -> None:
        if self._selected_card:
            self._selected_card.set_selected(False)
            self._selected_card = None
        for card in self._all_cards:
            if card.item.path == item.path:
                card.set_selected(True)
                self._selected_card = card
                self._scroll.ensureWidgetVisible(card, 20, 20)
                break

    def select_path(self, path: str) -> None:
        for card in self._all_cards:
            if card.item.path == path:
                self._on_card_clicked(card.item)
                return

    def clear_selection(self) -> None:
        if self._selected_card:
            self._selected_card.set_selected(False)
            self._selected_card = None
        self.selection_cleared.emit()

    def get_selected_item(self) -> RecentItem | None:
        return self._selected_card.item if self._selected_card else None

    def _visible_cards(self) -> list[FolderCard | FileCard]:
        return [c for c in self._all_cards if not c.isHidden()]

    def keyPressEvent(self, event: QKeyEvent) -> None:
        cards = self._visible_cards()
        if not cards:
            super().keyPressEvent(event)
            return
        key = event.key()
        current = cards.index(self._selected_card) if self._selected_card in cards else -1

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._selected_card:
            self.item_opened.emit(self._selected_card.item)
            return

        per_row = max(1, (self._scroll.viewport().width() - 24) // (self._card_width + 10))
        target = current
        if key == Qt.Key.Key_Right:
            target = min(len(cards) - 1, current + 1)
        elif key == Qt.Key.Key_Left:
            target = max(0, current - 1)
        elif key == Qt.Key.Key_Down:
            target = min(len(cards) - 1, current + per_row)
        elif key == Qt.Key.Key_Up:
            target = max(0, current - per_row)
        elif key == Qt.Key.Key_Home:
            target = 0
        elif key == Qt.Key.Key_End:
            target = len(cards) - 1
        else:
            super().keyPressEvent(event)
            return

        if target != current and 0 <= target < len(cards):
            self._on_card_clicked(cards[target].item)
        event.accept()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        # Cards accept their own presses; anything reaching the viewport hit empty space.
        if watched is self._scroll.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            self.clear_selection()
        return super().eventFilter(watched, event)

    def _clear_all(self) -> None:
        for card in self._all_cards:
            card.deleteLater()
        self._all_cards.clear()
        self._selected_card = None
        for section, flow in self._sections.values():
            flow.clear()
            section.setParent(None)
            section.deleteLater()
        self._sections.clear()
