"""
OP(AI)UM — Chat Input Bar

Text input with send button and microphone toggle for
speech-to-text input. Supports multiline and keyboard shortcuts.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QWidget,
)


class ChatInputBar(QWidget):
    """
    Chat message input bar.

    Signals:
        message_sent(str): User sends a message.
        mic_toggled(bool): Microphone recording toggled.
    """

    message_sent = Signal(str)
    mic_toggled = Signal(bool)

    MAX_HEIGHT = 120
    MIN_HEIGHT = 42

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mic_active = False
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        # Mic button
        self._mic_btn = QPushButton("🎤")
        self._mic_btn.setObjectName("micButton")
        self._mic_btn.setFixedSize(42, 42)
        self._mic_btn.setCheckable(True)
        self._mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mic_btn.setToolTip("Toggle voice input")
        mic_font = QFont()
        mic_font.setPointSize(14)
        self._mic_btn.setFont(mic_font)
        layout.addWidget(self._mic_btn)

        # Text input
        self._text_input = ChatTextEdit()
        self._text_input.setObjectName("chatInput")
        self._text_input.setPlaceholderText("Ask OP(AI)UM anything about your files...")
        self._text_input.setMinimumHeight(self.MIN_HEIGHT)
        self._text_input.setMaximumHeight(self.MAX_HEIGHT)
        input_font = QFont()
        input_font.setPointSize(10)
        self._text_input.setFont(input_font)
        self._text_input.setAcceptRichText(False)
        layout.addWidget(self._text_input, stretch=1)

        # Send button
        self._send_btn = QPushButton("Send")
        self._send_btn.setObjectName("sendButton")
        self._send_btn.setFixedHeight(42)
        self._send_btn.setMinimumWidth(70)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_font = QFont()
        send_font.setPointSize(10)
        send_font.setBold(True)
        self._send_btn.setFont(send_font)
        layout.addWidget(self._send_btn)

    def _connect_signals(self) -> None:
        self._send_btn.clicked.connect(self._on_send)
        self._text_input.enter_pressed.connect(self._on_send)
        self._mic_btn.toggled.connect(self._on_mic_toggled)

    def _on_send(self) -> None:
        """Send the current text."""
        text = self._text_input.toPlainText().strip()
        if text:
            self.message_sent.emit(text)
            self._text_input.clear()

    def _on_mic_toggled(self, checked: bool) -> None:
        self._mic_active = checked
        if checked:
            self._mic_btn.setObjectName("micButtonActive")
            self._mic_btn.setToolTip("Recording... Click to stop")
        else:
            self._mic_btn.setObjectName("micButton")
            self._mic_btn.setToolTip("Toggle voice input")
        # Force style refresh
        self._mic_btn.style().unpolish(self._mic_btn)
        self._mic_btn.style().polish(self._mic_btn)
        self.mic_toggled.emit(checked)

    def set_text(self, text: str) -> None:
        """Set the input text (e.g., from speech transcription)."""
        self._text_input.setPlainText(text)
        # Move cursor to end
        cursor = self._text_input.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._text_input.setTextCursor(cursor)

    def append_text(self, text: str) -> None:
        """Append text to existing input."""
        current = self._text_input.toPlainText()
        if current:
            self._text_input.setPlainText(current + " " + text)
        else:
            self._text_input.setPlainText(text)

    def set_enabled(self, enabled: bool) -> None:
        """Enable/disable the entire input bar."""
        self._text_input.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)
        self._mic_btn.setEnabled(enabled)

    def set_mic_state(self, active: bool) -> None:
        """Set microphone state without triggering signal."""
        self._mic_btn.blockSignals(True)
        self._mic_btn.setChecked(active)
        self._mic_active = active
        self._mic_btn.blockSignals(False)

    def focus_input(self) -> None:
        self._text_input.setFocus()


class ChatTextEdit(QTextEdit):
    """
    Custom text edit that sends on Enter (Shift+Enter for newline).
    """

    enter_pressed = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Shift+Enter: newline
                super().keyPressEvent(event)
            else:
                # Enter: send
                self.enter_pressed.emit()
        else:
            super().keyPressEvent(event)
