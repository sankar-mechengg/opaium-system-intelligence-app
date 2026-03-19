"""
OP(AI)UM — Startup Programs Tool

AI-callable tool for listing Windows startup programs.
"""

from __future__ import annotations

from typing import Any

from src.ai.tools.base_tool import BaseTool, ToolResult
from src.core.startup_manager import StartupManager


class StartupTool(BaseTool):
    @property
    def name(self) -> str:
        return "startup_programs"

    @property
    def description(self) -> str:
        return "List programs configured to start with Windows. Shows entries from registry and Startup folder."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "enum": ["all", "registry_user", "registry_machine", "startup_folder"],
                    "description": "Which startup source to query",
                    "default": "all",
                },
            },
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)
        source = kwargs.get("source", "all")

        entries = StartupManager.get_all_entries()

        if source != "all":
            entries = [e for e in entries if e.source == source]

        if not entries:
            return ToolResult(
                success=True,
                message="No startup programs found.",
                data={"entries": [], "count": 0},
            )

        lines = [f"Found {len(entries)} startup program(s):"]
        for entry in entries:
            source_label = {
                "registry_user": "User Registry",
                "registry_machine": "System Registry",
                "startup_folder": "Startup Folder",
            }.get(entry.source, entry.source)
            lines.append(f"  {entry.name} ({source_label})")
            lines.append(f"    {entry.command}")

        data_entries = [
            {"name": e.name, "command": e.command, "source": e.source, "enabled": e.enabled} for e in entries
        ]

        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={"entries": data_entries, "count": len(entries)},
        )
