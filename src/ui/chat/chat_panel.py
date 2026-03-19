"""
OP(AI)UM — Chat Panel

Main AI chat interface combining:
- Conversations sidebar (left)
- Message list with markdown rendering (center)
- Input bar, quick actions, typing indicator (bottom)
- Auto-save conversation history to SQLite
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.ai.ai_engine import AIEngine
from src.ai.conversation_db import ConversationDB
from src.ai.conversation_manager import ConversationManager
from src.ai.speech_recorder import SpeechRecorder
from src.ai.speech_transcriber import SpeechTranscriber
from src.config.config_manager import ConfigManager
from src.ui.chat.chat_input import ChatInputBar
from src.ui.chat.context_card import ChatContextCard
from src.ui.chat.conversations_sidebar import ConversationsSidebar
from src.ui.chat.message_bubble import ChatMessage, MessageBubble, MessageRole
from src.ui.chat.quick_actions import QuickActionChips
from src.ui.chat.typing_indicator import TypingIndicator
from src.undo.operation_journal import OperationJournal
from src.undo.undo_manager import UndoManager


class ChatPanel(QWidget):
    """
    Main AI chat interface with conversation sidebar.

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
        self._conversation_db = ConversationDB()
        self._ai_engine: AIEngine | None = None
        self._speech_recorder: SpeechRecorder | None = None
        self._speech_transcriber: SpeechTranscriber | None = None
        self._pending_context: str = ""
        self._current_folder: str = ""
        self._current_conversation_id: int | None = None

        self._build_ui()
        self._connect_signals()
        self._initialize_ai()
        self._sidebar.refresh()

    def _build_ui(self) -> None:
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Conversations sidebar (left)
        self._sidebar = ConversationsSidebar(self._conversation_db)
        outer_layout.addWidget(self._sidebar)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setObjectName("convSeparator")
        outer_layout.addWidget(sep)

        # Chat area (right)
        chat_widget = QWidget()
        layout = QVBoxLayout(chat_widget)
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

        # Message scroll area — widgetResizable for proper sizing
        scroll = QScrollArea()
        scroll.setObjectName("chatScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll = scroll

        self._message_container = QWidget()
        self._message_layout = QVBoxLayout(self._message_container)
        self._message_layout.setContentsMargins(16, 8, 16, 8)
        self._message_layout.setSpacing(4)
        self._message_layout.addStretch()

        scroll.setWidget(self._message_container)
        layout.addWidget(scroll, stretch=1)

        # Typing indicator
        self._typing = TypingIndicator()
        layout.addWidget(self._typing)

        # Quick action chips
        self._quick_actions = QuickActionChips()
        layout.addWidget(self._quick_actions)

        # Input bar
        self._input_bar = ChatInputBar()
        layout.addWidget(self._input_bar)

        outer_layout.addWidget(chat_widget, stretch=1)

        # Welcome message
        self._add_system_message(
            "Welcome to OP(AI)UM! I can help you manage your files. "
            "Try asking me to count, organize, rename, or find files."
        )

    def _connect_signals(self) -> None:
        self._input_bar.message_sent.connect(self._on_user_message)
        self._input_bar.mic_toggled.connect(self._on_mic_toggled)
        self._quick_actions.chip_clicked.connect(self._on_user_message)
        self._sidebar.conversation_selected.connect(self._on_conversation_selected)
        self._sidebar.new_chat_requested.connect(lambda: self._start_new_chat())

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
                self._add_system_message("AI engine could not be initialized. Check your API key in Settings.")
        else:
            self._add_system_message(
                "No API key configured. Please add your OpenAI API key in Settings to enable AI features."
            )

    # === Message Handling ===

    def _on_user_message(self, text: str) -> None:
        """Handle user sending a message."""
        # Auto-create conversation if none active
        if self._current_conversation_id is None:
            title = text.strip()
            if title.startswith("[Working in:"):
                lines = title.split("\n", 1)
                title = lines[1] if len(lines) > 1 else lines[0]
            title = title.strip()[:60] or "New Conversation"
            self._current_conversation_id = self._conversation_db.create_conversation(
                title=title,
                folder_path=self._current_folder,
            )
            self._sidebar.refresh()
            self._sidebar.set_current_conversation(self._current_conversation_id)

        self._add_message(MessageRole.USER, text)
        self._save_message("user", text)

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
        """Handle AI response - skip if it's an error (handled by _on_ai_error)."""
        try:
            if parsed_response.is_error:
                return

            if parsed_response.text:
                self._add_message(MessageRole.ASSISTANT, parsed_response.text)
                self._save_message("assistant", parsed_response.text)
            self._scroll_to_bottom()
        except Exception as e:
            logger.error(f"Error in _on_ai_response handler: {e}")

    def _on_tool_executing(self, tool_name: str) -> None:
        self._add_system_message(f"Executing: {tool_name}...")

    def _on_approval_needed(self, description: str, plan_steps: list) -> None:
        plan_text = "\n".join(f"  {i + 1}. {step}" for i, step in enumerate(plan_steps))
        message = f"{description}\n\nPlan:\n{plan_text}\n\nType 'yes' to proceed or 'no' to cancel."
        self._add_system_message(message)

    def _on_ai_error(self, error: str) -> None:
        """Handle AI errors without clearing the chat."""
        try:
            self._typing.stop()
            self._input_bar.set_enabled(True)
            logger.error(f"AI error: {error}")

            if "context_length_exceeded" in error or "tokens" in error.lower():
                friendly_error = (
                    "The conversation is too long for the AI to process. "
                    "Please start a new chat or ask a simpler question."
                )
            elif "api_key" in error.lower() or "authentication" in error.lower():
                friendly_error = "API key is invalid or expired. Please update it in Settings."
            elif "rate_limit" in error.lower():
                friendly_error = "Rate limit reached. Please wait a moment and try again."
            elif "timeout" in error.lower():
                friendly_error = "Request timed out. The operation may be too complex."
            else:
                friendly_error = f"Error: {error}"

            self._add_system_message(friendly_error)
        except Exception as e:
            logger.error(f"Error in _on_ai_error handler: {e}")

    # === Speech ===

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

    # === UI Helpers ===

    def _add_message(self, role: str, content: str) -> None:
        """Add a chat message bubble."""
        try:
            if not content:
                return
            msg = ChatMessage(role=role, content=content)
            bubble = MessageBubble(msg)
            # Insert before the stretch at the end
            count = self._message_layout.count()
            self._message_layout.insertWidget(count - 1, bubble)
            self._scroll_to_bottom()
        except Exception as e:
            logger.error(f"Error adding message to chat: {e}")

    def _add_system_message(self, content: str) -> None:
        self._add_message(MessageRole.SYSTEM, content)

    def _add_context_card(self, path: str) -> None:
        """Add a compact context card showing the file/folder being asked about."""
        card = ChatContextCard(path)
        count = self._message_layout.count()
        self._message_layout.insertWidget(count - 1, card)

    def _scroll_to_bottom(self) -> None:
        """Scroll chat to the bottom after layout updates."""
        QTimer.singleShot(
            50,
            lambda: self._scroll.verticalScrollBar().setValue(self._scroll.verticalScrollBar().maximum()),
        )

    def _clear_chat(self) -> None:
        """Clear all messages from the chat UI."""
        while self._message_layout.count() > 1:  # Keep the stretch
            item = self._message_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    # === Conversation Management ===

    def _save_message(self, role: str, content: str) -> None:
        """Persist a message to the conversation database."""
        if self._current_conversation_id is not None:
            try:
                self._conversation_db.add_message(self._current_conversation_id, role, content)
            except Exception as e:
                logger.error(f"Failed to save message: {e}")

    def _on_conversation_selected(self, conv_id: int) -> None:
        """Load a conversation from the database."""
        self._clear_chat()
        self._current_conversation_id = conv_id
        self._sidebar.set_current_conversation(conv_id)

        # Reset AI conversation memory
        if self._ai_engine:
            self._ai_engine._conversation.clear()
            self._ai_engine._update_system_prompt()

        # Load messages from DB
        messages = self._conversation_db.get_messages(conv_id)
        for msg in messages:
            if msg.role in ("user", "assistant"):
                self._add_message(
                    MessageRole.USER if msg.role == "user" else MessageRole.ASSISTANT,
                    msg.content,
                )
                # Re-populate AI conversation memory for context
                if self._ai_engine:
                    if msg.role == "user":
                        self._ai_engine._conversation.add_user_message(msg.content)
                    else:
                        self._ai_engine._conversation.add_assistant_message(msg.content)

        # Restore folder context
        conversations = self._conversation_db.get_conversations()
        for conv in conversations:
            if conv.id == conv_id and conv.folder_path:
                self._current_folder = conv.folder_path
                self._quick_actions.set_current_folder(conv.folder_path)
                if self._ai_engine:
                    self._ai_engine.set_selected_folder(conv.folder_path)
                break

        self._scroll_to_bottom()

    def _start_new_chat(self, context_msg: str | None = None) -> None:
        """Start a fresh chat conversation."""
        self._clear_chat()
        self._current_conversation_id = None

        if self._ai_engine:
            self._ai_engine._conversation.clear()
            self._ai_engine._update_system_prompt()

        self._sidebar.set_current_conversation(None)

        if context_msg:
            self._add_system_message(context_msg)
        else:
            self._add_system_message("New conversation started. How can I help?")

    def set_folder_context(self, folder_path: str) -> None:
        """Update the folder context for AI. If a new folder, start new chat."""
        if folder_path != self._current_folder and self._current_folder:
            folder_name = Path(folder_path).name if folder_path else "folder"
            self._start_new_chat(f"Switched context to: {folder_name}. How can I help with this folder?")

        self._current_folder = folder_path
        self._pending_context = folder_path
        self._quick_actions.set_current_folder(folder_path)
        if self._ai_engine:
            self._ai_engine.set_selected_folder(folder_path)

        # Update current conversation's folder
        if self._current_conversation_id is not None:
            self._conversation_db.update_conversation(self._current_conversation_id, folder_path=folder_path)

    def inject_ai_question(self, question: str, path: str) -> None:
        """Inject a question from the context menu with context card."""
        if path != self._current_folder and self._current_folder:
            self._start_new_chat()

        self._current_folder = path
        self._pending_context = path

        if self._ai_engine:
            self._ai_engine.set_selected_folder(path)

        self._add_context_card(path)
        self._on_user_message(question)

    def focus_input(self) -> None:
        self._input_bar.focus_input()
