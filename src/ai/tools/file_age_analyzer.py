"""
OP(AI)UM — File Age Analyzer Tool

Analyzes file ages to find stale files not modified in a long time.
Useful for cleanup and archival decisions.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.ai.tools.base_tool import BaseTool, ToolResult
from src.utils.path_utils import PathUtils


class FileAgeAnalyzerTool(BaseTool):
    @property
    def name(self) -> str:
        return "analyze_file_ages"

    @property
    def description(self) -> str:
        return (
            "Find files that haven't been modified in a specified number of days. "
            "Helps identify stale or forgotten files for cleanup."
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
                "older_than_days": {
                    "type": "integer",
                    "description": "Find files not modified in this many days",
                    "default": 365,
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Include subdirectories",
                    "default": True,
                },
                "top_n": {
                    "type": "integer",
                    "description": "Maximum results to return",
                    "default": 20,
                },
            },
            "required": ["path"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        path = kwargs.get("path", "")
        older_than_days = kwargs.get("older_than_days", 365)
        recursive = kwargs.get("recursive", True)
        top_n = kwargs.get("top_n", 20)

        if not self._validate_directory(path):
            return ToolResult(success=False, message=f"Directory not accessible: {path}")

        cutoff = datetime.now() - timedelta(days=older_than_days)
        old_files: list[dict] = []
        total_scanned = 0

        try:
            walker = os.walk(path) if recursive else [(path, [], os.listdir(path))]
            for dirpath, _, filenames in walker:
                for fname in filenames:
                    fpath = os.path.join(dirpath, fname)
                    total_scanned += 1
                    try:
                        stat = os.stat(fpath)
                        mtime = datetime.fromtimestamp(stat.st_mtime)
                        if mtime < cutoff:
                            age_days = (datetime.now() - mtime).days
                            old_files.append(
                                {
                                    "name": fname,
                                    "path": fpath,
                                    "size_bytes": stat.st_size,
                                    "display_size": PathUtils.format_size(stat.st_size),
                                    "last_modified": mtime.isoformat(),
                                    "age_days": age_days,
                                    "age_display": self._format_age(age_days),
                                }
                            )
                    except OSError:
                        continue
        except (OSError, PermissionError) as e:
            return ToolResult(success=False, message=f"Error scanning: {e}")

        old_files.sort(key=lambda x: x["age_days"], reverse=True)
        result_files = old_files[:top_n]
        total_size = sum(f["size_bytes"] for f in old_files)

        if not old_files:
            return ToolResult(
                success=True,
                message=f"No files older than {older_than_days} days in {Path(path).name}.",
                data={"count": 0, "files": []},
            )

        lines = [
            f"Found {len(old_files)} files not modified in {older_than_days}+ days "
            f"({PathUtils.format_size(total_size)} total):"
        ]
        for f in result_files:
            lines.append(f"  {f['age_display']:>12s}  {f['display_size']:>8s}  {f['name']}")

        if len(old_files) > top_n:
            lines.append(f"  ... and {len(old_files) - top_n} more")

        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={
                "count": len(old_files),
                "total_size": total_size,
                "scanned": total_scanned,
                "files": result_files,
            },
        )

    @staticmethod
    def _format_age(days: int) -> str:
        if days < 30:
            return f"{days} days"
        elif days < 365:
            months = days // 30
            return f"{months} month{'s' if months != 1 else ''}"
        else:
            years = days // 365
            remaining = (days % 365) // 30
            if remaining:
                return f"{years}y {remaining}m"
            return f"{years} year{'s' if years != 1 else ''}"
