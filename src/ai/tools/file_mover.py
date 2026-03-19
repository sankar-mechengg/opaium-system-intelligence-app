"""
OP(AI)UM — File Mover Tool

Moves files from one location to another. Supports selective
and batch moves with full undo tracking.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from src.ai.tools.base_tool import BaseTool, ToolResult
from src.core.models import OperationRecord


class FileMoverTool(BaseTool):
    @property
    def name(self) -> str:
        return "move_files"

    @property
    def description(self) -> str:
        return (
            "Move files from source directory to destination directory. "
            "Can move specific files by name or filter by extension."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source_directory": {
                    "type": "string",
                    "description": "Source directory containing files to move",
                },
                "destination_directory": {
                    "type": "string",
                    "description": "Destination directory to move files to",
                },
                "filenames": {
                    "type": "array",
                    "description": "Specific filenames to move (if empty, uses filters)",
                    "items": {"type": "string"},
                },
                "extension": {
                    "type": "string",
                    "description": "Move all files with this extension",
                },
                "create_dest": {
                    "type": "boolean",
                    "description": "Create destination directory if it doesn't exist",
                    "default": True,
                },
            },
            "required": ["source_directory", "destination_directory"],
        }

    @property
    def is_destructive(self) -> bool:
        return True

    def preview(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        source = kwargs.get("source_directory", "")
        dest = kwargs.get("destination_directory", "")
        files = self._collect_targets(**kwargs)

        if not files:
            return ToolResult(success=False, message="No files match the criteria.")

        from src.utils.path_utils import PathUtils

        total_size = sum(os.path.getsize(f) for f in files if os.path.exists(f))

        preview_lines = [
            f"Will move {len(files)} file(s) ({PathUtils.format_size(total_size)}):",
            f"  From: {source}",
            f"  To:   {dest}",
            "",
        ]

        for f in files[:15]:
            preview_lines.append(f"  {Path(f).name}")
        if len(files) > 15:
            preview_lines.append(f"  ... and {len(files) - 15} more")

        return ToolResult(
            success=True,
            message=f"Ready to move {len(files)} files",
            requires_approval=True,
            preview=preview_lines,
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        dest = kwargs.get("destination_directory", "")
        create_dest = kwargs.get("create_dest", True)
        files = self._collect_targets(**kwargs)

        if not files:
            return ToolResult(success=False, message="No files match the criteria.")

        # Create destination if needed
        if create_dest and not os.path.exists(dest):
            try:
                os.makedirs(dest, exist_ok=True)
                logger.info(f"Created directory: {dest}")
            except OSError as e:
                return ToolResult(success=False, message=f"Cannot create destination: {e}")

        if not os.path.isdir(dest):
            return ToolResult(success=False, message=f"Destination is not a directory: {dest}")

        succeeded = 0
        failed = 0
        source_paths = []
        dest_paths = []

        for fpath in files:
            fname = Path(fpath).name
            dest_path = os.path.join(dest, fname)

            try:
                # Handle name conflicts
                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(fname)
                    counter = 1
                    while os.path.exists(dest_path):
                        dest_path = os.path.join(dest, f"{base} ({counter}){ext}")
                        counter += 1

                shutil.move(fpath, dest_path)
                succeeded += 1
                source_paths.append(fpath)
                dest_paths.append(dest_path)
                logger.info(f"Moved: {fpath} -> {dest_path}")

            except (OSError, shutil.Error) as e:
                logger.error(f"Move failed: {fpath}: {e}")
                failed += 1

        operation = OperationRecord(
            timestamp=datetime.now(),
            operation_type="move",
            description=f"Moved {succeeded} files to {Path(dest).name}",
            source_paths=source_paths,
            dest_paths=dest_paths,
            is_undoable=True,
        )

        message = f"Moved {succeeded} file(s) successfully."
        if failed:
            message += f" {failed} failed."

        return ToolResult(
            success=succeeded > 0,
            message=message,
            data={"succeeded": succeeded, "failed": failed},
            operation=operation,
        )

    def _collect_targets(self, **kwargs: Any) -> list[str]:
        """Collect files to move."""
        source = kwargs.get("source_directory", "")
        filenames = kwargs.get("filenames", [])
        extension = kwargs.get("extension", "")

        if not self._validate_directory(source):
            return []

        targets: list[str] = []

        if filenames:
            for fname in filenames:
                fpath = os.path.join(source, fname)
                if os.path.isfile(fpath):
                    targets.append(fpath)
        else:
            for entry in os.scandir(source):
                try:
                    if not entry.is_file(follow_symlinks=False):
                        continue
                    if extension:
                        ext = Path(entry.name).suffix.lstrip(".").lower()
                        if ext != extension.lower().lstrip("."):
                            continue
                    targets.append(entry.path)
                except (OSError, PermissionError):
                    continue

        return targets
