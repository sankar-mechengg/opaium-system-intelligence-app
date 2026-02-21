"""
OP(AI)UM — Folder Flattener Tool

Moves all files from nested subfolders into the parent directory,
effectively un-nesting a folder structure.
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


class FolderFlattenerTool(BaseTool):

    @property
    def name(self) -> str:
        return "flatten_folder"

    @property
    def description(self) -> str:
        return (
            "Move all files from subfolders into the parent folder. "
            "Un-nests a directory structure by pulling all files to the top level."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Parent directory to flatten",
                },
                "remove_empty": {
                    "type": "boolean",
                    "description": "Remove empty subfolders after flattening",
                    "default": True,
                },
            },
            "required": ["path"],
        }

    @property
    def is_destructive(self) -> bool:
        return True

    def preview(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        path = kwargs.get("path", "")

        if not self._validate_directory(path):
            return ToolResult(success=False, message=f"Directory not accessible: {path}")

        files_to_move = []
        for dirpath, _, filenames in os.walk(path):
            if dirpath == path:
                continue
            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                rel = os.path.relpath(fpath, path)
                files_to_move.append(rel)

        if not files_to_move:
            return ToolResult(success=True, message="No nested files to flatten.")

        lines = [f"Will move {len(files_to_move)} files to {Path(path).name}/:"]
        for f in files_to_move[:20]:
            lines.append(f"  {f}  →  {Path(f).name}")
        if len(files_to_move) > 20:
            lines.append(f"  ... and {len(files_to_move) - 20} more")

        return ToolResult(
            success=True,
            message=f"Ready to flatten {len(files_to_move)} files",
            requires_approval=True,
            preview=lines,
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        path = kwargs.get("path", "")
        remove_empty = kwargs.get("remove_empty", True)

        if not self._validate_directory(path):
            return ToolResult(success=False, message=f"Directory not accessible: {path}")

        moved = 0
        failed = 0
        source_paths = []
        dest_paths = []

        for dirpath, _, filenames in os.walk(path):
            if dirpath == path:
                continue
            for fname in filenames:
                src = os.path.join(dirpath, fname)
                dest = os.path.join(path, fname)

                try:
                    if os.path.exists(dest):
                        base, ext = os.path.splitext(fname)
                        counter = 1
                        while os.path.exists(dest):
                            dest = os.path.join(path, f"{base} ({counter}){ext}")
                            counter += 1

                    shutil.move(src, dest)
                    moved += 1
                    source_paths.append(src)
                    dest_paths.append(dest)
                except (OSError, shutil.Error) as e:
                    logger.error(f"Flatten move failed: {src}: {e}")
                    failed += 1

        # Remove empty directories
        removed_dirs = 0
        if remove_empty:
            for dirpath, dirnames, filenames in os.walk(path, topdown=False):
                if dirpath == path:
                    continue
                try:
                    if not os.listdir(dirpath):
                        os.rmdir(dirpath)
                        removed_dirs += 1
                except OSError:
                    pass

        operation = OperationRecord(
            timestamp=datetime.now(),
            operation_type="flatten",
            description=f"Flattened {moved} files in {Path(path).name}",
            source_paths=source_paths,
            dest_paths=dest_paths,
            is_undoable=True,
        )

        message = f"Flattened {moved} files to top level."
        if removed_dirs:
            message += f" Removed {removed_dirs} empty folders."
        if failed:
            message += f" {failed} failed."

        return ToolResult(success=moved > 0, message=message, operation=operation)
