"""
OP(AI)UM — Regex Renamer Tool

Batch rename files using regex pattern matching.
Supports capture groups for advanced renaming.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from src.ai.tools.base_tool import BaseTool, ToolResult
from src.core.models import OperationRecord


class RegexRenamerTool(BaseTool):
    @property
    def name(self) -> str:
        return "regex_rename"

    @property
    def description(self) -> str:
        return (
            "Rename files using regex patterns. The pattern is matched against "
            "filenames, and the replacement string can use capture groups (\\1, \\2)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory containing files to rename",
                },
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to match against filenames",
                },
                "replacement": {
                    "type": "string",
                    "description": "Replacement string (supports \\1, \\2 for groups)",
                },
                "extension": {
                    "type": "string",
                    "description": "Only rename files with this extension",
                },
            },
            "required": ["directory", "pattern", "replacement"],
        }

    @property
    def is_destructive(self) -> bool:
        return True

    def preview(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        directory = kwargs.get("directory", "")
        pattern = kwargs.get("pattern", "")
        replacement = kwargs.get("replacement", "")
        extension = kwargs.get("extension", "")

        if not self._validate_directory(directory):
            return ToolResult(success=False, message=f"Directory not accessible: {directory}")

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return ToolResult(success=False, message=f"Invalid regex pattern: {e}")

        matches = []
        for entry in os.scandir(directory):
            try:
                if not entry.is_file(follow_symlinks=False):
                    continue
                if extension:
                    ext = Path(entry.name).suffix.lstrip(".").lower()
                    if ext != extension.lower().lstrip("."):
                        continue

                new_name = regex.sub(replacement, entry.name)
                if new_name != entry.name:
                    matches.append((entry.name, new_name))
            except OSError:
                continue

        if not matches:
            return ToolResult(success=False, message="No filenames match the pattern.")

        lines = [f"Will rename {len(matches)} file(s):"]
        for old, new in matches[:20]:
            lines.append(f"  {old}  →  {new}")
        if len(matches) > 20:
            lines.append(f"  ... and {len(matches) - 20} more")

        return ToolResult(
            success=True,
            message=f"Ready to regex rename {len(matches)} files",
            requires_approval=True,
            preview=lines,
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        directory = kwargs.get("directory", "")
        pattern = kwargs.get("pattern", "")
        replacement = kwargs.get("replacement", "")
        extension = kwargs.get("extension", "")

        if not self._validate_directory(directory):
            return ToolResult(success=False, message=f"Directory not accessible: {directory}")

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return ToolResult(success=False, message=f"Invalid regex: {e}")

        succeeded = 0
        failed = 0
        source_paths = []
        dest_paths = []
        original_names = []
        new_names = []

        for entry in os.scandir(directory):
            try:
                if not entry.is_file(follow_symlinks=False):
                    continue
                if extension:
                    ext = Path(entry.name).suffix.lstrip(".").lower()
                    if ext != extension.lower().lstrip("."):
                        continue

                new_name = regex.sub(replacement, entry.name)
                if new_name == entry.name:
                    continue

                new_path = os.path.join(directory, new_name)
                if os.path.exists(new_path):
                    logger.warning(f"Regex rename skip: {new_name} already exists")
                    failed += 1
                    continue

                os.rename(entry.path, new_path)
                succeeded += 1
                source_paths.append(entry.path)
                dest_paths.append(new_path)
                original_names.append(entry.name)
                new_names.append(new_name)

            except OSError as e:
                logger.error(f"Regex rename failed: {entry.name}: {e}")
                failed += 1

        operation = OperationRecord(
            timestamp=datetime.now(),
            operation_type="regex_rename",
            description=f"Regex renamed {succeeded} files (/{pattern}/ → {replacement})",
            source_paths=source_paths,
            dest_paths=dest_paths,
            original_names=original_names,
            new_names=new_names,
            is_undoable=True,
        )

        message = f"Renamed {succeeded} file(s) using pattern."
        if failed:
            message += f" {failed} failed."

        return ToolResult(
            success=succeeded > 0,
            message=message,
            data={"succeeded": succeeded, "failed": failed},
            operation=operation,
        )
