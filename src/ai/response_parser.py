"""
OP(AI)UM — Response Parser

Parses AI responses to extract:
- Text content for display
- Tool call requests
- Operation plans requiring approval
- Structured data (file lists, counts, etc.)
"""

from __future__ import annotations

import json
import re
from typing import Any, NamedTuple

from loguru import logger


class ParsedToolCall(NamedTuple):
    """A parsed tool call from the AI response."""

    id: str
    name: str
    arguments: dict[str, Any]


class ParsedResponse:
    """
    Structured representation of an AI response.

    Contains the text content, any tool calls, and metadata
    about whether user confirmation is needed.
    """

    def __init__(
        self,
        text: str = "",
        tool_calls: list[ParsedToolCall] | None = None,
        needs_approval: bool = False,
        approval_plan: list[str] | None = None,
        is_error: bool = False,
        error_message: str = "",
        raw_response: dict[str, Any] | None = None,
        cancelled: bool = False,
    ) -> None:
        self.cancelled = cancelled
        self.text = text
        self.tool_calls = tool_calls or []
        self.needs_approval = needs_approval
        self.approval_plan = approval_plan or []
        self.is_error = is_error
        self.error_message = error_message
        self.raw_response = raw_response

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    @property
    def display_text(self) -> str:
        """Get the text to display in the chat UI."""
        if self.is_error:
            return f"Error: {self.error_message}"
        return self.text or ""


class ResponseParser:
    """Parses raw OpenAI API responses into structured format."""

    @staticmethod
    def parse(response: dict[str, Any]) -> ParsedResponse:
        """
        Parse a raw API response into a structured ParsedResponse.

        Args:
            response: Raw response from OpenAIClient.

        Returns:
            ParsedResponse with extracted content.
        """
        try:
            message = response.get("message", {})
            text = message.get("content", "") or ""
            raw_tool_calls = message.get("tool_calls")

            tool_calls: list[ParsedToolCall] = []
            if raw_tool_calls:
                for tc in raw_tool_calls:
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except (json.JSONDecodeError, KeyError):
                        args = {}

                    tool_calls.append(
                        ParsedToolCall(
                            id=tc.get("id", ""),
                            name=tc["function"]["name"],
                            arguments=args,
                        )
                    )

            # Check if the response contains an approval request
            needs_approval, plan = ResponseParser._detect_approval_request(text)

            return ParsedResponse(
                text=text,
                tool_calls=tool_calls,
                needs_approval=needs_approval,
                approval_plan=plan,
                raw_response=response,
                cancelled=bool(response.get("cancelled")),
            )

        except Exception as e:
            logger.error(f"Response parsing error: {e}")
            return ParsedResponse(
                is_error=True,
                error_message=f"Failed to parse AI response: {e}",
                raw_response=response,
            )

    @staticmethod
    def parse_error(error: Exception) -> ParsedResponse:
        """Create an error ParsedResponse from an exception."""
        error_msg = str(error)

        low = error_msg.lower()
        # Friendly error messages
        if "api_key" in low or "authentication" in low or "invalid_api_key" in low or "401" in low:
            friendly = "API key is invalid or expired. Please update it in Settings."
        elif "rate_limit" in low or "429" in low:
            friendly = "Rate limit reached. Please wait a moment and try again."
        elif "insufficient_quota" in low or "billing" in low:
            friendly = "Your API account has no remaining quota. Check your provider billing."
        elif "context_length" in low or "maximum context" in low:
            friendly = "The conversation is too long for the model. Start a new chat."
        elif "timeout" in low or "timed out" in low:
            friendly = "Request timed out. Check your connection or try a simpler request."
        elif "connection" in low or "connect" in low or "name resolution" in low:
            friendly = "Could not reach the AI endpoint. Check your internet connection or base URL."
        elif "model" in low and ("not found" in low or "does not exist" in low or "404" in low):
            friendly = "The configured AI model is not available on this endpoint. Check Settings."
        else:
            friendly = f"AI error: {error_msg}"

        return ParsedResponse(is_error=True, error_message=friendly)

    @staticmethod
    def _detect_approval_request(text: str) -> tuple[bool, list[str]]:
        """
        Detect if the AI response contains an operation plan
        that needs user approval.

        Returns:
            Tuple of (needs_approval, plan_steps).
        """
        if not text:
            return False, []

        # Look for approval keywords
        approval_patterns = [
            r"(?i)approve\s+this\s+operation",
            r"(?i)confirm\s+to\s+proceed",
            r"(?i)shall\s+i\s+proceed",
            r"(?i)do\s+you\s+want\s+me\s+to",
            r"(?i)would\s+you\s+like\s+me\s+to\s+(proceed|execute|continue)",
            r"(?i)\(yes\/no\)",
        ]

        has_approval = any(re.search(p, text) for p in approval_patterns)

        if not has_approval:
            return False, []

        # Extract numbered plan steps
        plan_steps: list[str] = []
        step_pattern = r"^\s*\d+[\.\)]\s*(.+)$"
        for line in text.split("\n"):
            match = re.match(step_pattern, line)
            if match:
                plan_steps.append(match.group(1).strip())

        return True, plan_steps

    @staticmethod
    def format_tool_result(tool_name: str, result: Any) -> str:
        """Format a tool result for display in chat."""
        if isinstance(result, dict):
            if "error" in result:
                return f"**Error**: {result['error']}"
            # Pretty format dict
            lines = []
            for key, value in result.items():
                if key.startswith("_"):
                    continue
                label = key.replace("_", " ").title()
                if isinstance(value, list) and len(value) > 5:
                    lines.append(f"**{label}**: {len(value)} items")
                else:
                    lines.append(f"**{label}**: {value}")
            return "\n".join(lines)
        elif isinstance(result, list):
            if len(result) > 20:
                return f"Found {len(result)} items."
            return "\n".join(f"- {item}" for item in result)
        else:
            return str(result)
