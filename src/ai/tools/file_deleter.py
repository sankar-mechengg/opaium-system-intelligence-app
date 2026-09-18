"""
OP(AI)UM — File Deleter Tool

Deletes files by moving them to the Recycle Bin (recoverable).
Supports selective and batch deletion with undo support.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger
from send2trash import send2trash

from src.ai.tools.base_tool import BaseTool, ToolResult
from src.core.models import OperationRecord


class FileDeleterTool(BaseTool):
    @property
    def name(self) -> str:
        return "delete_files"

    @property
    def description(self) -> str:
        return (
            "Delete files by moving them to the Recycle Bin. Files can be recovered "
            "from the Recycle Bin if needed. Provide file names or patterns."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory containing the files to delete",
                },
                "filenames": {
                    "type": "array",
                    "description": "List of specific filenames to delete",
                    "items": {"type": "string"},
                },
                "extension": {
                    "type": "string",
                    "description": "Delete all files with this extension (e.g., 'tmp')",
                },
                "older_than_days": {
                    "type": "integer",
                    "description": "Delete files older than N days",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Include subdirectories",
                    "default": False,
                },
            },
            "required": ["directory"],
        }

    @property
    def is_destructive(self) -> bool:
        return True

    def preview(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)
        files = self._collect_targets(**kwargs)

        if not files:
            return ToolResult(success=False, message="No files match the criteria.")

        from src.utils.path_utils import PathUtils

        total_size = sum(os.path.getsize(f) for f in files if os.path.exists(f))

        preview_lines = [
            f"Will delete {len(files)} file(s) to Recycle Bin ({PathUtils.format_size(total_size)} total):",
        ]

        for f in files[:20]:
            size = PathUtils.format_size(os.path.getsize(f)) if os.path.exists(f) else "?"
            preview_lines.append(f"  {Path(f).name}  ({size})")

        if len(files) > 20:
            preview_lines.append(f"  ... and {len(files) - 20} more")

        return ToolResult(
            success=True,
            message=f"Ready to delete {len(files)} files",
            requires_approval=True,
            preview=preview_lines,
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)
        files = self._collect_targets(**kwargs)

        if not files:
            return ToolResult(success=False, message="No files match the criteria.")

        succeeded = 0
        failed = 0
        deleted_paths = []

        for fpath in files:
            try:
                send2trash(fpath)
                succeeded += 1
                deleted_paths.append(fpath)
                logger.info(f"Deleted to Recycle Bin: {fpath}")
            except Exception as e:
                logger.error(f"Delete failed: {fpath}: {e}")
                failed += 1

        operation = OperationRecord(
            timestamp=datetime.now(),
            operation_type="delete",
            description=f"Deleted {succeeded} files to Recycle Bin",
            source_paths=deleted_paths,
            is_undoable=True,  # Restored from the Recycle Bin via Shell COM
            metadata={"method": "recycle_bin"},
        )

        message = f"Deleted {succeeded} file(s) to Recycle Bin."
        if failed:
            message += f" {failed} failed."

        return ToolResult(
            success=succeeded > 0,
            message=message,
            data={"succeeded": succeeded, "failed": failed},
            operation=operation,
        )

    def _collect_targets(self, **kwargs: Any) -> list[str]:
        """Collect files matching the deletion criteria."""
        directory = kwargs.get("directory", "")
        filenames = kwargs.get("filenames", [])
        extension = kwargs.get("extension", "")
        older_than_days = kwargs.get("older_than_days", 0)
        recursive = kwargs.get("recursive", False)

        if not self._validate_directory(directory):
            return []

        targets: list[str] = []

        if filenames:
            for fname in filenames:
                fpath = os.path.join(directory, fname)
                if os.path.isfile(fpath):
                    targets.append(fpath)
        else:
            from datetime import timedelta

            cutoff = None
            if older_than_days:
                cutoff = datetime.now() - timedelta(days=older_than_days)

            walker = os.walk(directory) if recursive else [(directory, [], os.listdir(directory))]
            for dirpath, _, fnames in walker:
                for fname in fnames:
                    fpath = os.path.join(dirpath, fname)
                    if not os.path.isfile(fpath):
                        continue

                    if extension:
                        ext = Path(fname).suffix.lstrip(".").lower()
                        if ext != extension.lower().lstrip("."):
                            continue

                    if cutoff:
                        try:
                            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                            if mtime > cutoff:
                                continue
                        except OSError:
                            continue

                    targets.append(fpath)

        return targets
