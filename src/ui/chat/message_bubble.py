"""
OP(AI)UM — Chat Message Bubble

Individual message widget for the chat view. Assistant bubbles render
markdown (with syntax-highlighted code) and support incremental streaming;
user and system bubbles are plain text. Every bubble offers a copy action.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QContextMenuEvent,
    QFont,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QRegion,
    QResizeEvent,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QStyle,
    QStyleOption,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


class MessageRole:
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage:
    """Data model for a chat message."""

    def __init__(self, role: str, content: str, timestamp: datetime | None = None) -> None:
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now()


class StyledBubbleFrame(QFrame):
    """QFrame subclass that properly paints QSS backgrounds and borders."""

    def paintEvent(self, event: QPaintEvent) -> None:
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, painter, self)
        painter.end()


class RoundAvatar(QWidget):
    """Round avatar icon for chat messages."""

    SIZE = 34

    def __init__(self, role: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._role = role
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setObjectName(f"chatAvatar_{role}")

    def paintEvent(self, event: QPaintEvent) -> None:
        from src.ui.theme import token

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
                        self.SIZE - 4,
                        self.SIZE - 4,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    painter.setClipRegion(QRegion(rect.toRect(), QRegion.RegionType.Ellipse))
                    painter.drawPixmap(2, 2, scaled)
                    painter.end()
                    return
            painter.setBrush(QBrush(QColor(token("teal"))))
            label = "AI"
        else:
            painter.setBrush(QBrush(QColor(token("accent"))))
            label = "You"[:1]

        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(rect)
        painter.setPen(QPen(QColor(token("accent_text"))))
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
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
        self.setStyleSheet("QTextBrowser { background: transparent; border: none; }")
        self.setHtml(html_content)
        self.document().setDocumentMargin(4)
        self.document().contentsChanged.connect(self._sync_layout)
        QTimer.singleShot(0, self._sync_layout)
        QTimer.singleShot(50, self._sync_layout)

    def set_html_keep_scroll(self, html_content: str) -> None:
        self.setHtml(html_content)
        self._sync_layout()

    def _sync_layout(self) -> None:
        """QTextDocument needs an explicit width to wrap paragraphs and size correctly."""
        w = self.viewport().width()
        if w < 80:
            parent_w = self.parentWidget()
            if parent_w is not None and parent_w.width() > 80:
                w = max(80, parent_w.width() - 80)
            if w < 80:
                w = 400
        self.document().setTextWidth(w)
        doc_height = int(self.document().size().height()) + 8
        doc_height = max(doc_height, 24)
        self.setMinimumHeight(doc_height)
        self.setMaximumHeight(doc_height)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._sync_layout)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._sync_layout()


class MessageBubble(QFrame):
    """
    Visual chat message bubble.

    User messages align right, AI messages align left, system messages are
    full-width notes. AI bubbles can be created empty and streamed into.
    """

    STREAM_RENDER_MS = 70

    def __init__(self, message: ChatMessage, parent: QWidget | None = None, streaming: bool = False) -> None:
        super().__init__(parent)
        self._message = message
        self._streaming = streaming
        self._content_widget: MarkdownBrowser | QLabel | None = None
        self._render_timer: QTimer | None = None
        self.setObjectName(f"messageBubble_{message.role}")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self._build_ui()

    # === Build ===

    def _build_ui(self) -> None:
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 4, 0, 4)
        outer_layout.setSpacing(8)

        is_user = self._message.role == MessageRole.USER
        is_system = self._message.role == MessageRole.SYSTEM
        is_assistant = self._message.role == MessageRole.ASSISTANT

        if is_user:
            outer_layout.addStretch(1)
        elif is_assistant:
            avatar = RoundAvatar(MessageRole.ASSISTANT, self)
            outer_layout.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)

        bubble = StyledBubbleFrame()
        bubble.setObjectName(f"bubble_{self._message.role}")
        bubble.setMaximumWidth(760 if not is_system else 900)
        bubble.setMinimumWidth(120)
        bubble.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(14, 10, 14, 8)
        bubble_layout.setSpacing(4)

        if is_assistant:
            role_label = QLabel("OP(AI)UM")
            role_label.setObjectName("bubbleRole")
            role_font = QFont()
            role_font.setPointSize(8)
            role_font.setBold(True)
            role_label.setFont(role_font)
            bubble_layout.addWidget(role_label)

        if is_assistant:
            from src.utils.markdown_renderer import markdown_to_html

            content_widget = MarkdownBrowser(
                markdown_to_html(self._message.content or ("…" if self._streaming else ""))
            )
            content_widget.setObjectName(f"bubbleContent_{self._message.role}")
            content_font = QFont()
            content_font.setPointSize(10)
            content_widget.setFont(content_font)
            bubble_layout.addWidget(content_widget)
            self._content_widget = content_widget
        else:
            content_label = QLabel(self._message.content)
            content_label.setObjectName(f"bubbleContent_{self._message.role}")
            content_label.setWordWrap(True)
            content_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse
            )
            content_label.setMinimumWidth(60)
            content_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            content_font = QFont()
            content_font.setPointSize(10 if not is_system else 9)
            content_label.setFont(content_font)
            bubble_layout.addWidget(content_label)
            self._content_widget = content_label

        time_label = QLabel(self._message.timestamp.strftime("%H:%M"))
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
        elif is_assistant:
            outer_layout.addStretch(1)

    # === Streaming ===

    def append_text(self, delta: str) -> None:
        """Append streamed text (assistant bubbles only) and re-render lazily."""
        self._message.content = (self._message.content or "") + delta
        if self._render_timer is None:
            self._render_timer = QTimer(self)
            self._render_timer.setSingleShot(True)
            self._render_timer.timeout.connect(self._render_now)
        if not self._render_timer.isActive():
            self._render_timer.start(self.STREAM_RENDER_MS)

    def set_content(self, text: str) -> None:
        """Replace the full content (used to finalize a streamed answer)."""
        self._message.content = text
        self._streaming = False
        if self._render_timer is not None:
            self._render_timer.stop()
        self._render_now()

    def _render_now(self) -> None:
        if isinstance(self._content_widget, MarkdownBrowser):
            from src.utils.markdown_renderer import markdown_to_html

            self._content_widget.set_html_keep_scroll(markdown_to_html(self._message.content or ""))
        elif isinstance(self._content_widget, QLabel):
            self._content_widget.setText(self._message.content)

    # === Misc ===

    @property
    def message(self) -> ChatMessage:
        return self._message

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = QMenu(self)
        menu.setObjectName("contextMenu")
        menu.addAction("Copy message", self._copy)
        menu.exec(event.globalPos())

    def _copy(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self._message.content or "")
