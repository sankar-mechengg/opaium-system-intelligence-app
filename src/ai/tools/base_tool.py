"""
OP(AI)UM — Base Tool Class

Abstract base class that all AI-callable tools must inherit from.
Provides a standard interface for the function registry and
integrates with the undo journal for reversible operations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from loguru import logger

from src.core.models import OperationRecord


class ToolResult:
    """
    Standardized result returned by all tools.

    Attributes:
        success: Whether the operation succeeded.
        message: Human-readable result description.
        data: Structured data payload (tool-specific).
        operation: OperationRecord for undo journal (if applicable).
        requires_approval: Whether this needs user confirmation before executing.
        preview: Preview of what the operation will do (for approval dialog).
    """

    def __init__(
        self,
        success: bool = True,
        message: str = "",
        data: Any = None,
        operation: OperationRecord | None = None,
        requires_approval: bool = False,
        preview: list[str] | None = None,
        operation_id: int | None = None,
    ) -> None:
        self.success = success
        self.message = message
        self.data = data
        self.operation = operation
        self.requires_approval = requires_approval
        self.preview = preview or []
        self.operation_id = operation_id

    def __repr__(self) -> str:
        status = "OK" if self.success else "FAIL"
        return f"ToolResult({status}: {self.message})"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        payload: dict[str, Any] = {
            "success": self.success,
            "message": self.message,
            "data": self.data,
        }
        if self.operation_id is not None:
            payload["operation_id"] = self.operation_id
            payload["undoable"] = bool(self.operation and self.operation.is_undoable)
        return payload


class BaseTool(ABC):
    """
    Abstract base class for AI-callable tools.

    Every tool must define:
    - name: Unique tool name for the function registry
    - description: What the tool does (sent to GPT for function calling)
    - parameters: JSON Schema of accepted parameters
    - execute(): The actual implementation
    - is_destructive: Whether it modifies/deletes files

    Non-destructive tools (count, size, list) execute immediately.
    Destructive tools (rename, delete, move) return a preview first,
    then execute only after user approval.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does."""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema for the tool's parameters."""
        ...

    @property
    def is_destructive(self) -> bool:
        """Whether this tool modifies, moves, or deletes files."""
        return False

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute the tool operation.

        Args:
            **kwargs: Tool-specific parameters matching the JSON schema.

        Returns:
            ToolResult with outcome.
        """
        ...

    def preview(self, **kwargs: Any) -> ToolResult:
        """
        Generate a preview of what the tool will do without executing.

        Default implementation for non-destructive tools just executes.
        Destructive tools should override this to show a plan.
        """
        if self.is_destructive:
            return ToolResult(
                success=True,
                message=f"Preview for {self.name}",
                requires_approval=True,
                preview=[f"This operation will be performed by {self.name}"],
            )
        return self.execute(**kwargs)

    def to_openai_function(self) -> dict[str, Any]:
        """
        Convert this tool to OpenAI function calling format.

        Returns:
            Dict compatible with OpenAI's tools parameter.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def _validate_path(self, path: str) -> bool:
        """Validate that a path exists and is accessible."""
        import os

        return os.path.exists(path) and os.access(path, os.R_OK)

    def _validate_directory(self, path: str) -> bool:
        """Validate that a path is an accessible directory."""
        import os

        return os.path.isdir(path) and os.access(path, os.R_OK)

    def _log_execution(self, **kwargs: Any) -> None:
        """Log tool execution for debugging."""
        params = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
        logger.info(f"Tool executing: {self.name}({params})")
