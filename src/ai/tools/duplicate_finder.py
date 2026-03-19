"""
OP(AI)UM — Duplicate File Finder Tool

Finds exact duplicate files using MD5 hash comparison.
Groups duplicates and reports total wasted space.
"""

from __future__ import annotations

import hashlib
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.ai.tools.base_tool import BaseTool, ToolResult
from src.utils.path_utils import PathUtils


class DuplicateFinderTool(BaseTool):
    @property
    def name(self) -> str:
        return "find_duplicates"

    @property
    def description(self) -> str:
        return (
            "Find duplicate files in a directory by comparing file hashes. "
            "Reports groups of identical files and total wasted space."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory to scan for duplicates",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Include subdirectories",
                    "default": True,
                },
                "min_size_kb": {
                    "type": "number",
                    "description": "Minimum file size in KB to consider (skip tiny files)",
                    "default": 1,
                },
                "extension": {
                    "type": "string",
                    "description": "Only check files with this extension",
                },
            },
            "required": ["path"],
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        path = kwargs.get("path", "")
        recursive = kwargs.get("recursive", True)
        min_size_kb = kwargs.get("min_size_kb", 1)
        extension = kwargs.get("extension", "")

        if not self._validate_directory(path):
            return ToolResult(success=False, message=f"Directory not accessible: {path}")

        min_size = int(min_size_kb * 1024)

        # Phase 1: Group by file size (quick filter)
        size_groups: dict[int, list[str]] = defaultdict(list)
        file_count = 0

        try:
            walker = os.walk(path) if recursive else [(path, [], os.listdir(path))]
            for dirpath, _, filenames in walker:
                for fname in filenames:
                    fpath = os.path.join(dirpath, fname)
                    if not os.path.isfile(fpath):
                        continue

                    if extension:
                        ext = Path(fname).suffix.lstrip(".").lower()
                        if ext != extension.lower().lstrip("."):
                            continue

                    try:
                        size = os.path.getsize(fpath)
                        if size >= min_size:
                            size_groups[size].append(fpath)
                            file_count += 1
                    except OSError:
                        continue
        except (OSError, PermissionError) as e:
            return ToolResult(success=False, message=f"Error scanning: {e}")

        # Phase 2: Hash files that share the same size
        hash_groups: dict[str, list[str]] = defaultdict(list)
        files_hashed = 0

        for _size, file_list in size_groups.items():
            if len(file_list) < 2:
                continue

            for fpath in file_list:
                file_hash = self._quick_hash(fpath)
                if file_hash:
                    hash_groups[file_hash].append(fpath)
                    files_hashed += 1

        # Phase 3: Collect duplicate groups
        duplicate_groups = []
        total_wasted = 0

        for hash_val, file_list in hash_groups.items():
            if len(file_list) < 2:
                continue

            file_size = os.path.getsize(file_list[0]) if os.path.exists(file_list[0]) else 0
            wasted = file_size * (len(file_list) - 1)
            total_wasted += wasted

            duplicate_groups.append(
                {
                    "hash": hash_val[:12],
                    "size_bytes": file_size,
                    "display_size": PathUtils.format_size(file_size),
                    "count": len(file_list),
                    "files": [str(f) for f in file_list],
                    "wasted_bytes": wasted,
                }
            )

        duplicate_groups.sort(key=lambda g: g["wasted_bytes"], reverse=True)

        total_duplicates = sum(g["count"] - 1 for g in duplicate_groups)

        message_parts = [
            f"Scanned {file_count} files in {Path(path).name}.",
        ]

        if duplicate_groups:
            message_parts.append(
                f"Found {len(duplicate_groups)} groups of duplicates "
                f"({total_duplicates} extra copies, "
                f"{PathUtils.format_size(total_wasted)} wasted)."
            )
            for i, group in enumerate(duplicate_groups[:5]):
                message_parts.append(
                    f"  Group {i + 1}: {group['count']} copies of "
                    f"{Path(group['files'][0]).name} ({group['display_size']} each)"
                )
        else:
            message_parts.append("No duplicate files found.")

        return ToolResult(
            success=True,
            message=" ".join(message_parts) if not duplicate_groups else "\n".join(message_parts),
            data={
                "files_scanned": file_count,
                "files_hashed": files_hashed,
                "duplicate_groups": duplicate_groups,
                "total_duplicates": total_duplicates,
                "wasted_bytes": total_wasted,
                "wasted_display": PathUtils.format_size(total_wasted),
            },
        )

    def _quick_hash(self, fpath: str, chunk_size: int = 8192) -> str | None:
        """Hash a file using MD5 for duplicate detection."""
        try:
            hasher = hashlib.md5()
            with open(fpath, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (OSError, PermissionError):
            return None
