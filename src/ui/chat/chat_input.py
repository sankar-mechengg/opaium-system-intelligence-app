"""
OP(AI)UM — Chat Input Bar

Auto-growing text input with Send / Stop, a microphone toggle that shows the
live input level while recording, Enter-to-send (Shift+Enter for newline)
and Up-arrow recall of the previous prompt.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTextEdit, QWidget

from src.ui.widgets.icon_button import IconButton


class ChatInputBar(QWidget):
    """
    Signals:
        message_sent(str): User sends a message.
        mic_toggled(bool): Microphone recording toggled.
        stop_requested(): User wants to stop the current generation.
    """

    message_sent = Signal(str)
    mic_toggled = Signal(bool)
    stop_requested = Signal()

    MAX_HEIGHT = 140
    MIN_HEIGHT = 44

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mic_active = False
        self._history: list[str] = []
        self._history_pos = -1
        self.setObjectName("chatInputBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(8)

        self._mic_btn = MicButton()
        layout.addWidget(self._mic_btn, alignment=Qt.AlignmentFlag.AlignBottom)

        self._text_input = ChatTextEdit()
        self._text_input.setObjectName("chatInput")
        self._text_input.setPlaceholderText(
            "Ask OP(AI)UM anything about your files…  (Enter to send, Shift+Enter for a new line)"
        )
        self._text_input.setMinimumHeight(self.MIN_HEIGHT)
        self._text_input.setMaximumHeight(self.MAX_HEIGHT)
        self._text_input.setAcceptRichText(False)
        self._text_input.setTabChangesFocus(True)
        layout.addWidget(self._text_input, stretch=1)

        self._send_btn = IconButton("send", "Send", role="accent_text", icon_size=16, object_name="sendButton")
        self._send_btn.setFixedHeight(44)
        self._send_btn.setMinimumWidth(92)
        layout.addWidget(self._send_btn, alignment=Qt.AlignmentFlag.AlignBottom)

        self._stop_btn = IconButton("stop", "Stop", role="red", icon_size=14, object_name="stopButton")
        self._stop_btn.setFixedHeight(44)
        self._stop_btn.setMinimumWidth(92)
        self._stop_btn.hide()
        layout.addWidget(self._stop_btn, alignment=Qt.AlignmentFlag.AlignBottom)

    def _connect_signals(self) -> None:
        self._send_btn.clicked.connect(self._on_send)
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        self._text_input.enter_pressed.connect(self._on_send)
        self._text_input.history_up.connect(self._recall_previous)
        self._text_input.textChanged.connect(self._auto_grow)
        self._mic_btn.toggled.connect(self._on_mic_toggled)

    # === Behaviour ===

    def _on_send(self) -> None:
        text = self._text_input.toPlainText().strip()
        if text:
            self._history.append(text)
            self._history_pos = len(self._history)
            self.message_sent.emit(text)
            self._text_input.clear()

    def _recall_previous(self) -> None:
        if not self._history:
            return
        self._history_pos = max(0, self._history_pos - 1)
        self.set_text(self._history[self._history_pos])

    def _auto_grow(self) -> None:
        doc_height = int(self._text_input.document().size().height()) + 14
        self._text_input.setFixedHeight(max(self.MIN_HEIGHT, min(self.MAX_HEIGHT, doc_height)))

    def _on_mic_toggled(self, checked: bool) -> None:
        self._mic_active = checked
        self.mic_toggled.emit(checked)

    def set_level(self, level: float) -> None:
        self._mic_btn.set_level(level)

    def set_text(self, text: str) -> None:
        self._text_input.setPlainText(text)
        cursor = self._text_input.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._text_input.setTextCursor(cursor)
        self._text_input.setFocus()

    def append_text(self, text: str) -> None:
        current = self._text_input.toPlainText()
        self.set_text((current + " " + text) if current else text)

    def set_busy(self, busy: bool) -> None:
        """While the AI is working: hide Send, show Stop, keep typing enabled."""
        self._send_btn.setVisible(not busy)
        self._stop_btn.setVisible(busy)
        self._mic_btn.setEnabled(not busy)

    def set_enabled(self, enabled: bool) -> None:
        self._text_input.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)
        self._mic_btn.setEnabled(enabled)

    def set_mic_state(self, active: bool) -> None:
        """Set microphone state without triggering the signal."""
        self._mic_btn.blockSignals(True)
        self._mic_btn.setChecked(active)
        self._mic_active = active
        self._mic_btn.blockSignals(False)
        self._mic_btn.set_level(0.0)

    def focus_input(self) -> None:
        self._text_input.setFocus()

    @property
    def text(self) -> str:
        return self._text_input.toPlainText()


class MicButton(QPushButton):
    """Round microphone toggle that paints a live level ring while recording."""

    SIZE = 44

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._level = 0.0
        self.setObjectName("micButton")
        self.setCheckable(True)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Voice input — click to start, click again to stop")
        self.toggled.connect(self._on_toggled)
        self._refresh_icon()

    def _on_toggled(self, checked: bool) -> None:
        self.setObjectName("micButtonActive" if checked else "micButton")
        self.setToolTip("Recording… click to stop" if checked else "Voice input — click to start, click again to stop")
        self.style().unpolish(self)
        self.style().polish(self)
        self._refresh_icon()

    def _refresh_icon(self) -> None:
        from src.utils.icon_provider import SvgIcons

        self.setIcon(SvgIcons.themed("mic", "red" if self.isChecked() else "text_sub", 18))
        self.setIconSize(QSize(18, 18))

    def set_level(self, level: float) -> None:
        self._level = max(0.0, min(1.0, level))
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        if not self.isChecked() or self._level <= 0.02:
            return
        from src.ui.theme import token

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(token("red"))
        color.setAlphaF(0.25 + 0.5 * self._level)
        pen = painter.pen()
        pen.setColor(color)
        pen.setWidthF(2.0 + 3.0 * self._level)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        inset = 3 + (1.0 - self._level) * 4
        painter.drawEllipse(QRectF(inset, inset, self.SIZE - 2 * inset, self.SIZE - 2 * inset))
        painter.end()


class ChatTextEdit(QTextEdit):
    """Text edit that sends on Enter (Shift+Enter for newline) and recalls history with Up."""

    enter_pressed = Signal()
    history_up = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.enter_pressed.emit()
            return
        if event.key() == Qt.Key.Key_Up and not self.toPlainText().strip():
            self.history_up.emit()
            return
        super().keyPressEvent(event)
