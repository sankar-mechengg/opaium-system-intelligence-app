"""
OP(AI)UM — Date Organizer Tool

Organizes files into date-based subfolders (YYYY-MM format).
Ideal for photos, screenshots, and downloaded files.
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


class DateOrganizerTool(BaseTool):
    @property
    def name(self) -> str:
        return "organize_by_date"

    @property
    def description(self) -> str:
        return (
            "Organize files into subfolders by date. Creates folders like "
            "2024-01/, 2024-02/ based on file modification date."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory to organize",
                },
                "format": {
                    "type": "string",
                    "enum": ["year", "year-month", "year-month-day"],
                    "description": "Folder naming format",
                    "default": "year-month",
                },
                "extension": {
                    "type": "string",
                    "description": "Only organize files with this extension",
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
        fmt = kwargs.get("format", "year-month")
        extension = kwargs.get("extension", "")

        if not self._validate_directory(path):
            return ToolResult(success=False, message=f"Directory not accessible: {path}")

        plan: dict[str, list[str]] = {}

        for entry in os.scandir(path):
            try:
                if not entry.is_file(follow_symlinks=False):
                    continue
                if extension:
                    ext = Path(entry.name).suffix.lstrip(".").lower()
                    if ext != extension.lower().lstrip("."):
                        continue

                mtime = datetime.fromtimestamp(entry.stat().st_mtime)
                folder_name = self._get_folder_name(mtime, fmt)
                plan.setdefault(folder_name, []).append(entry.name)
            except OSError:
                continue

        if not plan:
            return ToolResult(success=False, message="No files to organize.")

        total = sum(len(v) for v in plan.values())
        lines = [f"Will organize {total} files into {len(plan)} date folders:"]
        for folder in sorted(plan.keys()):
            files = plan[folder]
            lines.append(f"  📁 {folder}/ ({len(files)} files)")

        return ToolResult(
            success=True,
            message=f"Ready to organize {total} files by date",
            requires_approval=True,
            preview=lines,
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        path = kwargs.get("path", "")
        fmt = kwargs.get("format", "year-month")
        extension = kwargs.get("extension", "")

        if not self._validate_directory(path):
            return ToolResult(success=False, message=f"Directory not accessible: {path}")

        moved = 0
        failed = 0
        source_paths = []
        dest_paths = []

        for entry in os.scandir(path):
            try:
                if not entry.is_file(follow_symlinks=False):
                    continue
                if extension:
                    ext = Path(entry.name).suffix.lstrip(".").lower()
                    if ext != extension.lower().lstrip("."):
                        continue

                mtime = datetime.fromtimestamp(entry.stat().st_mtime)
                folder_name = self._get_folder_name(mtime, fmt)
                dest_dir = os.path.join(path, folder_name)

                os.makedirs(dest_dir, exist_ok=True)

                dest_path = os.path.join(dest_dir, entry.name)
                if os.path.exists(dest_path):
                    base, fext = os.path.splitext(entry.name)
                    counter = 1
                    while os.path.exists(dest_path):
                        dest_path = os.path.join(dest_dir, f"{base} ({counter}){fext}")
                        counter += 1

                shutil.move(entry.path, dest_path)
                moved += 1
                source_paths.append(entry.path)
                dest_paths.append(dest_path)

            except (OSError, shutil.Error) as e:
                logger.error(f"Date organize failed for {entry.name}: {e}")
                failed += 1

        operation = OperationRecord(
            timestamp=datetime.now(),
            operation_type="organize_date",
            description=f"Organized {moved} files by date in {Path(path).name}",
            source_paths=source_paths,
            dest_paths=dest_paths,
            is_undoable=True,
        )

        message = f"Organized {moved} files into date-based folders."
        if failed:
            message += f" {failed} failed."

        return ToolResult(success=moved > 0, message=message, operation=operation)

    @staticmethod
    def _get_folder_name(dt: datetime, fmt: str) -> str:
        if fmt == "year":
            return dt.strftime("%Y")
        elif fmt == "year-month-day":
            return dt.strftime("%Y-%m-%d")
        else:
            return dt.strftime("%Y-%m")
