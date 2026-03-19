"""
OP(AI)UM — Disk Usage Tool

AI-callable tool for disk space information and usage analysis.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.ai.tools.base_tool import BaseTool, ToolResult
from src.core.disk_utils import DiskUtils


class DiskUsageTool(BaseTool):
    @property
    def name(self) -> str:
        return "disk_usage"

    @property
    def description(self) -> str:
        return "Get disk space information. Can show all drives, a specific drive, or analyze a folder's disk usage."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["drives", "folder"],
                    "description": "'drives' lists all drives, 'folder' analyzes a specific folder",
                    "default": "drives",
                },
                "path": {
                    "type": "string",
                    "description": "Folder path (required for 'folder' mode)",
                },
            },
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)
        mode = kwargs.get("mode", "drives")

        if mode == "drives":
            return self._list_drives()
        elif mode == "folder":
            path = kwargs.get("path", "")
            if not path:
                return ToolResult(success=False, message="Path is required for folder mode.")
            return self._analyze_folder(path)
        else:
            return ToolResult(success=False, message=f"Unknown mode: {mode}")

    def _list_drives(self) -> ToolResult:
        drives = DiskUtils.get_all_drives()

        if not drives:
            return ToolResult(success=False, message="No drives detected.")

        lines = [f"Found {len(drives)} drive(s):"]
        data_drives = []

        for d in drives:
            bar_len = int(d.percent_used / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            lines.append(
                f"  {d.letter}: [{bar}] {d.percent_used}% "
                f"({d.display_used} / {d.display_total}) - {d.label} ({d.filesystem})"
            )
            data_drives.append(
                {
                    "letter": d.letter,
                    "label": d.label,
                    "filesystem": d.filesystem,
                    "total_bytes": d.total_bytes,
                    "used_bytes": d.used_bytes,
                    "free_bytes": d.free_bytes,
                    "percent_used": d.percent_used,
                    "display_total": d.display_total,
                    "display_free": d.display_free,
                }
            )

        return ToolResult(success=True, message="\n".join(lines), data={"drives": data_drives})

    def _analyze_folder(self, path: str) -> ToolResult:
        if not self._validate_directory(path):
            return ToolResult(success=False, message=f"Directory not accessible: {path}")

        usage = DiskUtils.get_folder_disk_usage(path)

        lines = [
            f"Disk usage for {Path(path).name}:",
            f"  Total size: {usage['display_size']}",
            f"  Files: {usage['file_count']}",
            f"  Folders: {usage['folder_count']}",
        ]

        return ToolResult(success=True, message="\n".join(lines), data=usage)
