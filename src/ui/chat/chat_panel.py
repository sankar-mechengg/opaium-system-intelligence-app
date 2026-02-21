"""
OP(AI)UM — Chat Panel

Main AI chat interface combining message list, input bar,
quick actions, and typing indicator. Orchestrates communication
with the AI engine and handles tool approvals.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QFrame, QLabel, QDialog,
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
from src.undo.undo_manager import UndoManager
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
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._undo_manager = undo_manager
        self._conversation = ConversationManager()
        self._ai_engine: Optional[AIEngine] = None
        self._speech_recorder: Optional[SpeechRecorder] = None
        self._speech_transcriber: Optional[SpeechTranscriber] = None
        self._pending_context: str = ""  # Selected folder context

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

        # Message scroll area
        scroll = QScrollArea()
        scroll.setObjectName("chatScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll = scroll

        self._message_container = QWidget()
        self._message_layout = QVBoxLayout(self._message_container)
        self._message_layout.setContentsMargins(4, 8, 4, 8)
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
                    api_key=api_key,
                    model=self._config.settings.ai.model,
                )
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
        # Add to UI
        self._add_message(MessageRole.USER, text)

        # Add context if a folder is selected
        context = ""
        if self._pending_context:
            context = f"[Context: Currently selected folder is '{self._pending_context}']"

        # Add to conversation
        full_text = f"{context}\n{text}" if context else text
        self._conversation.add_user_message(full_text)

        # Send to AI
        if self._ai_engine:
            self._input_bar.set_enabled(False)
            self._typing.start()

            worker = Worker(self._get_ai_response, text)
            worker.signals.result.connect(self._on_ai_response)
            worker.signals.error.connect(self._on_ai_error)
            ThreadPoolManager.run(worker)
        else:
            self._add_system_message("AI is not available. Please configure your API key.")

    def _get_ai_response(self, user_text: str) -> dict:
        """Background: get AI response."""
        messages = self._conversation.get_messages()
        response = self._ai_engine.chat(messages)
        return response

    def _on_ai_response(self, response: dict) -> None:
        """Handle AI response on the main thread."""
        self._typing.stop()
        self._input_bar.set_enabled(True)

        if not response:
            self._add_system_message("AI returned an empty response. Please try again.")
            return

        # Handle text response
        text_content = response.get("text", "")
        if text_content:
            self._add_message(MessageRole.ASSISTANT, text_content)
            self._conversation.add_assistant_message(text_content)

        # Handle tool calls
        tool_calls = response.get("tool_calls", [])
        for tool_call in tool_calls:
            self._handle_tool_call(tool_call)

        self._scroll_to_bottom()

    def _handle_tool_call(self, tool_call: dict) -> None:
        """Process an AI tool call — preview, approve, execute."""
        tool_name = tool_call.get("name", "")
        args = tool_call.get("arguments", {})

        if not self._ai_engine:
            return

        # Get the tool
        tool = self._ai_engine.get_tool(tool_name)
        if not tool:
            self._add_system_message(f"Unknown tool: {tool_name}")
            return

        if tool.is_destructive:
            # Preview first
            preview_result = tool.preview(**args)

            if preview_result.requires_approval:
                dialog = ApprovalDialog(tool_name, preview_result, self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    # User approved — execute
                    result = tool.execute(**args)
                    self._display_tool_result(tool_name, result)
                else:
                    self._add_system_message(f"Operation '{tool_name}' was cancelled.")
                    return
            else:
                result = tool.execute(**args)
                self._display_tool_result(tool_name, result)
        else:
            # Non-destructive: execute immediately
            result = tool.execute(**args)
            self._display_tool_result(tool_name, result)

    def _display_tool_result(self, tool_name: str, result) -> None:
        """Display tool result in the chat."""
        operation_id = None

        # Save to undo journal if applicable
        if result.operation:
            operation_id = self._undo_manager.record_operation(result.operation)

        widget = ToolResultWidget(tool_name, result, operation_id)
        widget.undo_requested.connect(self.undo_requested.emit)

        # Insert before the stretch
        self._message_layout.insertWidget(
            self._message_layout.count() - 1, widget
        )

        if result.success and result.operation:
            self.operation_completed.emit()

    def _on_ai_error(self, error: str) -> None:
        self._typing.stop()
        self._input_bar.set_enabled(True)
        logger.error(f"AI error: {error}")
        self._add_system_message(f"Error: {error}")

    def _on_mic_toggled(self, active: bool) -> None:
        """Handle microphone toggle."""
        if active:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self) -> None:
        """Start speech recording."""
        try:
            if self._speech_recorder is None:
                self._speech_recorder = SpeechRecorder()
            self._speech_recorder.start_recording()
            self._add_system_message("🎤 Recording... Click the mic to stop.")
        except Exception as e:
            logger.error(f"Recording error: {e}")
            self._input_bar.set_mic_state(False)
            self._add_system_message(f"Could not start recording: {e}")

    def _stop_recording(self) -> None:
        """Stop recording and transcribe."""
        if self._speech_recorder:
            audio_data = self._speech_recorder.stop_recording()
            if audio_data:
                self._transcribe_audio(audio_data)

    def _transcribe_audio(self, audio_data) -> None:
        """Send audio to transcription service."""
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
        """Handle transcribed text."""
        if text.strip():
            self._input_bar.set_text(text)

    def _add_message(self, role: str, content: str) -> None:
        """Add a chat message bubble."""
        msg = ChatMessage(role=role, content=content)
        bubble = MessageBubble(msg)
        self._message_layout.insertWidget(
            self._message_layout.count() - 1, bubble
        )
        self._scroll_to_bottom()

    def _add_system_message(self, content: str) -> None:
        """Add a system/info message."""
        self._add_message(MessageRole.SYSTEM, content)

    def _scroll_to_bottom(self) -> None:
        """Scroll chat to the bottom."""
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    def set_folder_context(self, folder_path: str) -> None:
        """Update the folder context for AI and quick actions."""
        self._pending_context = folder_path
        self._quick_actions.set_current_folder(folder_path)

    def inject_ai_question(self, question: str, path: str) -> None:
        """Inject a question from the context menu."""
        self._pending_context = path
        self._on_user_message(question)

    def focus_input(self) -> None:
        self._input_bar.focus_input()
