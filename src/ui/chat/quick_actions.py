"""
OP(AI)UM — Quick Action Chips

Row of clickable suggestion chips above the chat input
for common file operations.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QWidget,
)

from src.ui.widgets.icon_button import IconButton


class _ChipScroll(QScrollArea):
    """Horizontal strip without a visible scrollbar; the mouse wheel pans it."""

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y() or event.angleDelta().x()
        bar = self.horizontalScrollBar()
        if bar.maximum() > 0 and delta:
            bar.setValue(bar.value() - int(delta / 2))
            event.accept()
            return
        super().wheelEvent(event)


class QuickActionChips(QWidget):
    """
    Horizontal row of quick-action chip buttons.

    Signals:
        chip_clicked(str): The action text to send to the AI.
    """

    chip_clicked = Signal(str)

    DEFAULT_ACTIONS = [
        ("chart", "Count files", "Count the files in {folder}"),
        ("duplicate", "Find duplicates", "Find duplicate files in {folder}"),
        ("folder-open", "Organize by type", "Organize the files in {folder} into folders by type"),
        ("clock", "Organize by date", "Organize the files in {folder} into folders by date"),
        ("broom", "Clean empties", "Find empty folders in {folder}"),
        ("chart", "Folder size", "What's the size of {folder} and what takes the most space?"),
        ("filter", "File types", "Show a file type breakdown for {folder}"),
        ("search", "Large files", "Find the largest files in {folder}"),
        ("disk", "Disk usage", "Show disk usage for all my drives"),
        ("rocket", "Startup programs", "List my Windows startup programs"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_folder: str = ""
        self._build_ui()

    def _build_ui(self) -> None:
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(8, 4, 8, 4)
        outer_layout.setSpacing(0)

        # Scrollable chip area
        scroll = _ChipScroll()
        scroll.setObjectName("chipScroll")
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setFixedHeight(36)

        container = QWidget()
        self._chip_layout = QHBoxLayout(container)
        self._chip_layout.setContentsMargins(0, 0, 0, 0)
        self._chip_layout.setSpacing(6)

        for icon, label, template in self.DEFAULT_ACTIONS:
            chip = IconButton(icon, label, role="text_sub", icon_size=13, object_name="actionChip")
            chip.setFixedHeight(28)

            t = template
            chip.clicked.connect(lambda checked=False, tmpl=t: self._on_chip_clicked(tmpl))
            self._chip_layout.addWidget(chip)

        self._chip_layout.addStretch()
        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

    def _on_chip_clicked(self, template: str) -> None:
        """Replace {folder} placeholder and emit."""
        if self._current_folder:
            text = template.replace("{folder}", self._current_folder)
        else:
            text = template.replace(" in {folder}", "").replace("{folder}", "my files")
        self.chip_clicked.emit(text)

    def set_current_folder(self, folder_path: str) -> None:
        """Update the folder context for chips."""
        from pathlib import Path

        self._current_folder = Path(folder_path).name if folder_path else ""
