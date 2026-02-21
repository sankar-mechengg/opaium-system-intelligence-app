"""
OP(AI)UM — Large File Finder Tool

Finds files exceeding a specified size threshold.
Useful for disk cleanup and space management.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.ai.tools.base_tool import BaseTool, ToolResult
from src.utils.path_utils import PathUtils


class LargeFileFinderTool(BaseTool):

    @property
    def name(self) -> str:
        return "find_large_files"

    @property
    def description(self) -> str:
        return (
            "Find files larger than a specified size. Useful for disk cleanup. "
            "Returns files sorted by size (largest first)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory to search",
                },
                "min_size_mb": {
                    "type": "number",
                    "description": "Minimum file size in megabytes",
                    "default": 100,
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Include subdirectories",
                    "default": True,
                },
                "top_n": {
                    "type": "integer",
                    "description": "Maximum number of results",
                    "default": 20,
                },
            },
            "required": ["path"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        path = kwargs.get("path", "")
        min_size_mb = kwargs.get("min_size_mb", 100)
        recursive = kwargs.get("recursive", True)
        top_n = kwargs.get("top_n", 20)

        if not self._validate_directory(path):
            return ToolResult(success=False, message=f"Directory not accessible: {path}")

        min_bytes = int(min_size_mb * 1024 * 1024)
        large_files: list[dict] = []

        try:
            walker = os.walk(path) if recursive else [(path, [], os.listdir(path))]
            for dirpath, _, filenames in walker:
                for fname in filenames:
                    fpath = os.path.join(dirpath, fname)
                    try:
                        size = os.path.getsize(fpath)
                        if size >= min_bytes:
                            large_files.append({
                                "name": fname,
                                "path": fpath,
                                "size_bytes": size,
                                "display_size": PathUtils.format_size(size),
                                "extension": Path(fname).suffix.lstrip(".").lower(),
                            })
                    except OSError:
                        continue
        except (OSError, PermissionError) as e:
            return ToolResult(success=False, message=f"Error scanning: {e}")

        large_files.sort(key=lambda x: x["size_bytes"], reverse=True)
        result_files = large_files[:top_n]

        total_size = sum(f["size_bytes"] for f in result_files)

        if not result_files:
            return ToolResult(
                success=True,
                message=f"No files larger than {min_size_mb} MB found in {Path(path).name}.",
                data={"files": [], "count": 0},
            )

        lines = [
            f"Found {len(large_files)} files over {min_size_mb} MB "
            f"({PathUtils.format_size(total_size)} total):"
        ]
        for f in result_files:
            lines.append(f"  {f['display_size']:>10s}  {f['name']}")

        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={"files": result_files, "count": len(large_files), "total_bytes": total_size},
        )
