"""
OP(AI)UM — Chat Panel

Main AI chat interface:
- Conversations sidebar (left)
- Header with model / endpoint, folder context chip and scan-depth toggle
- Streaming message list with inline tool activity cards and one-click Undo
- Approval dialogs for destructive operations
- Input bar with voice input, quick-action chips and a Stop button
- Auto-save of every conversation to SQLite
"""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from src.ai.ai_engine import AIEngine
from src.ai.conversation_db import ConversationDB
from src.ai.prompt_builder import PromptBuilder
from src.ai.response_parser import ParsedResponse
from src.ai.safety import ApprovalRequest
from src.config.config_manager import ConfigManager
from src.ui.chat.approval_dialog import ApprovalDialog
from src.ui.chat.chat_input import ChatInputBar
from src.ui.chat.context_card import ChatContextCard
from src.ui.chat.conversations_sidebar import ConversationsSidebar
from src.ui.chat.message_bubble import ChatMessage, MessageBubble, MessageRole
from src.ui.chat.quick_actions import QuickActionChips
from src.ui.chat.tool_card import ToolCard, pretty_tool_name
from src.ui.chat.typing_indicator import TypingIndicator
from src.ui.widgets.icon_button import IconButton
from src.undo.operation_journal import OperationJournal
from src.undo.undo_manager import UndoManager

WELCOME = (
    "Welcome to OP(AI)UM. Ask me to count, find, organize, rename, move or clean up files — "
    "select a folder in the Explorer to give me context, or just type a path. "
    "Destructive changes always show a preview you can approve or cancel."
)


class ChatPanel(QWidget):
    """
    Signals:
        operation_completed(str): A destructive AI operation finished (description).
        undo_requested(int): User wants to undo an operation.
        status_message(str): Text for the status bar.
        notify(str, str): (kind, message) for the notification service.
    """

    operation_completed = Signal(str)
    undo_requested = Signal(int)
    status_message = Signal(str)
    notify = Signal(str, str)

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
        self._conversation_db = ConversationDB()
        self._ai_engine: AIEngine | None = None
        self._current_folder: str = ""
        self._current_conversation_id: int | None = None
        self._streaming_bubble: MessageBubble | None = None
        self._active_tool_cards: list[ToolCard] = []
        self._pending_context_card: str | None = None

        self._build_ui()
        self._connect_signals()
        self._initialize_ai()
        self._sidebar.refresh()

    # === UI ===

    def _build_ui(self) -> None:
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self._sidebar = ConversationsSidebar(self._conversation_db)
        outer_layout.addWidget(self._sidebar)

        chat_widget = QWidget()
        layout = QVBoxLayout(chat_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setObjectName("chatHeader")
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header.setFixedHeight(44)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 0, 10, 0)
        header_layout.setSpacing(8)

        title = QLabel("AI Assistant")
        title.setObjectName("chatHeaderTitle")
        header_layout.addWidget(title)

        self._model_label = QLabel("")
        self._model_label.setObjectName("chatHeaderModel")
        header_layout.addWidget(self._model_label)

        header_layout.addStretch()

        self._context_chip = IconButton("folder", "", role="accent", icon_size=14, object_name="actionChip")
        self._context_chip.setToolTip("Current folder context — click to clear")
        self._context_chip.setFixedHeight(28)
        self._context_chip.clicked.connect(self.clear_folder_context)
        self._context_chip.hide()
        header_layout.addWidget(self._context_chip)

        self._depth_btn = IconButton(
            "filter", "Shallow", role="text_sub", icon_size=14, object_name="actionChip", checkable=True
        )
        self._depth_btn.setToolTip("Toggle folder scan depth for AI context (shallow / recursive)")
        self._depth_btn.setFixedHeight(28)
        self._depth_btn.toggled.connect(self._on_depth_toggled)
        header_layout.addWidget(self._depth_btn)

        self._new_btn = IconButton("plus", "New chat", role="text_sub", icon_size=14, object_name="actionChip")
        self._new_btn.setFixedHeight(28)
        self._new_btn.clicked.connect(lambda: self._start_new_chat())
        header_layout.addWidget(self._new_btn)

        layout.addWidget(header)

        # Message list
        scroll = QScrollArea()
        scroll.setObjectName("chatScroll")
        # The container is sized manually (see _relayout_messages): bubbles change
        # height asynchronously while streaming, and widgetResizable's cached size
        # hints let messages overlap.
        scroll.setWidgetResizable(False)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.viewport().installEventFilter(self)
        self._scroll = scroll

        self._message_container = QWidget()
        self._message_layout = QVBoxLayout(self._message_container)
        self._message_layout.setContentsMargins(18, 10, 18, 10)
        self._message_layout.setSpacing(4)
        self._message_layout.addStretch()
        scroll.setWidget(self._message_container)
        layout.addWidget(scroll, stretch=1)

        self._in_relayout = False
        self._pending_scroll = False
        self._relayout_timer = QTimer(self)
        self._relayout_timer.setSingleShot(True)
        self._relayout_timer.setInterval(60)
        self._relayout_timer.timeout.connect(self._relayout_messages)

        self._typing = TypingIndicator()
        layout.addWidget(self._typing)

        self._quick_actions = QuickActionChips()
        layout.addWidget(self._quick_actions)

        self._input_bar = ChatInputBar()
        layout.addWidget(self._input_bar)

        outer_layout.addWidget(chat_widget, stretch=1)

        self._add_system_message(WELCOME)

    def _connect_signals(self) -> None:
        self._input_bar.message_sent.connect(self._on_user_message)
        self._input_bar.mic_toggled.connect(self._on_mic_toggled)
        self._input_bar.stop_requested.connect(self._on_stop)
        self._quick_actions.chip_clicked.connect(self._on_user_message)
        self._sidebar.conversation_selected.connect(self._on_conversation_selected)
        self._sidebar.new_chat_requested.connect(lambda: self._start_new_chat())

    # === AI engine lifecycle ===

    def _initialize_ai(self) -> None:
        """Create the AI engine (or reconfigure it) from current settings."""
        try:
            if self._ai_engine is None:
                engine = AIEngine(config=self._config, operation_journal=self._operation_journal, parent=self)
                engine.response_ready.connect(self._on_ai_response)
                engine.error.connect(self._on_ai_error)
                engine.thinking_started.connect(self._on_thinking_started)
                engine.thinking_finished.connect(self._on_thinking_finished)
                engine.text_delta.connect(self._on_text_delta)
                engine.tool_started.connect(self._on_tool_started)
                engine.tool_finished.connect(self._on_tool_finished)
                engine.approval_needed.connect(self._on_approval_needed)
                engine.speech_transcribed.connect(self._on_transcription)
                engine.recorder.audio_level.connect(self._input_bar.set_level)
                engine.recorder.recording_stopped.connect(lambda: self._input_bar.set_mic_state(False))
                engine.initialize()
                self._ai_engine = engine
                if self._current_folder:
                    engine.set_selected_folder(self._current_folder)
            else:
                self._ai_engine.reconfigure()
            self._update_model_label()
            if not self._ai_engine.is_configured:
                self._add_system_message(
                    "No API key configured yet. Open Settings → AI to add your OpenAI key "
                    "or point OP(AI)UM at a local OpenAI-compatible server."
                )
        except Exception as e:
            logger.error(f"Failed to initialize AI engine: {e}")
            self._add_system_message("The AI engine could not be initialized. Check your API key in Settings.")

    def reinitialize_ai(self) -> None:
        """Called after settings change — picks up key/model/endpoint without a restart."""
        self._initialize_ai()

    def _update_model_label(self) -> None:
        ai = self._config.settings.ai
        endpoint = ai.api_base_url.strip()
        where = f" · {endpoint}" if endpoint else ""
        self._model_label.setText(f"{ai.ai_model}{where}")

    # === Sending ===

    def _on_user_message(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        if self._ai_engine is None or not self._ai_engine.is_configured:
            self._add_system_message("AI is not available. Please configure your API key in Settings.")
            return
        if self._ai_engine.is_processing:
            self.status_message.emit("Still working on the previous request…")
            return

        if self._current_conversation_id is None:
            title = text[:60] or "New Conversation"
            self._current_conversation_id = self._conversation_db.create_conversation(
                title=title, folder_path=self._current_folder
            )
            self._sidebar.refresh()
            self._sidebar.set_current_conversation(self._current_conversation_id)

        if self._pending_context_card:
            self._add_context_card(self._pending_context_card)
            self._pending_context_card = None

        self._add_message(MessageRole.USER, text)
        self._save_message("user", text)
        self._ai_engine.send_message(text)

    def _on_stop(self) -> None:
        if self._ai_engine:
            self._ai_engine.cancel()
            self.status_message.emit("Stopping…")

    # === Engine events ===

    def _on_thinking_started(self) -> None:
        self._input_bar.set_busy(True)
        self._typing.start()
        self._streaming_bubble = None
        self._active_tool_cards = []
        self.status_message.emit("OP(AI)UM is thinking…")

    def _on_thinking_finished(self) -> None:
        self._typing.stop()
        self._input_bar.set_busy(False)
        self.status_message.emit("Ready")
        self._input_bar.focus_input()

    def _on_text_delta(self, delta: str) -> None:
        if self._streaming_bubble is None:
            self._typing.stop()
            self._streaming_bubble = self._insert_bubble(MessageRole.ASSISTANT, "", streaming=True)
        self._streaming_bubble.append_text(delta)
        # Follow the stream only while the user is already at the bottom.
        self._schedule_relayout()

    def _on_tool_started(self, name: str, arguments: dict) -> None:  # type: ignore[type-arg]
        # A tool call ends the current streamed paragraph; the answer continues in a new bubble.
        self._streaming_bubble = None
        card = ToolCard(name, arguments)
        card.undo_requested.connect(self._on_card_undo)
        self._insert_widget(card)
        self._active_tool_cards.append(card)
        self._save_message("tool", json.dumps({"tool": name, "arguments": arguments, "status": "running"}))
        self.status_message.emit(f"{pretty_tool_name(name)}…")
        self._scroll_to_bottom()

    def _on_tool_finished(self, name: str, arguments: dict, result: object) -> None:  # type: ignore[type-arg]
        payload = result if isinstance(result, dict) else {"success": True, "message": str(result)}
        card = next((c for c in reversed(self._active_tool_cards) if c.tool_name == name and not c.is_finished), None)
        if card is not None:
            card.set_result(payload)
        self._save_message("tool", json.dumps({"tool": name, "result": payload}, default=str))
        if payload.get("success") and payload.get("operation_id") is not None:
            self.operation_completed.emit(str(payload.get("message") or f"{pretty_tool_name(name)} completed"))
        self._schedule_relayout()

    def _on_approval_needed(self, request: object) -> None:
        if not isinstance(request, ApprovalRequest):
            return
        try:
            self.window().activateWindow()
            dialog = ApprovalDialog(request, self.window())
            approved = dialog.exec() == ApprovalDialog.DialogCode.Accepted
            request.resolve(approved, remember_for_session=dialog.remember)
            self.status_message.emit("Approved — running…" if approved else "Cancelled")
        except Exception as e:
            logger.error(f"Approval dialog failed: {e}")
            request.resolve(False)

    def _on_ai_response(self, parsed: object) -> None:
        if not isinstance(parsed, ParsedResponse):
            return
        try:
            if parsed.is_error:
                return
            text = parsed.text or ""
            if self._streaming_bubble is not None:
                if text:
                    self._streaming_bubble.set_content(text)
                else:
                    self._streaming_bubble.set_content(self._streaming_bubble.message.content)
                self._streaming_bubble = None
            elif text:
                self._add_message(MessageRole.ASSISTANT, text)
            if text:
                self._save_message("assistant", text)
            if parsed.cancelled:
                self._add_system_message("Generation stopped.")
            self._schedule_relayout()
        except Exception as e:
            logger.error(f"Error in _on_ai_response handler: {e}")

    def _on_ai_error(self, error: str) -> None:
        self._typing.stop()
        self._input_bar.set_busy(False)
        self._streaming_bubble = None
        logger.error(f"AI error: {error}")
        self._add_system_message(error)
        self.notify.emit("error", error)

    def _on_card_undo(self, operation_id: int) -> None:
        self.undo_requested.emit(operation_id)
        for card in self._active_tool_cards:
            if card.operation_id == operation_id:
                card.mark_undone()

    # === Speech ===

    def _on_mic_toggled(self, active: bool) -> None:
        if self._ai_engine is None:
            self._input_bar.set_mic_state(False)
            self._add_system_message("Voice input needs the AI engine. Configure your API key first.")
            return
        try:
            if active:
                self._ai_engine.start_recording()
                self.status_message.emit("Recording… click the mic again to stop.")
            else:
                self._ai_engine.stop_recording()
                self.status_message.emit("Transcribing…")
        except Exception as e:
            logger.error(f"Recording error: {e}")
            self._input_bar.set_mic_state(False)
            self._add_system_message(f"Could not start recording: {e}")

    def _on_transcription(self, text: str) -> None:
        self.status_message.emit("Ready")
        if not text.strip():
            return
        if self._config.settings.ai.voice_auto_send:
            self._on_user_message(text.strip())
        else:
            self._input_bar.set_text(text.strip())

    # === Context ===

    def set_folder_context(self, folder_path: str) -> None:
        """Update the folder the AI works in (called by the explorer)."""
        if folder_path == self._current_folder:
            return
        self._current_folder = folder_path
        self._quick_actions.set_current_folder(folder_path)
        if self._ai_engine:
            self._ai_engine.set_selected_folder(folder_path or None)
        if folder_path:
            self._context_chip.setText(Path(folder_path).name or folder_path)
            self._context_chip.setToolTip(f"{folder_path}\nClick to clear the folder context")
            self._context_chip.show()
        else:
            self._context_chip.hide()
        if self._current_conversation_id is not None:
            self._conversation_db.update_conversation(self._current_conversation_id, folder_path=folder_path)

    def clear_folder_context(self) -> None:
        self.set_folder_context("")
        self._add_system_message("Folder context cleared.")

    def _on_depth_toggled(self, checked: bool) -> None:
        mode = "recursive" if checked else "shallow"
        self._depth_btn.setText("Recursive" if checked else "Shallow")
        if self._ai_engine:
            self._ai_engine.set_scan_mode(mode)

    def inject_ai_question(self, question: str, path: str) -> None:
        """Ask about a specific item from a context menu."""
        folder = path if Path(path).is_dir() else str(Path(path).parent)
        self.set_folder_context(folder)
        if self._ai_engine:
            self._ai_engine.set_selected_files([] if Path(path).is_dir() else [path])
        self._pending_context_card = path
        self._on_user_message(question)

    # === Conversation management ===

    def _save_message(self, role: str, content: str) -> None:
        if self._current_conversation_id is not None:
            try:
                self._conversation_db.add_message(self._current_conversation_id, role, content)
            except Exception as e:
                logger.error(f"Failed to save message: {e}")

    def _on_conversation_selected(self, conv_id: int) -> None:
        if self._ai_engine and self._ai_engine.is_processing:
            self.status_message.emit("Wait for the current request to finish before switching chats.")
            return
        self._clear_chat()
        self._current_conversation_id = conv_id
        self._sidebar.set_current_conversation(conv_id)

        history: list[tuple[str, str]] = []
        for msg in self._conversation_db.get_messages(conv_id):
            if msg.role in ("user", "assistant"):
                display = PromptBuilder.strip_context_prefix(msg.content) if msg.role == "user" else msg.content
                self._add_message(MessageRole.USER if msg.role == "user" else MessageRole.ASSISTANT, display)
                history.append((msg.role, msg.content))
            elif msg.role == "tool":
                self._restore_tool_message(msg.content)

        if self._ai_engine:
            self._ai_engine.load_history(history)

        for conv in self._conversation_db.get_conversations():
            if conv.id == conv_id:
                self.set_folder_context(conv.folder_path or "")
                break

        self._scroll_to_bottom()

    def _restore_tool_message(self, content: str) -> None:
        try:
            data = json.loads(content)
        except Exception:
            return
        if not isinstance(data, dict) or "result" not in data:
            return
        card = ToolCard(str(data.get("tool", "tool")), {})
        card.set_result(data.get("result") or {})
        card.undo_requested.connect(self._on_card_undo)
        self._insert_widget(card)

    def _start_new_chat(self, context_msg: str | None = None) -> None:
        if self._ai_engine and self._ai_engine.is_processing:
            self._ai_engine.cancel()
        self._clear_chat()
        self._current_conversation_id = None
        if self._ai_engine:
            self._ai_engine.clear_conversation()
        self._sidebar.set_current_conversation(None)
        self._add_system_message(context_msg or "New conversation. How can I help?")
        self._input_bar.focus_input()

    # === Message list helpers ===

    def _insert_widget(self, widget: QWidget) -> None:
        count = self._message_layout.count()
        self._message_layout.insertWidget(count - 1, widget)
        # Any later height change of the entry (markdown re-render, tool card
        # result, wrapped label) shows up as a LayoutRequest on it.
        widget.installEventFilter(self)
        self._pending_scroll = True
        self._schedule_relayout()

    def _schedule_relayout(self) -> None:
        if not self._in_relayout:
            self._relayout_timer.start()

    def _relayout_messages(self) -> None:
        """
        Size the message container by hand.

        Bubbles change height asynchronously (markdown documents report their
        height only once they know their width, tool cards grow when results
        arrive). Qt propagates those changes one layout level per event-loop
        pass, so a widgetResizable scroll area keeps stale size hints and lets
        messages overlap. Here we flush pending layout requests, activate the
        list layout and pin the container to the resulting height, repeating
        until the numbers stop moving.
        """
        viewport = self._scroll.viewport()
        vw, vh = viewport.width(), viewport.height()
        if vw <= 0 or self._in_relayout:
            return
        self._in_relayout = True
        try:
            bar = self._scroll.verticalScrollBar()
            was_at_bottom = bar.value() >= bar.maximum() - 12
            container = self._message_container
            layout = self._message_layout
            if container.width() != vw:
                container.setFixedWidth(vw)
            for _ in range(6):
                QCoreApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest.value)
                layout.invalidate()
                layout.activate()
                if layout.hasHeightForWidth():
                    # minimumSize() would wrap labels at their narrowest width
                    # and report a far taller column than we actually need.
                    height = max(layout.heightForWidth(vw), layout.minimumHeightForWidth(vw))
                else:
                    height = max(layout.sizeHint().height(), layout.minimumSize().height())
                height = max(height, vh)
                if height == container.height():
                    break
                container.setFixedHeight(height)
            if self._pending_scroll or was_at_bottom:
                self._pending_scroll = False
                bar.setValue(bar.maximum())
        finally:
            self._in_relayout = False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        etype = event.type()
        if watched is self._scroll.viewport():
            if etype == QEvent.Type.Resize:
                self._schedule_relayout()
        elif etype == QEvent.Type.LayoutRequest:
            self._schedule_relayout()
        return super().eventFilter(watched, event)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._pending_scroll = True
        self._schedule_relayout()

    def _insert_bubble(self, role: str, content: str, streaming: bool = False) -> MessageBubble:
        bubble = MessageBubble(ChatMessage(role=role, content=content), streaming=streaming)
        self._insert_widget(bubble)
        return bubble

    def _add_message(self, role: str, content: str) -> None:
        if content:
            self._insert_bubble(role, content)

    def _add_system_message(self, content: str) -> None:
        self._add_message(MessageRole.SYSTEM, content)

    def _add_context_card(self, path: str) -> None:
        self._insert_widget(ChatContextCard(path))

    def _scroll_to_bottom(self) -> None:
        self._pending_scroll = True
        self._schedule_relayout()

    def _clear_chat(self) -> None:
        self._streaming_bubble = None
        self._active_tool_cards = []
        while self._message_layout.count() > 1:
            li = self._message_layout.takeAt(0)
            w = li.widget() if li is not None else None
            if w is not None:
                w.removeEventFilter(self)
                w.hide()
                w.deleteLater()
        self._schedule_relayout()

    def focus_input(self) -> None:
        self._input_bar.focus_input()

    def shutdown(self) -> None:
        if self._ai_engine:
            self._ai_engine.cancel()
            if self._ai_engine.is_recording:
                self._ai_engine.stop_recording()
        self._conversation_db.close()

    @property
    def engine(self) -> AIEngine | None:
        return self._ai_engine
