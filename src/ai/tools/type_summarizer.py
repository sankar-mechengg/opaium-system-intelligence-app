"""
OP(AI)UM — File Type Summarizer Tool

Provides a breakdown of file types in a directory with counts
and sizes per extension.
"""

from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.ai.tools.base_tool import BaseTool, ToolResult
from src.utils.path_utils import PathUtils


class TypeSummarizerTool(BaseTool):

    @property
    def name(self) -> str:
        return "summarize_file_types"

    @property
    def description(self) -> str:
        return (
            "Get a summary of file types in a directory. Shows count and "
            "total size for each file extension."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory to analyze",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Include subdirectories",
                    "default": False,
                },
            },
            "required": ["path"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        path = kwargs.get("path", "")
        recursive = kwargs.get("recursive", False)

        if not self._validate_directory(path):
            return ToolResult(success=False, message=f"Directory not accessible: {path}")

        type_data: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "size": 0})
        total_files = 0
        total_size = 0

        try:
            walker = os.walk(path) if recursive else [(path, [], os.listdir(path))]
            for dirpath, _, filenames in walker:
                for fname in filenames:
                    fpath = os.path.join(dirpath, fname)
                    if not os.path.isfile(fpath):
                        continue

                    ext = Path(fname).suffix.lstrip(".").lower() or "(no extension)"
                    try:
                        size = os.path.getsize(fpath)
                    except OSError:
                        size = 0

                    type_data[ext]["count"] += 1
                    type_data[ext]["size"] += size
                    total_files += 1
                    total_size += size

        except (OSError, PermissionError) as e:
            return ToolResult(success=False, message=f"Error scanning: {e}")

        # Sort by count descending
        sorted_types = sorted(type_data.items(), key=lambda x: x[1]["count"], reverse=True)

        summary = []
        for ext, info in sorted_types:
            summary.append({
                "extension": ext,
                "count": info["count"],
                "size_bytes": info["size"],
                "display_size": PathUtils.format_size(info["size"]),
                "percentage": round(info["count"] / total_files * 100, 1) if total_files else 0,
            })

        lines = [
            f"File type summary for {Path(path).name} "
            f"({total_files} files, {PathUtils.format_size(total_size)}):",
        ]
        for item in summary[:15]:
            bar = "█" * max(1, int(item["percentage"] / 5))
            lines.append(
                f"  .{item['extension']:12s}  {item['count']:5d} files  "
                f"{item['display_size']:>10s}  {bar} {item['percentage']}%"
            )

        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={
                "total_files": total_files,
                "total_size": total_size,
                "types": summary,
            },
        )
