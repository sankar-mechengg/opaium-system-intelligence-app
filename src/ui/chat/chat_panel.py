"""
OP(AI)UM — Chat Panel

Main AI chat interface combining message list, input bar,
quick actions, and typing indicator. Orchestrates communication
with the AI engine and handles tool approvals.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QFrame, QLabel, QDialog,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont
from loguru import logger

from src.ai.ai_engine import AIEngine
from src.ai.conversation_manager import ConversationManager
from src.ai.speech_recorder import SpeechRecorder
from src.ai.speech_transcriber import SpeechTranscriber
from src.config.config_manager import ConfigManager
from src.ui.chat.message_bubble import ChatMessage, MessageBubble, MessageRole
from src.ui.chat.chat_input import ChatInputBar
from src.ui.chat.typing_indicator import TypingIndicator
from src.ui.chat.quick_actions import QuickActionChips
from src.ui.chat.tool_result_widget import ToolResultWidget
from src.ui.chat.approval_dialog import ApprovalDialog
from src.ui.chat.context_card import ChatContextCard
from src.undo.undo_manager import UndoManager
from src.undo.operation_journal import OperationJournal
from src.utils.thread_pool import Worker, ThreadPoolManager


class ChatPanel(QWidget):
    """
    Main AI chat interface.

    Signals:
        operation_completed(): An AI operation finished (refresh explorer).
        undo_requested(int): User wants to undo an operation.
    """

    operation_completed = Signal()
    undo_requested = Signal(int)

    def __init__(
        self,
        config: ConfigManager,
        undo_manager: UndoManager,
        operation_journal: OperationJournal,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._undo_manager = undo_manager
        self._operation_journal = operation_journal
        self._conversation = ConversationManager()
        self._ai_engine: Optional[AIEngine] = None
        self._speech_recorder: Optional[SpeechRecorder] = None
        self._speech_transcriber: Optional[SpeechTranscriber] = None
        self._pending_context: str = ""
        self._current_folder: str = ""

        self._build_ui()
        self._connect_signals()
        self._initialize_ai()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Chat header
        header = QLabel("  AI Assistant")
        header.setObjectName("chatHeader")
        header_font = QFont()
        header_font.setPointSize(10)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setFixedHeight(36)
        layout.addWidget(header)

        # Message scroll area — sized to content to avoid empty space below messages
        scroll = QScrollArea()
        scroll.setObjectName("chatScroll")
        scroll.setWidgetResizable(False)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMinimumHeight(80)
        self._scroll = scroll

        self._message_container = QWidget()
        self._message_container.setMinimumWidth(400)
        self._message_layout = QVBoxLayout(self._message_container)
        self._message_layout.setContentsMargins(16, 8, 16, 8)
        self._message_layout.setSpacing(4)
        self._message_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self._message_container)
        layout.addWidget(scroll)
        layout.addStretch(1)  # Takes extra space so scroll stays content-sized, input at bottom

        # Typing indicator
        self._typing = TypingIndicator()
        layout.addWidget(self._typing)

        # Quick action chips
        self._quick_actions = QuickActionChips()
        layout.addWidget(self._quick_actions)

        # Input bar
        self._input_bar = ChatInputBar()
        layout.addWidget(self._input_bar)

        # Welcome message
        self._add_system_message(
            "Welcome to OP(AI)UM! I can help you manage your files. "
            "Try asking me to count, organize, rename, or find files."
        )

    def _connect_signals(self) -> None:
        self._input_bar.message_sent.connect(self._on_user_message)
        self._input_bar.mic_toggled.connect(self._on_mic_toggled)
        self._quick_actions.chip_clicked.connect(self._on_user_message)

    def _initialize_ai(self) -> None:
        """Initialize the AI engine if API key is available."""
        api_key = self._config.get_api_key()
        if api_key:
            try:
                self._ai_engine = AIEngine(
                    config=self._config,
                    operation_journal=self._operation_journal,
                    parent=self,
                )
                self._ai_engine.response_ready.connect(self._on_ai_response)
                self._ai_engine.error.connect(self._on_ai_error)
                self._ai_engine.thinking_started.connect(self._on_thinking_started)
                self._ai_engine.thinking_finished.connect(self._on_thinking_finished)
                self._ai_engine.tool_executing.connect(self._on_tool_executing)
                self._ai_engine.approval_needed.connect(self._on_approval_needed)
                self._ai_engine.initialize()
                logger.info("AI engine initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize AI engine: {e}")
                self._add_system_message(
                    "AI engine could not be initialized. Check your API key in Settings."
                )
        else:
            self._add_system_message(
                "No API key configured. Please add your OpenAI API key in Settings to enable AI features."
            )

    def _on_user_message(self, text: str) -> None:
        """Handle user sending a message."""
        self._add_message(MessageRole.USER, text)

        if self._ai_engine:
            self._ai_engine.send_message(text)
        else:
            self._add_system_message("AI is not available. Please configure your API key.")

    def _on_thinking_started(self) -> None:
        self._input_bar.set_enabled(False)
        self._typing.start()

    def _on_thinking_finished(self) -> None:
        self._typing.stop()
        self._input_bar.set_enabled(True)

    def _on_ai_response(self, parsed_response) -> None:
        if parsed_response.text:
            self._add_message(MessageRole.ASSISTANT, parsed_response.text)
        self._scroll_to_bottom()

    def _on_tool_executing(self, tool_name: str) -> None:
        self._add_system_message(f"Executing: {tool_name}...")

    def _on_approval_needed(self, description: str, plan_steps: list) -> None:
        plan_text = "\n".join(f"  {i+1}. {step}" for i, step in enumerate(plan_steps))
        message = f"{description}\n\nPlan:\n{plan_text}\n\nType 'yes' to proceed or 'no' to cancel."
        self._add_system_message(message)

    def _on_ai_error(self, error: str) -> None:
        self._typing.stop()
        self._input_bar.set_enabled(True)
        logger.error(f"AI error: {error}")
        self._add_system_message(f"Error: {error}")

    def _on_mic_toggled(self, active: bool) -> None:
        if active:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self) -> None:
        try:
            if self._speech_recorder is None:
                self._speech_recorder = SpeechRecorder()
            self._speech_recorder.start_recording()
            self._add_system_message("Recording... Click the mic to stop.")
        except Exception as e:
            logger.error(f"Recording error: {e}")
            self._input_bar.set_mic_state(False)
            self._add_system_message(f"Could not start recording: {e}")

    def _stop_recording(self) -> None:
        if self._speech_recorder:
            audio_data = self._speech_recorder.stop_recording()
            if audio_data:
                self._transcribe_audio(audio_data)

    def _transcribe_audio(self, audio_data) -> None:
        api_key = self._config.get_api_key()
        if not api_key:
            self._add_system_message("API key required for speech transcription.")
            return

        if self._speech_transcriber is None:
            self._speech_transcriber = SpeechTranscriber(api_key)
            self._speech_transcriber.transcription_ready.connect(self._on_transcription)
            self._speech_transcriber.transcription_error.connect(
                lambda e: self._add_system_message(f"Transcription error: {e}")
            )

        self._speech_transcriber.transcribe(audio_data)

    def _on_transcription(self, text: str) -> None:
        if text.strip():
            self._input_bar.set_text(text)

    def _add_message(self, role: str, content: str) -> None:
        """Add a chat message bubble."""
        msg = ChatMessage(role=role, content=content)
        bubble = MessageBubble(msg)
        self._message_layout.addWidget(bubble)
        self._update_scroll_content_size()
        self._scroll_to_bottom()

    def _add_system_message(self, content: str) -> None:
        self._add_message(MessageRole.SYSTEM, content)

    def _add_context_card(self, path: str) -> None:
        """Add a compact context card showing the file/folder being asked about."""
        card = ChatContextCard(path)
        self._message_layout.addWidget(card)
        self._update_scroll_content_size()

    def _update_scroll_content_size(self) -> None:
        """Size the message container and scroll area to fit content (removes empty space below messages)."""
        def _do_update():
            h = self._message_layout.sizeHint().height()
            h = max(h, 1)
            self._message_container.setFixedHeight(h)
            vp = self._scroll.viewport()
            if vp and vp.width() > 0:
                self._message_container.setMinimumWidth(vp.width())
                self._message_container.setMaximumWidth(vp.width())
            avail = max(self.height() - 180, 200)
            scroll_h = min(h, avail)
            self._scroll.setMinimumHeight(scroll_h)
            self._scroll.setMaximumHeight(scroll_h)
        QTimer.singleShot(0, _do_update)

    def _scroll_to_bottom(self) -> None:
        """Scroll chat to the bottom after layout updates."""
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    def _clear_chat(self) -> None:
        """Clear all messages from the chat."""
        while self._message_layout.count() > 0:
            item = self._message_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._update_scroll_content_size()

    def _start_new_chat(self, context_msg: str | None = None) -> None:
        """Start a fresh chat conversation."""
        self._clear_chat()

        # Reset conversation in AI engine
        if self._ai_engine:
            self._ai_engine._conversation.clear()
            self._ai_engine._update_system_prompt()

        if context_msg:
            self._add_system_message(context_msg)
        else:
            self._add_system_message(
                "New conversation started. How can I help?"
            )

    def set_folder_context(self, folder_path: str) -> None:
        """Update the folder context for AI. If a new folder, start new chat."""
        if folder_path != self._current_folder and self._current_folder:
            folder_name = Path(folder_path).name if folder_path else "folder"
            self._start_new_chat(
                f"Switched context to: {folder_name}. How can I help with this folder?"
            )

        self._current_folder = folder_path
        self._pending_context = folder_path
        self._quick_actions.set_current_folder(folder_path)
        if self._ai_engine:
            self._ai_engine.set_selected_folder(folder_path)

    def inject_ai_question(self, question: str, path: str) -> None:
        """Inject a question from the context menu with context card."""
        # If different folder/file, start new chat
        if path != self._current_folder and self._current_folder:
            self._start_new_chat()

        self._current_folder = path
        self._pending_context = path

        if self._ai_engine:
            self._ai_engine.set_selected_folder(path)

        # Show the context card above the user message
        self._add_context_card(path)

        # Send the question
        self._on_user_message(question)

    def focus_input(self) -> None:
        self._input_bar.focus_input()

    def resizeEvent(self, event) -> None:
        """Update scroll area size when panel is resized."""
        super().resizeEvent(event)
        self._update_scroll_content_size()
