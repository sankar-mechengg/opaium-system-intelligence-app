"""
OP(AI)UM — Chat Message Bubble

Individual message widget for the chat view.
Supports user messages, AI responses, and system messages.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class MessageRole:
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage:
    """Data model for a chat message."""

    def __init__(
        self,
        role: str,
        content: str,
        timestamp: datetime | None = None,
    ) -> None:
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now()


class MessageBubble(QFrame):
    """
    Visual chat message bubble.

    User messages align right, AI messages align left.
    System messages are centered and styled differently.
    """

    def __init__(self, message: ChatMessage, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._message = message
        self.setObjectName(f"messageBubble_{message.role}")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._build_ui()

    def _build_ui(self) -> None:
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(8, 4, 8, 4)

        is_user = self._message.role == MessageRole.USER
        is_system = self._message.role == MessageRole.SYSTEM

        if is_user:
            outer_layout.addStretch()

        # Bubble container
        bubble = QFrame()
        bubble.setObjectName(f"bubble_{self._message.role}")
        bubble.setMaximumWidth(520)

        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(12, 8, 12, 8)
        bubble_layout.setSpacing(4)

        # Role label for AI
        if not is_user and not is_system:
            role_label = QLabel("OP(AI)UM")
            role_label.setObjectName("bubbleRole")
            role_font = QFont()
            role_font.setPointSize(8)
            role_font.setBold(True)
            role_label.setFont(role_font)
            bubble_layout.addWidget(role_label)

        # Content
        content_label = QLabel(self._message.content)
        content_label.setObjectName(f"bubbleContent_{self._message.role}")
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        content_font = QFont()
        content_font.setPointSize(10)
        content_label.setFont(content_font)
        bubble_layout.addWidget(content_label)

        # Timestamp
        time_str = self._message.timestamp.strftime("%H:%M")
        time_label = QLabel(time_str)
        time_label.setObjectName("bubbleTime")
        time_font = QFont()
        time_font.setPointSize(7)
        time_label.setFont(time_font)
        if is_user:
            time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        bubble_layout.addWidget(time_label)

        outer_layout.addWidget(bubble)

        if not is_user:
            outer_layout.addStretch()

    @property
    def message(self) -> ChatMessage:
        return self._message
