"""
OP(AI)UM — File Size Detection Tool

Analyzes file and folder sizes. Can show individual file sizes,
folder totals, and disk usage breakdowns.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.ai.tools.base_tool import BaseTool, ToolResult
from src.utils.path_utils import PathUtils


class FileSizerTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_file_sizes"

    @property
    def description(self) -> str:
        return (
            "Get size information for files and folders. Can show individual "
            "file sizes, folder totals, or find the largest items."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File or directory path to analyze",
                },
                "mode": {
                    "type": "string",
                    "enum": ["total", "breakdown", "largest"],
                    "description": "Analysis mode: total size, per-item breakdown, or largest files",
                    "default": "total",
                },
                "top_n": {
                    "type": "integer",
                    "description": "Number of largest items to show (for 'largest' mode)",
                    "default": 10,
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Include subdirectories",
                    "default": True,
                },
            },
            "required": ["path"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        path = kwargs.get("path", "")
        mode = kwargs.get("mode", "total")
        top_n = kwargs.get("top_n", 10)
        recursive = kwargs.get("recursive", True)

        if not self._validate_path(path):
            return ToolResult(success=False, message=f"Path not accessible: {path}")

        if os.path.isfile(path):
            size = os.path.getsize(path)
            return ToolResult(
                success=True,
                message=f"{Path(path).name}: {PathUtils.format_size(size)}",
                data={
                    "path": path,
                    "size_bytes": size,
                    "display_size": PathUtils.format_size(size),
                },
            )

        if mode == "total":
            return self._total_size(path, recursive)
        elif mode == "breakdown":
            return self._breakdown(path)
        elif mode == "largest":
            return self._largest_files(path, top_n, recursive)
        else:
            return ToolResult(success=False, message=f"Unknown mode: {mode}")

    def _total_size(self, path: str, recursive: bool) -> ToolResult:
        total = 0
        file_count = 0
        folder_count = 0

        if recursive:
            for dirpath, dirnames, filenames in os.walk(path):
                folder_count += len(dirnames)
                for fname in filenames:
                    try:
                        total += os.path.getsize(os.path.join(dirpath, fname))
                        file_count += 1
                    except OSError:
                        continue
        else:
            for entry in os.scandir(path):
                try:
                    if entry.is_dir(follow_symlinks=False):
                        folder_count += 1
                    elif entry.is_file(follow_symlinks=False):
                        total += entry.stat().st_size
                        file_count += 1
                except OSError:
                    continue

        data = {
            "total_bytes": total,
            "display_size": PathUtils.format_size(total),
            "file_count": file_count,
            "folder_count": folder_count,
        }

        return ToolResult(
            success=True,
            message=(
                f"{Path(path).name}: {PathUtils.format_size(total)} total, {file_count} files, {folder_count} folders"
            ),
            data=data,
        )

    def _breakdown(self, path: str) -> ToolResult:
        items: list[dict] = []

        for entry in os.scandir(path):
            try:
                if entry.is_dir(follow_symlinks=False):
                    size = PathUtils.get_folder_size(entry.path)
                    items.append(
                        {
                            "name": entry.name,
                            "type": "folder",
                            "size_bytes": size,
                            "display_size": PathUtils.format_size(size),
                        }
                    )
                elif entry.is_file(follow_symlinks=False):
                    size = entry.stat().st_size
                    items.append(
                        {
                            "name": entry.name,
                            "type": "file",
                            "size_bytes": size,
                            "display_size": PathUtils.format_size(size),
                        }
                    )
            except OSError:
                continue

        items.sort(key=lambda x: x["size_bytes"], reverse=True)

        lines = [f"Size breakdown for {Path(path).name}:"]
        for item in items[:20]:
            icon = "📁" if item["type"] == "folder" else "📄"
            lines.append(f"  {icon} {item['name']}: {item['display_size']}")

        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={"items": items},
        )

    def _largest_files(self, path: str, top_n: int, recursive: bool) -> ToolResult:
        from src.core.file_scanner import FileScanner

        large_files = FileScanner.find_large_files(path, min_size_bytes=0, recursive=recursive)
        top = large_files[:top_n]

        lines = [f"Top {len(top)} largest files in {Path(path).name}:"]
        data_items = []
        for f in top:
            lines.append(f"  {f.name}: {f.display_size}")
            data_items.append(
                {
                    "name": f.name,
                    "path": f.path,
                    "size_bytes": f.size_bytes,
                    "display_size": f.display_size,
                }
            )

        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={"files": data_items},
        )
