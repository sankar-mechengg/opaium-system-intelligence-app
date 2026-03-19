"""
OP(AI)UM — Chat Message Bubble

Individual message widget for the chat view.
Supports user messages, AI responses (with markdown), and system messages.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QSizePolicy, QTextBrowser,
)
from PySide6.QtCore import Qt, QSize, QRectF, QTimer
from PySide6.QtGui import QFont, QPainter, QPixmap, QColor, QBrush, QPen


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


class StyledBubbleFrame(QFrame):
    """QFrame subclass that properly paints QSS backgrounds and borders."""

    def paintEvent(self, event):
        from PySide6.QtWidgets import QStyleOption, QStyle
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)
        painter.end()


class RoundAvatar(QWidget):
    """Round avatar icon for chat messages."""

    SIZE = 36

    def __init__(self, role: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._role = role
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setObjectName(f"chatAvatar_{role}")

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = QRectF(1, 1, self.SIZE - 2, self.SIZE - 2)

        if self._role == MessageRole.ASSISTANT:
            from src.config.constants import AppConstants
            logo_path = AppConstants.LOGO_PATH
            if logo_path and Path(logo_path).exists():
                pixmap = QPixmap(str(logo_path))
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        self.SIZE - 4, self.SIZE - 4,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    from PySide6.QtGui import QRegion
                    from PySide6.QtCore import QRect
                    painter.setClipRegion(QRegion(rect.toRect(), QRegion.RegionType.Ellipse))
                    painter.drawPixmap(2, 2, scaled)
                    painter.setClipRegion(QRegion())
                    painter.end()
                    return

            painter.setBrush(QBrush(QColor("#89DCEB")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(rect)
            painter.setPen(QPen(QColor("#1E1E2E")))
            font = QFont()
            font.setPointSize(8)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "AI")
        else:
            painter.setBrush(QBrush(QColor("#89B4FA")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(rect)
            painter.setPen(QPen(QColor("#1E1E2E")))
            font = QFont()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "U")

        painter.end()


class MarkdownBrowser(QTextBrowser):
    """QTextBrowser that renders markdown as HTML and auto-sizes to content."""

    def __init__(self, html_content: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("markdownBrowser")
        self.setOpenExternalLinks(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.setStyleSheet(
            "QTextBrowser { background: transparent; border: none; }"
        )

        self.setHtml(html_content)
        self.document().setDocumentMargin(4)
        self.document().contentsChanged.connect(self._on_document_changed)
        QTimer.singleShot(0, self._sync_layout)
        QTimer.singleShot(50, self._sync_layout)

    def _on_document_changed(self) -> None:
        self._sync_layout()

    def _sync_layout(self) -> None:
        """QTextDocument needs an explicit width to wrap paragraphs and size correctly."""
        w = self.viewport().width()
        if w < 80:
            if self.parent():
                pw = self.parent().width()
                if pw > 80:
                    w = max(80, pw - 80)
            if w < 80:
                w = 400
        self.document().setTextWidth(w)
        self._adjust_height()

    def _adjust_height(self) -> None:
        doc_height = int(self.document().size().height()) + 8
        doc_height = max(doc_height, 24)
        self.setMinimumHeight(doc_height)
        self.setMaximumHeight(doc_height)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._sync_layout)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_layout()


class MessageBubble(QFrame):
    """
    Visual chat message bubble.

    User messages align right, AI messages align left.
    System messages are centered and styled differently.
    AI messages render markdown with syntax highlighting.
    """

    def __init__(self, message: ChatMessage, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._message = message
        self.setObjectName(f"messageBubble_{message.role}")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._build_ui()

    def _build_ui(self) -> None:
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 4, 0, 4)

        is_user = self._message.role == MessageRole.USER
        is_system = self._message.role == MessageRole.SYSTEM
        is_assistant = self._message.role == MessageRole.ASSISTANT

        if is_user:
            outer_layout.addStretch(1)
        elif not is_system:
            avatar = RoundAvatar(MessageRole.ASSISTANT, self)
            outer_layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)

        bubble = StyledBubbleFrame()
        bubble.setObjectName(f"bubble_{self._message.role}")
        bubble.setMaximumWidth(680)
        bubble.setMinimumWidth(180)
        bubble.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(14, 10, 14, 8)
        bubble_layout.setSpacing(4)

        if not is_user and not is_system:
            role_label = QLabel("OP(AI)UM")
            role_label.setObjectName("bubbleRole")
            role_font = QFont()
            role_font.setPointSize(8)
            role_font.setBold(True)
            role_label.setFont(role_font)
            bubble_layout.addWidget(role_label)

        # Render content: markdown for assistant, plain text for others
        if is_assistant:
            from src.utils.markdown_renderer import markdown_to_html
            html_content = markdown_to_html(self._message.content)
            content_widget = MarkdownBrowser(html_content)
            content_widget.setObjectName(f"bubbleContent_{self._message.role}")
            content_font = QFont()
            content_font.setPointSize(10)
            content_widget.setFont(content_font)
            bubble_layout.addWidget(content_widget)
        else:
            content_label = QLabel(self._message.content)
            content_label.setObjectName(f"bubbleContent_{self._message.role}")
            content_label.setWordWrap(True)
            content_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            content_label.setMinimumWidth(60)
            content_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            content_font = QFont()
            content_font.setPointSize(10)
            content_label.setFont(content_font)
            bubble_layout.addWidget(content_label)

        # Timestamp
        time_str = self._message.timestamp.strftime("%H:%M")
        time_label = QLabel(time_str)
        time_label.setObjectName(f"bubbleTime_{self._message.role}")
        time_font = QFont()
        time_font.setPointSize(7)
        time_label.setFont(time_font)
        if is_user:
            time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        bubble_layout.addWidget(time_label)

        outer_layout.addWidget(bubble, 1)

        if is_user:
            avatar = RoundAvatar(MessageRole.USER, self)
            outer_layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)
            outer_layout.addSpacing(8)
        elif not is_system:
            outer_layout.addStretch(1)

    @property
    def message(self) -> ChatMessage:
        return self._message
