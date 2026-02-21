"""
OP(AI)UM — Extension Changer Tool

Batch-rename file extensions (e.g., .jpeg → .jpg, .htm → .html).
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from src.ai.tools.base_tool import BaseTool, ToolResult
from src.core.models import OperationRecord


class ExtensionChangerTool(BaseTool):

    @property
    def name(self) -> str:
        return "change_extensions"

    @property
    def description(self) -> str:
        return "Change file extensions in batch (e.g., rename all .jpeg to .jpg)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory containing files",
                },
                "from_ext": {
                    "type": "string",
                    "description": "Current extension to match (e.g., 'jpeg')",
                },
                "to_ext": {
                    "type": "string",
                    "description": "New extension (e.g., 'jpg')",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Include subdirectories",
                    "default": False,
                },
            },
            "required": ["directory", "from_ext", "to_ext"],
        }

    @property
    def is_destructive(self) -> bool:
        return True

    def preview(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)
        files = self._collect_targets(**kwargs)
        from_ext = kwargs.get("from_ext", "").lstrip(".")
        to_ext = kwargs.get("to_ext", "").lstrip(".")

        if not files:
            return ToolResult(success=False, message=f"No .{from_ext} files found.")

        lines = [f"Will change extension on {len(files)} file(s): .{from_ext} → .{to_ext}"]
        for f in files[:15]:
            old_name = Path(f).name
            new_name = Path(f).stem + f".{to_ext}"
            lines.append(f"  {old_name}  →  {new_name}")
        if len(files) > 15:
            lines.append(f"  ... and {len(files) - 15} more")

        return ToolResult(
            success=True, message=f"Ready to change {len(files)} extensions",
            requires_approval=True, preview=lines,
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        to_ext = kwargs.get("to_ext", "").lstrip(".")
        files = self._collect_targets(**kwargs)

        if not files:
            return ToolResult(success=False, message="No matching files found.")

        succeeded = 0
        failed = 0
        source_paths = []
        dest_paths = []
        original_names = []
        new_names = []

        for fpath in files:
            try:
                p = Path(fpath)
                new_name = p.stem + f".{to_ext}"
                new_path = str(p.parent / new_name)

                if os.path.exists(new_path) and new_path != fpath:
                    failed += 1
                    continue

                os.rename(fpath, new_path)
                succeeded += 1
                source_paths.append(fpath)
                dest_paths.append(new_path)
                original_names.append(p.name)
                new_names.append(new_name)

            except OSError as e:
                logger.error(f"Extension change failed: {fpath}: {e}")
                failed += 1

        operation = OperationRecord(
            timestamp=datetime.now(),
            operation_type="extension_change",
            description=f"Changed extension on {succeeded} files to .{to_ext}",
            source_paths=source_paths,
            dest_paths=dest_paths,
            original_names=original_names,
            new_names=new_names,
            is_undoable=True,
        )

        message = f"Changed extension on {succeeded} file(s)."
        if failed:
            message += f" {failed} failed."

        return ToolResult(success=succeeded > 0, message=message, operation=operation)

    def _collect_targets(self, **kwargs: Any) -> list[str]:
        directory = kwargs.get("directory", "")
        from_ext = kwargs.get("from_ext", "").lstrip(".")
        recursive = kwargs.get("recursive", False)

        if not self._validate_directory(directory):
            return []

        targets = []
        walker = os.walk(directory) if recursive else [(directory, [], os.listdir(directory))]
        for dirpath, _, filenames in walker:
            for fname in filenames:
                if Path(fname).suffix.lstrip(".").lower() == from_ext.lower():
                    targets.append(os.path.join(dirpath, fname))
        return targets
