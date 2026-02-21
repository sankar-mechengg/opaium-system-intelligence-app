"""
OP(AI)UM — File Renamer Tool

Renames files selectively or in batch. Supports pattern-based
renaming and integrates with the undo journal.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from src.ai.tools.base_tool import BaseTool, ToolResult
from src.core.models import OperationRecord


class FileRenamerTool(BaseTool):

    @property
    def name(self) -> str:
        return "rename_files"

    @property
    def description(self) -> str:
        return (
            "Rename one or more files. Provide a list of current names and their "
            "new names. All files must be in the same directory."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory containing the files",
                },
                "renames": {
                    "type": "array",
                    "description": "List of rename operations",
                    "items": {
                        "type": "object",
                        "properties": {
                            "old_name": {"type": "string", "description": "Current filename"},
                            "new_name": {"type": "string", "description": "New filename"},
                        },
                        "required": ["old_name", "new_name"],
                    },
                },
            },
            "required": ["directory", "renames"],
        }

    @property
    def is_destructive(self) -> bool:
        return True

    def preview(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        directory = kwargs.get("directory", "")
        renames = kwargs.get("renames", [])

        if not self._validate_directory(directory):
            return ToolResult(success=False, message=f"Directory not accessible: {directory}")

        preview_lines = [f"Will rename {len(renames)} file(s) in {Path(directory).name}:"]
        errors = []

        for r in renames:
            old_name = r.get("old_name", "")
            new_name = r.get("new_name", "")
            old_path = os.path.join(directory, old_name)
            new_path = os.path.join(directory, new_name)

            if not os.path.exists(old_path):
                errors.append(f"  Not found: {old_name}")
            elif os.path.exists(new_path):
                errors.append(f"  Already exists: {new_name}")
            else:
                preview_lines.append(f"  {old_name}  →  {new_name}")

        if errors:
            preview_lines.append("\nIssues:")
            preview_lines.extend(errors)

        return ToolResult(
            success=True,
            message=f"Ready to rename {len(renames)} files",
            requires_approval=True,
            preview=preview_lines,
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        directory = kwargs.get("directory", "")
        renames = kwargs.get("renames", [])

        if not self._validate_directory(directory):
            return ToolResult(success=False, message=f"Directory not accessible: {directory}")

        if not renames:
            return ToolResult(success=False, message="No rename operations provided.")

        succeeded = 0
        failed = 0
        source_paths = []
        dest_paths = []
        original_names = []
        new_names = []

        for r in renames:
            old_name = r.get("old_name", "")
            new_name = r.get("new_name", "")
            old_path = os.path.join(directory, old_name)
            new_path = os.path.join(directory, new_name)

            try:
                if not os.path.exists(old_path):
                    logger.warning(f"Rename skip: {old_path} not found")
                    failed += 1
                    continue

                if os.path.exists(new_path):
                    logger.warning(f"Rename skip: {new_path} already exists")
                    failed += 1
                    continue

                os.rename(old_path, new_path)
                succeeded += 1
                source_paths.append(old_path)
                dest_paths.append(new_path)
                original_names.append(old_name)
                new_names.append(new_name)
                logger.info(f"Renamed: {old_name} -> {new_name}")

            except OSError as e:
                logger.error(f"Rename failed: {old_name} -> {new_name}: {e}")
                failed += 1

        # Create undo record
        operation = OperationRecord(
            timestamp=datetime.now(),
            operation_type="rename",
            description=f"Renamed {succeeded} files in {Path(directory).name}",
            source_paths=source_paths,
            dest_paths=dest_paths,
            original_names=original_names,
            new_names=new_names,
            is_undoable=True,
        )

        message = f"Renamed {succeeded} file(s) successfully."
        if failed:
            message += f" {failed} failed."

        return ToolResult(
            success=succeeded > 0,
            message=message,
            data={"succeeded": succeeded, "failed": failed},
            operation=operation,
        )
