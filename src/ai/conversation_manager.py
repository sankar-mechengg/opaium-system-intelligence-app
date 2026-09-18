"""
OP(AI)UM — Conversation Manager

Manages the chat conversation history within a session.
Handles message storage (including tool-call transcripts), context window
management, and session lifecycle.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

from src.config.constants import AppConstants

# Tool results are kept in memory so the model remembers what it found, but
# large payloads (file contents, long listings) are trimmed to stay in context.
MAX_TOOL_RESULT_CHARS = 6000


class ChatMessage:
    """A single message in the conversation."""

    def __init__(
        self,
        role: str,  # 'system', 'user', 'assistant', 'tool'
        content: str | None,
        timestamp: datetime | None = None,
        tool_call_id: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now()
        self.tool_call_id = tool_call_id
        self.tool_calls = tool_calls
        self.metadata = metadata or {}

    def to_api_format(self) -> dict[str, Any]:
        """Convert to OpenAI API message format."""
        msg: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.role == "assistant" and self.content is None and not self.tool_calls:
            msg["content"] = ""
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        return msg

    @property
    def is_user(self) -> bool:
        return self.role == "user"

    @property
    def is_assistant(self) -> bool:
        return self.role == "assistant"

    @property
    def is_tool(self) -> bool:
        return self.role == "tool"

    @property
    def display_time(self) -> str:
        return self.timestamp.strftime("%I:%M %p")


class ConversationManager:
    """
    Manages chat conversation history for a single session.

    Handles:
    - Message storage (system, user, assistant, tool)
    - Context window trimming (never splits an assistant tool-call from its results)
    - System prompt management
    - Session reset
    """

    def __init__(self, max_history: int = AppConstants.MAX_CONVERSATION_HISTORY) -> None:
        self._messages: list[ChatMessage] = []
        self._system_prompt: str = ""
        self._max_history = max(4, max_history)

    @property
    def messages(self) -> list[ChatMessage]:
        """Get all messages (excluding system prompt)."""
        return self._messages

    @property
    def display_messages(self) -> list[ChatMessage]:
        """Get messages for UI display (user + assistant only)."""
        return [m for m in self._messages if m.role in ("user", "assistant") and m.content]

    @property
    def message_count(self) -> int:
        return len(self._messages)

    def set_max_history(self, max_history: int) -> None:
        self._max_history = max(4, max_history)
        self._trim_history()

    def set_system_prompt(self, prompt: str) -> None:
        """Set or update the system prompt."""
        self._system_prompt = prompt

    def add_user_message(self, content: str) -> ChatMessage:
        """Add a user message."""
        msg = ChatMessage(role="user", content=content)
        self._messages.append(msg)
        self._trim_history()
        return msg

    def add_assistant_message(
        self,
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        """Add an assistant response."""
        msg = ChatMessage(role="assistant", content=content, tool_calls=tool_calls)
        self._messages.append(msg)
        self._trim_history()
        return msg

    def add_tool_result(self, tool_call_id: str, content: str) -> ChatMessage:
        """Add a tool call result."""
        if len(content) > MAX_TOOL_RESULT_CHARS:
            content = content[:MAX_TOOL_RESULT_CHARS] + '... [truncated for memory]"}'
        msg = ChatMessage(role="tool", content=content, tool_call_id=tool_call_id)
        self._messages.append(msg)
        return msg

    def add_transcript(self, transcript: list[dict[str, Any]]) -> None:
        """Append a full tool-loop transcript (assistant tool calls, tool results, final answer)."""
        for m in transcript:
            role = m.get("role")
            if role == "assistant":
                self.add_assistant_message(content=m.get("content"), tool_calls=m.get("tool_calls"))
            elif role == "tool":
                self.add_tool_result(tool_call_id=str(m.get("tool_call_id", "")), content=str(m.get("content", "")))
            elif role == "user":
                self.add_user_message(str(m.get("content", "")))
        self._trim_history()

    def drop_trailing_user_message(self) -> None:
        """Remove the last message if it is an unanswered user turn (used after request failures)."""
        if self._messages and self._messages[-1].is_user:
            self._messages.pop()

    def get_api_messages(self) -> list[dict[str, Any]]:
        """
        Get messages formatted for the OpenAI API.
        Includes system prompt + conversation history.
        """
        api_messages: list[dict[str, Any]] = []

        if self._system_prompt:
            api_messages.append({"role": "system", "content": self._system_prompt})

        for msg in self._messages:
            api_messages.append(msg.to_api_format())

        return api_messages

    def get_last_user_message(self) -> str | None:
        """Get the most recent user message content."""
        for msg in reversed(self._messages):
            if msg.is_user:
                return msg.content
        return None

    def get_last_assistant_message(self) -> str | None:
        """Get the most recent assistant response."""
        for msg in reversed(self._messages):
            if msg.is_assistant and msg.content:
                return msg.content
        return None

    def _trim_history(self) -> None:
        """
        Trim conversation history to stay within limits.
        Keeps the most recent messages and never starts the window with a tool
        result or with an assistant tool-call whose results were dropped.
        """
        if len(self._messages) <= self._max_history:
            return

        trim_point = len(self._messages) - self._max_history

        # Advance to the next user message so tool-call pairs stay intact.
        while trim_point < len(self._messages) and not self._messages[trim_point].is_user:
            trim_point += 1

        if trim_point >= len(self._messages):
            # Only tool/assistant chatter remains — keep the tail as-is.
            return

        self._messages = self._messages[trim_point:]
        logger.debug(f"Conversation trimmed to {len(self._messages)} messages.")

    def clear(self) -> None:
        """Clear all conversation history (keeps system prompt)."""
        self._messages.clear()
        logger.debug("Conversation cleared.")

    def reset(self) -> None:
        """Full reset — clear messages and system prompt."""
        self._messages.clear()
        self._system_prompt = ""
