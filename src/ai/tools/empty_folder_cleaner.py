"""
OP(AI)UM — Empty Folder Cleaner Tool

Finds and removes empty directories. Scans recursively
to detect nested empty folder structures.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from src.ai.tools.base_tool import BaseTool, ToolResult
from src.core.models import OperationRecord


class EmptyFolderCleanerTool(BaseTool):
    @property
    def name(self) -> str:
        return "clean_empty_folders"

    @property
    def description(self) -> str:
        return "Find and remove empty folders in a directory. Scans recursively to find nested empty folder trees."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory to scan for empty folders",
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, only report empty folders without deleting",
                    "default": True,
                },
            },
            "required": ["path"],
        }

    @property
    def is_destructive(self) -> bool:
        return True

    def preview(self, **kwargs: Any) -> ToolResult:
        kwargs["dry_run"] = True
        return self.execute(**kwargs)

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        path = kwargs.get("path", "")
        dry_run = kwargs.get("dry_run", True)

        if not self._validate_directory(path):
            return ToolResult(success=False, message=f"Directory not accessible: {path}")

        empty_dirs = self._find_empty(path)

        if not empty_dirs:
            return ToolResult(
                success=True,
                message=f"No empty folders found in {Path(path).name}.",
                data={"count": 0, "folders": []},
            )

        if dry_run:
            lines = [f"Found {len(empty_dirs)} empty folder(s) in {Path(path).name}:"]
            for d in empty_dirs[:30]:
                rel = os.path.relpath(d, path)
                lines.append(f"  📁 {rel}")
            if len(empty_dirs) > 30:
                lines.append(f"  ... and {len(empty_dirs) - 30} more")

            return ToolResult(
                success=True,
                message="\n".join(lines),
                requires_approval=True,
                preview=lines,
                data={"count": len(empty_dirs), "folders": empty_dirs},
            )

        # Execute deletion
        removed = 0
        failed = 0
        removed_paths = []

        # Remove bottom-up
        for d in sorted(empty_dirs, key=len, reverse=True):
            try:
                os.rmdir(d)
                removed += 1
                removed_paths.append(d)
                logger.info(f"Removed empty folder: {d}")
            except OSError as e:
                logger.debug(f"Could not remove {d}: {e}")
                failed += 1

        operation = OperationRecord(
            timestamp=datetime.now(),
            operation_type="clean_empty",
            description=f"Removed {removed} empty folders from {Path(path).name}",
            source_paths=removed_paths,
            is_undoable=True,  # Undo recreates the (empty) folders
        )

        message = f"Removed {removed} empty folder(s)."
        if failed:
            message += f" {failed} could not be removed."

        return ToolResult(
            success=removed > 0,
            message=message,
            data={"removed": removed, "failed": failed},
            operation=operation,
        )

    def _find_empty(self, path: str) -> list[str]:
        """Find all empty directories recursively."""
        empty = []
        for dirpath, dirnames, filenames in os.walk(path, topdown=False):
            if dirpath == path:
                continue
            if (
                not dirnames
                and not filenames
                or all(os.path.join(dirpath, d) in empty for d in dirnames)
                and not filenames
            ):
                empty.append(dirpath)
        return empty
