"""
OP(AI)UM — Conversations Sidebar

Left-side panel showing conversation history.
Users can create new chats, restore old ones, and delete conversations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QMenu,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QAction, QCursor

from loguru import logger

from src.ai.conversation_db import ConversationDB, ConversationRecord


class ConversationItem(QFrame):
    """A single conversation entry in the sidebar."""

    clicked = Signal(int)       # conversation_id
    delete_requested = Signal(int)

    def __init__(self, record: ConversationRecord, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._record = record
        self._selected = False
        self.setObjectName("convItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(58)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        # Title
        title = QLabel(self._record.title or "New Conversation")
        title.setObjectName("convItemTitle")
        title.setWordWrap(False)
        title_font = QFont()
        title_font.setPointSize(9)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setMaximumWidth(200)
        layout.addWidget(title)

        # Meta row: folder + time
        meta_layout = QHBoxLayout()
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(4)

        if self._record.folder_name:
            folder_label = QLabel(f"📁 {self._record.folder_name}")
            folder_label.setObjectName("convItemFolder")
            folder_font = QFont()
            folder_font.setPointSize(7)
            folder_label.setFont(folder_font)
            folder_label.setMaximumWidth(130)
            meta_layout.addWidget(folder_label)

        meta_layout.addStretch()

        time_label = QLabel(self._record.display_time)
        time_label.setObjectName("convItemTime")
        time_font = QFont()
        time_font.setPointSize(7)
        time_label.setFont(time_font)
        meta_layout.addWidget(time_label)

        layout.addLayout(meta_layout)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._record.id)
        super().mousePressEvent(event)

    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.setObjectName("contextMenu")
        delete_action = QAction("Delete Conversation", menu)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(self._record.id))
        menu.addAction(delete_action)
        menu.exec(self.mapToGlobal(pos))

    @property
    def conversation_id(self) -> int:
        return self._record.id


class ConversationsSidebar(QWidget):
    """
    Left sidebar showing conversation history.

    Signals:
        conversation_selected(int): User clicked a conversation.
        new_chat_requested(): User wants a new conversation.
    """

    conversation_selected = Signal(int)
    new_chat_requested = Signal()

    def __init__(self, conversation_db: ConversationDB, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._db = conversation_db
        self._items: list[ConversationItem] = []
        self._current_id: Optional[int] = None
        self.setObjectName("convSidebar")
        self.setFixedWidth(240)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with "New Chat" button
        header = QWidget()
        header.setObjectName("convSidebarHeader")
        header.setFixedHeight(44)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 6, 10, 6)

        title = QLabel("Conversations")
        title.setObjectName("convSidebarTitle")
        title_font = QFont()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)

        header_layout.addStretch()

        new_btn = QPushButton("+")
        new_btn.setObjectName("convNewBtn")
        new_btn.setFixedSize(28, 28)
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.setToolTip("New Conversation")
        btn_font = QFont()
        btn_font.setPointSize(14)
        btn_font.setBold(True)
        new_btn.setFont(btn_font)
        new_btn.clicked.connect(self.new_chat_requested.emit)
        header_layout.addWidget(new_btn)

        layout.addWidget(header)

        # Scrollable conversation list
        scroll = QScrollArea()
        scroll.setObjectName("convSidebarScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(6, 4, 6, 4)
        self._list_layout.setSpacing(2)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self._list_container)
        layout.addWidget(scroll)

    def refresh(self) -> None:
        """Reload conversations from the database."""
        # Clear existing items
        while self._list_layout.count() > 0:
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._items.clear()

        conversations = self._db.get_conversations()
        for conv in conversations:
            item = ConversationItem(conv)
            item.clicked.connect(self._on_item_clicked)
            item.delete_requested.connect(self._on_delete_requested)
            if conv.id == self._current_id:
                item.set_selected(True)
            self._list_layout.addWidget(item)
            self._items.append(item)

        if not conversations:
            empty = QLabel("No conversations yet")
            empty.setObjectName("convEmptyLabel")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_font = QFont()
            empty_font.setPointSize(9)
            empty.setFont(empty_font)
            self._list_layout.addWidget(empty)

    def set_current_conversation(self, conv_id: Optional[int]) -> None:
        """Highlight the current conversation."""
        self._current_id = conv_id
        for item in self._items:
            item.set_selected(item.conversation_id == conv_id)

    def _on_item_clicked(self, conv_id: int) -> None:
        self.set_current_conversation(conv_id)
        self.conversation_selected.emit(conv_id)

    def _on_delete_requested(self, conv_id: int) -> None:
        self._db.delete_conversation(conv_id)
        if self._current_id == conv_id:
            self._current_id = None
        self.refresh()
