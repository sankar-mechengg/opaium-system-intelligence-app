"""
OP(AI)UM — Quick Action Chips

Row of clickable suggestion chips above the chat input
for common file operations.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QScrollArea, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


class QuickActionChips(QWidget):
    """
    Horizontal row of quick-action chip buttons.

    Signals:
        chip_clicked(str): The action text to send to the AI.
    """

    chip_clicked = Signal(str)

    DEFAULT_ACTIONS = [
        ("📊 Count files", "Count the files in {folder}"),
        ("🔍 Find duplicates", "Find duplicate files in {folder}"),
        ("📁 Organize by type", "Organize files in {folder} by type"),
        ("📅 Organize by date", "Organize files in {folder} by date"),
        ("🗑️ Clean empties", "Find empty folders in {folder}"),
        ("📏 Folder size", "What's the size of {folder}?"),
        ("📋 File types", "Show file type breakdown for {folder}"),
        ("🔄 Find large files", "Find large files in {folder}"),
        ("💾 Disk usage", "Show disk usage info"),
        ("🚀 Startup programs", "List my startup programs"),
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
        scroll = QScrollArea()
        scroll.setObjectName("chipScroll")
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setFixedHeight(40)

        container = QWidget()
        self._chip_layout = QHBoxLayout(container)
        self._chip_layout.setContentsMargins(0, 0, 0, 0)
        self._chip_layout.setSpacing(6)

        for label, template in self.DEFAULT_ACTIONS:
            chip = QPushButton(label)
            chip.setObjectName("actionChip")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setFixedHeight(30)
            chip_font = QFont()
            chip_font.setPointSize(8)
            chip.setFont(chip_font)

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
