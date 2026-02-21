"""
OP(AI)UM — AI Engine

Main orchestrator for the AI system. Ties together:
- OpenAI client (chat + transcription)
- Function registry (tool definitions)
- Conversation manager (history)
- Speech recorder + transcriber
- Undo journal (operation recording)
- Prompt builder (system prompt + context)

This is the single entry point the UI chat widget talks to.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QObject, Signal
from loguru import logger

from src.ai.openai_client import OpenAIClient
from src.ai.function_registry import FunctionRegistry
from src.ai.tool_executor import ToolExecutorWithJournal
from src.ai.conversation_manager import ConversationManager, ChatMessage
from src.ai.prompt_builder import PromptBuilder
from src.ai.response_parser import ResponseParser, ParsedResponse
from src.ai.speech_recorder import SpeechRecorder
from src.ai.speech_transcriber import SpeechTranscriber
from src.config.config_manager import ConfigManager
from src.undo.operation_journal import OperationJournal


class AIEngine(QObject):
    """
    Central AI engine for OP(AI)UM.

    Signals:
        response_ready: Emitted when AI response is ready (ParsedResponse).
        tool_executing: Emitted when a tool is being executed (tool_name).
        approval_needed: Emitted when destructive op needs approval (plan text).
        thinking_started: Emitted when AI starts processing.
        thinking_finished: Emitted when AI finishes processing.
        speech_transcribed: Emitted when speech is transcribed (text).
        error: Emitted on errors (error message).
    """

    response_ready = Signal(object)      # ParsedResponse
    tool_executing = Signal(str)         # tool name
    approval_needed = Signal(str, list)  # description, plan steps
    thinking_started = Signal()
    thinking_finished = Signal()
    speech_transcribed = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        config: ConfigManager,
        operation_journal: OperationJournal,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._journal = operation_journal

        # Components
        self._client = OpenAIClient(config)
        self._registry = FunctionRegistry()
        self._conversation = ConversationManager()
        self._recorder = SpeechRecorder(self)
        self._transcriber = SpeechTranscriber(self._client, self)

        # State
        self._selected_folder: Optional[str] = None
        self._selected_files: list[str] = []
        self._scan_mode: str = "shallow"
        self._is_processing = False
        self._pending_approval_action: Optional[dict[str, Any]] = None

        # Connect speech signals
        self._recorder.transcription_ready.connect(self._on_recording_ready)
        self._recorder.error.connect(self.error.emit)
        self._transcriber.transcription_complete.connect(self._on_transcription_complete)
        self._transcriber.transcription_error.connect(self.error.emit)

    def initialize(self) -> None:
        """Initialize the AI engine — register tools and set system prompt."""
        self._registry.register_all_tools()
        self._update_system_prompt()
        logger.info(f"AI Engine initialized with {self._registry.tool_count} tools.")

    @property
    def is_configured(self) -> bool:
        return self._client.is_configured()

    @property
    def is_processing(self) -> bool:
        return self._is_processing

    @property
    def is_recording(self) -> bool:
        return self._recorder.is_recording

    @property
    def conversation(self) -> ConversationManager:
        return self._conversation

    @property
    def recorder(self) -> SpeechRecorder:
        return self._recorder

    def set_selected_folder(self, folder_path: Optional[str]) -> None:
        """Update the currently selected folder context."""
        self._selected_folder = folder_path
        self._update_system_prompt()

    def set_selected_files(self, file_paths: list[str]) -> None:
        """Update the currently selected files."""
        self._selected_files = file_paths

    def set_scan_mode(self, mode: str) -> None:
        """Set scan mode: 'shallow' or 'recursive'."""
        self._scan_mode = mode
        self._update_system_prompt()

    def send_message(self, text: str) -> None:
        """
        Send a user message to the AI.

        This is the main entry point from the chat UI.
        Runs the AI request in a background thread.
        """
        if self._is_processing:
            self.error.emit("AI is still processing the previous request.")
            return

        if not self.is_configured:
            self.error.emit("OpenAI API key not configured. Go to Settings.")
            return

        # Check if this is an approval response
        if self._pending_approval_action:
            self._handle_approval_response(text)
            return

        # Build enriched user message
        enriched = PromptBuilder.build_user_message(
            text,
            selected_folder=self._selected_folder,
            selected_files=self._selected_files,
        )
        self._conversation.add_user_message(enriched)

        # Process in background
        self._process_request()

    def _process_request(self) -> None:
        """Send the conversation to the AI and handle the response."""
        self._is_processing = True
        self.thinking_started.emit()

        from src.utils.thread_pool import Worker, ThreadPoolManager

        worker = Worker(self._execute_ai_request)
        worker.signals.result.connect(self._on_ai_response)
        worker.signals.error.connect(self._on_ai_error)
        worker.signals.finished.connect(self._on_processing_done)
        ThreadPoolManager.run(worker)

    def _execute_ai_request(self) -> dict[str, Any]:
        """Execute the AI request (runs in thread pool)."""
        messages = self._conversation.get_api_messages()
        tools = self._registry.get_all_schemas()
        tool_executor = ToolExecutorWithJournal(self._registry, self._journal)

        return self._client.chat_with_tool_loop(
            messages=messages,
            tools=tools,
            tool_executor=tool_executor,
            max_rounds=5,
        )

    def _on_ai_response(self, raw_response: object) -> None:
        """Handle AI response from the background thread."""
        response = dict(raw_response) if isinstance(raw_response, dict) else {"message": {"content": str(raw_response), "tool_calls": None}}
        parsed = ResponseParser.parse(response)

        # Add assistant message to conversation
        content = parsed.text or ""
        self._conversation.add_assistant_message(
            content=content,
            tool_calls=[tc._asdict() for tc in parsed.tool_calls] if parsed.tool_calls else None,
        )

        # Check if approval is needed
        if parsed.needs_approval:
            self._pending_approval_action = {
                "plan": parsed.approval_plan,
                "text": parsed.text,
            }
            self.approval_needed.emit(parsed.text, parsed.approval_plan)
        else:
            self._pending_approval_action = None

        self.response_ready.emit(parsed)

    def _on_ai_error(self, error_msg: str) -> None:
        """Handle AI request error."""
        parsed = ResponseParser.parse_error(Exception(error_msg))
        self._conversation.add_assistant_message(content=parsed.error_message)
        self.response_ready.emit(parsed)
        self.error.emit(error_msg)

    def _on_processing_done(self) -> None:
        """Processing complete."""
        self._is_processing = False
        self.thinking_finished.emit()

    def _handle_approval_response(self, text: str) -> None:
        """Handle user's yes/no response to an approval request."""
        affirmative = text.strip().lower() in ("yes", "y", "approve", "ok", "go", "do it", "proceed")

        if affirmative:
            self._conversation.add_user_message("Yes, proceed with the operation.")
            self._pending_approval_action = None
            self._process_request()
        else:
            self._conversation.add_user_message("No, cancel the operation.")
            self._pending_approval_action = None
            cancel_msg = "Operation cancelled."
            self._conversation.add_assistant_message(content=cancel_msg)
            self.response_ready.emit(ParsedResponse(text=cancel_msg))

    def _update_system_prompt(self) -> None:
        """Update the system prompt with current folder context."""
        prompt = PromptBuilder.build_system_prompt(
            selected_folder=self._selected_folder,
            scan_mode=self._scan_mode,
        )
        self._conversation.set_system_prompt(prompt)

    # === Speech Methods ===

    def toggle_recording(self) -> None:
        """Toggle speech recording on/off."""
        self._recorder.toggle()

    def _on_recording_ready(self, wav_path: str) -> None:
        """Recording finished — start transcription."""
        self._transcriber.transcribe(wav_path)

    def _on_transcription_complete(self, text: str) -> None:
        """Transcription done — emit for UI to display in input."""
        self.speech_transcribed.emit(text)

    # === Utility ===

    def clear_conversation(self) -> None:
        """Clear conversation history."""
        self._conversation.clear()
        self._pending_approval_action = None
        self._update_system_prompt()

    def test_connection(self) -> tuple[bool, str]:
        """Test the OpenAI API connection."""
        return self._client.test_connection()

    def on_api_key_changed(self) -> None:
        """Handle API key change."""
        self._client.reset_client()
