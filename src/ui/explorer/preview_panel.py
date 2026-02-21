"""
OP(AI)UM — Preview Panel

Right-side panel showing metadata for the selected
file or folder. Displays name, path, size, dates,
and item counts for folders.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QScrollArea,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QPixmap

from src.core.models import RecentItem
from src.config.constants import AppConstants
from src.utils.path_utils import PathUtils
from src.utils.time_utils import TimeUtils
from src.utils.icon_provider import IconProvider


class PreviewPanel(QWidget):
    """
    Right-side metadata preview panel.

    Shows information about the currently selected item.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_provider = IconProvider()
        self._current_item: Optional[RecentItem] = None

        self.setMinimumWidth(AppConstants.PREVIEW_PANEL_WIDTH)
        self.setMaximumWidth(380)
        self.setObjectName("previewPanel")

        self._build_ui()
        self._show_empty_state()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Header
        header = QLabel("Preview")
        header.setObjectName("previewHeader")
        header_font = QFont()
        header_font.setPointSize(10)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("previewSeparator")
        layout.addWidget(sep)

        # Scroll content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(8)
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self._content)
        layout.addWidget(scroll, stretch=1)

    def show_item(self, item: RecentItem) -> None:
        """Display preview for a selected item."""
        self._current_item = item
        self._clear_content()

        # Icon
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if item.is_folder:
            icon = self._icon_provider.get_folder_icon(item.path if item.exists else None)
        else:
            icon = self._icon_provider.get_file_icon(item.path)
        pixmap = icon.pixmap(QSize(64, 64))
        icon_label.setPixmap(pixmap)
        self._content_layout.addWidget(icon_label)

        # Name
        name_label = QLabel(item.name)
        name_label.setObjectName("previewName")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        name_font = QFont()
        name_font.setPointSize(12)
        name_font.setBold(True)
        name_label.setFont(name_font)
        self._content_layout.addWidget(name_label)

        # Type
        type_text = "Folder" if item.is_folder else f"File (.{item.extension})" if item.extension else "File"
        self._add_info_row("Type", type_text)

        # Path
        self._add_info_row("Location", str(Path(item.path).parent), selectable=True)

        # Status
        if not item.exists:
            self._add_info_row("Status", "Not Found", color="#F44336")
        else:
            self._add_info_row("Status", "Available", color="#4CAF50")

        # Size
        if item.is_file and item.size_bytes > 0:
            self._add_info_row("Size", PathUtils.format_size(item.size_bytes))

        # Item counts for folders
        if item.is_folder and item.item_count:
            folders, files = item.item_count
            self._add_info_row("Contents", f"{folders} folders, {files} files")

        # Access time
        self._add_info_row("Last Accessed", TimeUtils.format_datetime(item.accessed_at))
        self._add_info_row("", TimeUtils.format_relative(item.accessed_at))

        # Time group
        self._add_info_row("Group", item.time_group.value)

        self._content_layout.addStretch()

    def _show_empty_state(self) -> None:
        """Show placeholder when nothing is selected."""
        self._clear_content()

        empty_label = QLabel("Select an item to\nview its details")
        empty_label.setObjectName("previewEmpty")
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_font = QFont()
        empty_font.setPointSize(10)
        empty_label.setFont(empty_font)
        self._content_layout.addStretch()
        self._content_layout.addWidget(empty_label)
        self._content_layout.addStretch()

    def _add_info_row(
        self,
        label: str,
        value: str,
        color: str = "",
        selectable: bool = False,
    ) -> None:
        """Add a label-value row to the preview."""
        if label:
            label_widget = QLabel(label)
            label_widget.setObjectName("previewLabel")
            label_font = QFont()
            label_font.setPointSize(8)
            label_font.setBold(True)
            label_widget.setFont(label_font)
            self._content_layout.addWidget(label_widget)

        value_widget = QLabel(value)
        value_widget.setObjectName("previewValue")
        value_widget.setWordWrap(True)
        value_font = QFont()
        value_font.setPointSize(9)
        value_widget.setFont(value_font)

        if color:
            value_widget.setStyleSheet(f"color: {color};")

        if selectable:
            value_widget.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )

        self._content_layout.addWidget(value_widget)

    def _clear_content(self) -> None:
        """Remove all content widgets."""
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def clear(self) -> None:
        """Reset to empty state."""
        self._current_item = None
        self._show_empty_state()
