"""
OP(AI)UM — File Counter Tool

Counts files and folders in a directory with optional
filtering by extension, size, and age.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.ai.tools.base_tool import BaseTool, ToolResult


class FileCounterTool(BaseTool):

    @property
    def name(self) -> str:
        return "count_files"

    @property
    def description(self) -> str:
        return (
            "Count files and folders in a directory. Can filter by extension, "
            "minimum size, or age. Returns total counts and breakdown by type."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to count files in",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Include subdirectories",
                    "default": False,
                },
                "extension": {
                    "type": "string",
                    "description": "Filter by file extension (e.g., 'pdf', 'jpg')",
                },
                "min_size_mb": {
                    "type": "number",
                    "description": "Only count files larger than this (MB)",
                },
                "older_than_days": {
                    "type": "integer",
                    "description": "Only count files older than N days",
                },
            },
            "required": ["path"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        path = kwargs.get("path", "")
        recursive = kwargs.get("recursive", False)
        extension = kwargs.get("extension", "")
        min_size_mb = kwargs.get("min_size_mb", 0)
        older_than_days = kwargs.get("older_than_days", 0)

        if not self._validate_directory(path):
            return ToolResult(success=False, message=f"Directory not accessible: {path}")

        min_size_bytes = int(min_size_mb * 1024 * 1024) if min_size_mb else 0
        cutoff_time = None
        if older_than_days:
            cutoff_time = datetime.now() - timedelta(days=older_than_days)

        total_files = 0
        total_folders = 0
        total_size = 0
        type_breakdown: dict[str, int] = {}
        matched_files = 0

        try:
            if recursive:
                for dirpath, dirnames, filenames in os.walk(path):
                    total_folders += len(dirnames)
                    for fname in filenames:
                        fpath = os.path.join(dirpath, fname)
                        total_files += 1

                        if self._matches_filter(
                            fpath, fname, extension, min_size_bytes, cutoff_time
                        ):
                            matched_files += 1
                            try:
                                total_size += os.path.getsize(fpath)
                            except OSError:
                                pass

                        ext = Path(fname).suffix.lstrip(".").lower() or "(no ext)"
                        type_breakdown[ext] = type_breakdown.get(ext, 0) + 1
            else:
                for entry in os.scandir(path):
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            total_folders += 1
                        elif entry.is_file(follow_symlinks=False):
                            total_files += 1
                            if self._matches_filter(
                                entry.path, entry.name, extension,
                                min_size_bytes, cutoff_time,
                            ):
                                matched_files += 1
                                try:
                                    total_size += entry.stat().st_size
                                except OSError:
                                    pass

                            ext = Path(entry.name).suffix.lstrip(".").lower() or "(no ext)"
                            type_breakdown[ext] = type_breakdown.get(ext, 0) + 1
                    except (OSError, PermissionError):
                        continue

        except (OSError, PermissionError) as e:
            return ToolResult(success=False, message=f"Error scanning directory: {e}")

        # Sort breakdown by count
        sorted_breakdown = dict(
            sorted(type_breakdown.items(), key=lambda x: x[1], reverse=True)
        )

        from src.utils.path_utils import PathUtils
        has_filter = bool(extension or min_size_bytes or cutoff_time)

        data = {
            "total_files": total_files,
            "total_folders": total_folders,
            "matched_files": matched_files if has_filter else total_files,
            "total_size": total_size,
            "display_size": PathUtils.format_size(total_size),
            "type_breakdown": sorted_breakdown,
            "recursive": recursive,
        }

        # Build message
        parts = [f"Found {total_files} files and {total_folders} folders in {Path(path).name}"]
        if has_filter:
            parts.append(f"{matched_files} files match your filters")
        if sorted_breakdown:
            top_types = list(sorted_breakdown.items())[:5]
            type_str = ", ".join(f"{ext}: {count}" for ext, count in top_types)
            parts.append(f"Top types: {type_str}")

        return ToolResult(success=True, message=". ".join(parts), data=data)

    def _matches_filter(
        self,
        fpath: str,
        fname: str,
        extension: str,
        min_size_bytes: int,
        cutoff_time: datetime | None,
    ) -> bool:
        """Check if a file matches the given filters."""
        if extension:
            ext = Path(fname).suffix.lstrip(".").lower()
            if ext != extension.lower().lstrip("."):
                return False

        try:
            if min_size_bytes and os.path.getsize(fpath) < min_size_bytes:
                return False

            if cutoff_time:
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if mtime > cutoff_time:
                    return False
        except OSError:
            return False

        return True
