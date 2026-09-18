"""
OP(AI)UM — AI Engine

Main orchestrator for the AI system. Ties together:
- OpenAI client (chat + transcription, any OpenAI-compatible endpoint)
- Function registry (tool definitions)
- Conversation manager (history incl. tool transcripts)
- Safety layer (path guard + user approval broker)
- Undo journal (operation recording)
- Prompt builder (system prompt + context)

This is the single entry point the UI chat widget talks to. All network
and tool work runs on the thread pool; results are delivered via signals.
"""

from __future__ import annotations

import threading
from typing import Any

from loguru import logger
from PySide6.QtCore import QObject, Signal

from src.ai.conversation_manager import ConversationManager
from src.ai.function_registry import FunctionRegistry
from src.ai.openai_client import OpenAIClient
from src.ai.prompt_builder import PromptBuilder
from src.ai.response_parser import ResponseParser
from src.ai.safety import ApprovalBroker, ApprovalRequest
from src.ai.speech_recorder import SpeechRecorder
from src.ai.speech_transcriber import SpeechTranscriber
from src.ai.tool_executor import ToolExecutorWithJournal
from src.config.config_manager import ConfigManager
from src.undo.operation_journal import OperationJournal


class AIEngine(QObject):
    """
    Central AI engine for OP(AI)UM.

    Signals:
        response_ready(ParsedResponse): Final response for the turn.
        text_delta(str): Streamed text chunk (only when streaming is enabled).
        tool_started(str, dict): A tool call began (name, arguments).
        tool_finished(str, dict, object): A tool call ended (name, arguments, result dict).
        approval_needed(object): ApprovalRequest that the UI must resolve.
        thinking_started / thinking_finished: Busy state.
        speech_transcribed(str): Voice input transcribed.
        error(str): Error message.
    """

    response_ready = Signal(object)
    text_delta = Signal(str)
    tool_started = Signal(str, dict)
    tool_finished = Signal(str, dict, object)
    approval_needed = Signal(object)
    thinking_started = Signal()
    thinking_finished = Signal()
    speech_transcribed = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        config: ConfigManager,
        operation_journal: OperationJournal,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._journal = operation_journal

        # Components
        self._client = OpenAIClient(config)
        self._registry = FunctionRegistry()
        self._conversation = ConversationManager(max_history=config.settings.ai.max_conversation_history)
        self._recorder = SpeechRecorder(self)
        self._transcriber = SpeechTranscriber(self._client, self)
        self._broker = ApprovalBroker()
        self._broker.set_handler(self._dispatch_approval)

        # State
        self._selected_folder: str | None = None
        self._selected_files: list[str] = []
        self._scan_mode: str = "shallow"
        self._is_processing = False
        self._cancel_event = threading.Event()
        self._initialized = False

        # Connect speech signals
        self._recorder.transcription_ready.connect(self._on_recording_ready)
        self._recorder.error.connect(self.error.emit)
        self._transcriber.transcription_complete.connect(self._on_transcription_complete)
        self._transcriber.transcription_error.connect(self.error.emit)

    # === Lifecycle ===

    def initialize(self) -> None:
        """Initialize the AI engine — register tools and set system prompt."""
        if not self._initialized:
            self._registry.register_all_tools()
            self._initialized = True
        self._update_system_prompt()
        logger.info(f"AI Engine initialized with {self._registry.tool_count} tools.")

    def reconfigure(self) -> None:
        """Re-read settings (API key, model, endpoint) without losing the conversation."""
        self._client.reset_client()
        self._conversation.set_max_history(self._config.settings.ai.max_conversation_history)
        self._update_system_prompt()
        logger.info("AI Engine reconfigured.")

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

    @property
    def registry(self) -> FunctionRegistry:
        return self._registry

    @property
    def approval_broker(self) -> ApprovalBroker:
        return self._broker

    @property
    def client(self) -> OpenAIClient:
        return self._client

    # === Context ===

    def set_selected_folder(self, folder_path: str | None) -> None:
        """Update the currently selected folder context."""
        self._selected_folder = folder_path
        self._update_system_prompt()

    def set_selected_files(self, file_paths: list[str]) -> None:
        """Update the currently selected files."""
        self._selected_files = list(file_paths)

    def set_scan_mode(self, mode: str) -> None:
        """Set scan mode: 'shallow' or 'recursive'."""
        self._scan_mode = mode
        self._update_system_prompt()

    # === Chat ===

    def send_message(self, text: str) -> None:
        """
        Send a user message to the AI. Runs the request in a background thread.
        """
        if self._is_processing:
            self.error.emit("AI is still processing the previous request.")
            return

        if not self.is_configured:
            self.error.emit("OpenAI API key not configured. Go to Settings.")
            return

        enriched = PromptBuilder.build_user_message(
            text,
            selected_folder=self._selected_folder,
            selected_files=self._selected_files,
        )
        self._conversation.add_user_message(enriched)
        self._process_request()

    def cancel(self) -> None:
        """Stop the current generation as soon as possible."""
        if self._is_processing:
            self._cancel_event.set()
            logger.info("AI generation cancel requested.")

    def _process_request(self) -> None:
        """Send the conversation to the AI and handle the response."""
        self._is_processing = True
        self._cancel_event.clear()
        self.thinking_started.emit()

        from src.utils.thread_pool import ThreadPoolManager, Worker

        worker = Worker(self._execute_ai_request)
        worker.signals.result.connect(self._on_ai_response)
        worker.signals.error.connect(self._on_ai_error)
        worker.signals.finished.connect(self._on_processing_done)
        ThreadPoolManager.run(worker)

    def _execute_ai_request(self) -> dict[str, Any]:
        """Execute the AI request (runs in thread pool)."""
        settings = self._config.settings.ai
        messages = self._conversation.get_api_messages()
        tools = self._registry.get_all_schemas()
        tool_executor = ToolExecutorWithJournal(
            self._registry,
            self._journal,
            approval_broker=self._broker,
            confirm_destructive=settings.confirm_destructive,
        )

        def on_tool_end(name: str, args: dict[str, Any], result: Any) -> None:
            payload = result.to_dict() if hasattr(result, "to_dict") else {"raw": result}
            self.tool_finished.emit(name, args, payload)

        return self._client.chat_with_tool_loop(
            messages=messages,
            tools=tools,
            tool_executor=tool_executor,
            max_rounds=max(1, settings.max_tool_rounds),
            stream=settings.streaming,
            on_text_delta=self.text_delta.emit,
            on_tool_start=lambda name, args: self.tool_started.emit(name, args),
            on_tool_end=on_tool_end,
            should_cancel=self._cancel_event.is_set,
        )

    def _dispatch_approval(self, request: ApprovalRequest) -> None:
        """Called on the worker thread — hand the request to the UI via a queued signal."""
        self.approval_needed.emit(request)

    def _on_ai_response(self, raw_response: object) -> None:
        """Handle AI response from the background thread (main thread)."""
        response = (
            dict(raw_response)
            if isinstance(raw_response, dict)
            else {"message": {"content": str(raw_response), "tool_calls": None}}
        )
        parsed = ResponseParser.parse(response)

        # Persist the whole turn (tool calls + results + final text) so the model
        # remembers what it discovered on the next turn.
        transcript = response.get("transcript") or []
        if transcript:
            self._conversation.add_transcript(transcript)
        else:
            self._conversation.add_assistant_message(content=parsed.text or "")

        parsed.cancelled = bool(response.get("cancelled"))
        self.response_ready.emit(parsed)

    def _on_ai_error(self, error_msg: str) -> None:
        """Handle AI request error."""
        parsed = ResponseParser.parse_error(Exception(error_msg))
        # Keep the failed user turn out of memory so a retry does not double-send it.
        self._conversation.drop_trailing_user_message()
        self.response_ready.emit(parsed)
        self.error.emit(parsed.error_message)

    def _on_processing_done(self) -> None:
        """Processing complete."""
        self._is_processing = False
        self._cancel_event.clear()
        self.thinking_finished.emit()

    def _update_system_prompt(self) -> None:
        """Update the system prompt with current folder context."""
        prompt = PromptBuilder.build_system_prompt(
            selected_folder=self._selected_folder,
            scan_mode=self._scan_mode,
            confirm_destructive=self._config.settings.ai.confirm_destructive,
        )
        self._conversation.set_system_prompt(prompt)

    # === Conversation memory helpers used by the chat panel ===

    def clear_conversation(self) -> None:
        """Clear conversation history."""
        self._conversation.clear()
        self._broker.clear_trust()
        self._update_system_prompt()

    def load_history(self, messages: list[tuple[str, str]]) -> None:
        """Replace memory with stored (role, content) pairs from a saved conversation."""
        self._conversation.clear()
        for role, content in messages:
            if role == "user":
                self._conversation.add_user_message(content)
            elif role == "assistant":
                self._conversation.add_assistant_message(content)
        self._update_system_prompt()

    # === Speech Methods ===

    def toggle_recording(self) -> None:
        """Toggle speech recording on/off."""
        self._recorder.toggle()

    def start_recording(self) -> None:
        self._recorder.start()

    def stop_recording(self) -> None:
        self._recorder.stop()

    def _on_recording_ready(self, wav_path: str) -> None:
        """Recording finished — start transcription."""
        if not self.is_configured:
            self.error.emit("API key required for speech transcription.")
            return
        self._transcriber.transcribe(wav_path)

    def _on_transcription_complete(self, text: str) -> None:
        """Transcription done — emit for UI to display in input."""
        self._recorder.cleanup()
        self.speech_transcribed.emit(text)

    # === Utility ===

    def test_connection(self) -> tuple[bool, str]:
        """Test the OpenAI API connection."""
        return self._client.test_connection()

    def on_api_key_changed(self) -> None:
        """Handle API key / endpoint change."""
        self.reconfigure()
