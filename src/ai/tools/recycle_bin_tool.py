"""
OP(AI)UM — Recycle Bin Tool

AI-callable tool for querying and managing the Windows Recycle Bin.
"""

from __future__ import annotations

from typing import Any

from src.ai.tools.base_tool import BaseTool, ToolResult
from src.core.recycle_bin import RecycleBinManager


class RecycleBinTool(BaseTool):
    @property
    def name(self) -> str:
        return "recycle_bin"

    @property
    def description(self) -> str:
        return "Query the Windows Recycle Bin. Can show how many items are in it, total size, and optionally empty it."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["info", "empty"],
                    "description": "Action: 'info' to query, 'empty' to clear the bin",
                    "default": "info",
                },
            },
        }

    @property
    def is_destructive(self) -> bool:
        return True  # 'empty' action is destructive

    def preview(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "info")
        if action == "info":
            return self.execute(**kwargs)

        info = RecycleBinManager.get_info()
        return ToolResult(
            success=True,
            message="Ready to empty Recycle Bin",
            requires_approval=True,
            preview=[
                "Will permanently empty the Recycle Bin:",
                f"  Items: {info.item_count}",
                f"  Size: {info.display_size}",
                "  This action cannot be undone.",
            ],
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)
        action = kwargs.get("action", "info")

        if action == "info":
            info = RecycleBinManager.get_info()
            return ToolResult(
                success=True,
                message=(f"Recycle Bin: {info.item_count} items, {info.display_size}"),
                data={
                    "item_count": info.item_count,
                    "size_bytes": info.total_size_bytes,
                    "display_size": info.display_size,
                },
            )
        elif action == "empty":
            success = RecycleBinManager.empty(confirm=False)
            if success:
                return ToolResult(success=True, message="Recycle Bin emptied successfully.")
            return ToolResult(success=False, message="Failed to empty Recycle Bin.")
        else:
            return ToolResult(success=False, message=f"Unknown action: {action}")
