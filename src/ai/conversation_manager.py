"""
OP(AI)UM — Conversation Manager

Manages the chat conversation history within a session.
Handles message storage, context window management, and
session lifecycle. Resets on app close (session-based).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

from src.config.constants import AppConstants


class ChatMessage:
    """A single message in the conversation."""

    def __init__(
        self,
        role: str,  # 'system', 'user', 'assistant', 'tool'
        content: str,
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
        msg: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
        }
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
    - Context window trimming (keep within token limits)
    - System prompt management
    - Session reset
    """

    def __init__(self, max_history: int = AppConstants.MAX_CONVERSATION_HISTORY) -> None:
        self._messages: list[ChatMessage] = []
        self._system_prompt: str = ""
        self._max_history = max_history

    @property
    def messages(self) -> list[ChatMessage]:
        """Get all messages (excluding system prompt)."""
        return self._messages

    @property
    def display_messages(self) -> list[ChatMessage]:
        """Get messages for UI display (user + assistant only)."""
        return [m for m in self._messages if m.role in ("user", "assistant")]

    @property
    def message_count(self) -> int:
        return len(self._messages)

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
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> ChatMessage:
        """Add an assistant response."""
        msg = ChatMessage(role="assistant", content=content, tool_calls=tool_calls)
        self._messages.append(msg)
        self._trim_history()
        return msg

    def add_tool_result(self, tool_call_id: str, content: str) -> ChatMessage:
        """Add a tool call result."""
        msg = ChatMessage(role="tool", content=content, tool_call_id=tool_call_id)
        self._messages.append(msg)
        return msg

    def get_api_messages(self) -> list[dict[str, Any]]:
        """
        Get messages formatted for the OpenAI API.
        Includes system prompt + conversation history.
        """
        api_messages: list[dict[str, Any]] = []

        # System prompt always first
        if self._system_prompt:
            api_messages.append(
                {
                    "role": "system",
                    "content": self._system_prompt,
                }
            )

        # Add conversation messages
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
            if msg.is_assistant:
                return msg.content
        return None

    def _trim_history(self) -> None:
        """
        Trim conversation history to stay within limits.
        Keeps the most recent messages, always preserving
        the system prompt and tool call/result pairs.
        """
        if len(self._messages) <= self._max_history:
            return

        # Keep the last N messages, but don't break tool call pairs
        trim_point = len(self._messages) - self._max_history

        # Find a safe trim point (don't split tool call pairs)
        while trim_point < len(self._messages):
            msg = self._messages[trim_point]
            if msg.role == "tool":
                # Don't start with a tool result — go one back
                trim_point += 1
            else:
                break

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

    def has_pending_approval(self) -> bool:
        """Check if the last assistant message is waiting for approval."""
        last = self.get_last_assistant_message()
        if last:
            approval_keywords = [
                "approve",
                "confirm",
                "proceed",
                "yes/no",
                "shall i",
                "would you like me to",
            ]
            return any(kw in last.lower() for kw in approval_keywords)
        return False
