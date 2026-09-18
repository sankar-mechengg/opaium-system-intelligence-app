"""
OP(AI)UM — Preview Panel

Right-side panel showing details for the selected file or folder:
icon or image thumbnail, name, type, location, size, dates, contents and a
row of quick actions (Open, Show in Explorer, Copy path, Ask AI).
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from src.config.constants import AppConstants
from src.core.models import RecentItem
from src.ui.widgets.icon_button import IconButton
from src.utils.icon_provider import IconProvider
from src.utils.path_utils import PathUtils
from src.utils.time_utils import TimeUtils

IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "bmp", "webp", "ico", "tiff", "svg"}
MAX_THUMB_BYTES = 40 * 1024 * 1024


class PreviewPanel(QWidget):
    """
    Signals:
        action_requested(str, str): (action, path) — 'open', 'reveal', 'copy_path', 'ask_ai', 'properties'
    """

    action_requested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_provider = IconProvider.shared()
        self._current_item: RecentItem | None = None

        self.setMinimumWidth(AppConstants.PREVIEW_PANEL_WIDTH)
        self.setMaximumWidth(420)
        self.setObjectName("previewPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._build_ui()
        self._show_empty_state()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        header = QLabel("PREVIEW")
        header.setObjectName("previewHeader")
        header_font = QFont()
        header_font.setPointSize(8)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("previewSeparator")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

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

    # === Public ===

    def show_item(self, item: RecentItem) -> None:
        """Display preview for a selected item."""
        self._current_item = item
        self._clear_content()

        # Icon / thumbnail
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb = self._thumbnail(item)
        if thumb is not None:
            icon_label.setObjectName("previewThumb")
            icon_label.setPixmap(thumb)
            icon_label.setMinimumHeight(thumb.height() + 12)
        else:
            icon = (
                self._icon_provider.get_folder_icon(item.path if item.exists else None)
                if item.is_folder
                else self._icon_provider.get_file_icon(item.path)
            )
            icon_label.setPixmap(icon.pixmap(QSize(72, 72)))
        self._content_layout.addWidget(icon_label)

        # Name
        name_label = QLabel(item.name)
        name_label.setObjectName("previewName")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        name_font = QFont()
        name_font.setPointSize(12)
        name_font.setBold(True)
        name_label.setFont(name_font)
        self._content_layout.addWidget(name_label)

        # Quick actions
        self._content_layout.addWidget(self._build_actions(item))

        # Details
        type_text = "Folder" if item.is_folder else (f"{item.extension.upper()} file" if item.extension else "File")
        self._add_info_row("Type", type_text)
        self._add_info_row("Location", str(Path(item.path).parent), selectable=True)

        if not item.exists:
            self._add_info_row("Status", "Not found", color="red")

        if item.is_file:
            self._add_info_row("Size", PathUtils.format_size(item.size_bytes))

        if item.is_folder and item.item_count:
            folders, files = item.item_count
            self._add_info_row("Contents", f"{folders} folders, {files} files")

        try:
            st = os.stat(item.path)
            self._add_info_row("Modified", TimeUtils.format_datetime(datetime.fromtimestamp(st.st_mtime)))
            self._add_info_row("Created", TimeUtils.format_datetime(datetime.fromtimestamp(st.st_ctime)))
        except OSError:
            pass

        if item.lnk_source:
            self._add_info_row("Last opened", TimeUtils.format_datetime(item.accessed_at))
            self._add_info_row("", TimeUtils.format_relative(item.accessed_at))

        self._content_layout.addStretch()

    def clear(self) -> None:
        """Reset to empty state."""
        self._current_item = None
        self._show_empty_state()

    # === Internals ===

    def _build_actions(self, item: RecentItem) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        actions = [
            ("external", "Open", "open"),
            ("folder-open", "Show in Explorer", "reveal"),
            ("copy", "Copy path", "copy_path"),
            ("sparkle", "Ask AI about this", "ask_ai"),
            ("properties", "Properties", "properties"),
        ]
        for icon, tip, action in actions:
            btn = IconButton(icon, role="text_sub", icon_size=16, tooltip=tip, object_name="previewActionBtn")
            btn.setFixedSize(34, 30)
            btn.clicked.connect(lambda checked=False, a=action, p=item.path: self.action_requested.emit(a, p))
            layout.addWidget(btn)
        return row

    @staticmethod
    def _thumbnail(item: RecentItem) -> QPixmap | None:
        if item.is_folder or item.extension.lower() not in IMAGE_EXTS or not item.exists:
            return None
        if item.size_bytes > MAX_THUMB_BYTES:
            return None
        pix = QPixmap(item.path)
        if pix.isNull():
            return None
        return pix.scaled(220, 160, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

    def _show_empty_state(self) -> None:
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

    def _add_info_row(self, label: str, value: str, color: str = "", selectable: bool = False) -> None:
        if label:
            label_widget = QLabel(label.upper())
            label_widget.setObjectName("previewLabel")
            self._content_layout.addWidget(label_widget)

        value_widget = QLabel(value)
        value_widget.setObjectName("previewValue")
        value_widget.setWordWrap(True)
        if color:
            from src.ui.theme import token

            value_widget.setStyleSheet(f"color: {token(color)};")
        if selectable:
            value_widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._content_layout.addWidget(value_widget)

    def _clear_content(self) -> None:
        while self._content_layout.count():
            li = self._content_layout.takeAt(0)
            w = li.widget() if li is not None else None
            if w is not None:
                w.deleteLater()
