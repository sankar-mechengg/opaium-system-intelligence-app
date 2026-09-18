"""
OP(AI)UM — Recycle Bin Tool

AI-callable tool for querying and managing the Windows Recycle Bin.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.ai.tools.base_tool import BaseTool, ToolResult
from src.core.models import OperationRecord
from src.core.recycle_bin import RecycleBinManager


class RecycleBinTool(BaseTool):
    @property
    def name(self) -> str:
        return "recycle_bin"

    @property
    def description(self) -> str:
        return (
            "Query the Windows Recycle Bin: 'info' gives item count and size, 'list' shows the items with their "
            "original locations, 'empty' permanently clears it (irreversible)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["info", "list", "empty"],
                    "description": "Action: 'info' to query, 'list' to enumerate items, 'empty' to clear the bin",
                    "default": "info",
                },
            },
        }

    @property
    def is_destructive(self) -> bool:
        return True  # 'empty' action is destructive

    def preview(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "info")
        if action in ("info", "list"):
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
        elif action == "list":
            items = RecycleBinManager.get_items(limit=200)
            lines = [f"{'[DIR] ' if it.is_folder else ''}{it.original_path} ({it.deleted_at})" for it in items[:50]]
            msg = f"Recycle Bin contains {len(items)} item(s)." + (" Showing first 50." if len(items) > 50 else "")
            return ToolResult(
                success=True,
                message=msg,
                data={"count": len(items), "items": lines},
            )
        elif action == "empty":
            info = RecycleBinManager.get_info()
            success = RecycleBinManager.empty(confirm=False)
            if success:
                operation = OperationRecord(
                    timestamp=datetime.now(),
                    operation_type="empty_recycle_bin",
                    description=f"Emptied Recycle Bin ({info.item_count} items, {info.display_size})",
                    is_undoable=False,
                    metadata={"items": info.item_count, "bytes": info.total_size_bytes},
                )
                return ToolResult(success=True, message="Recycle Bin emptied successfully.", operation=operation)
            return ToolResult(success=False, message="Failed to empty Recycle Bin.")
        else:
            return ToolResult(success=False, message=f"Unknown action: {action}")
