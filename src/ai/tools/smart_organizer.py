"""
OP(AI)UM — Smart Organizer Tool

Automatically organizes files into subfolders by type.
Creates folders like Images/, Documents/, Videos/ and
sorts files into them by extension.
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


class SmartOrganizerTool(BaseTool):
    # Extension → Folder mapping
    CATEGORY_MAP: dict[str, str] = {
        # Images
        "jpg": "Images",
        "jpeg": "Images",
        "png": "Images",
        "gif": "Images",
        "bmp": "Images",
        "webp": "Images",
        "svg": "Images",
        "ico": "Images",
        "tiff": "Images",
        "tif": "Images",
        "raw": "Images",
        "heic": "Images",
        # Documents
        "pdf": "Documents",
        "doc": "Documents",
        "docx": "Documents",
        "xls": "Documents",
        "xlsx": "Documents",
        "ppt": "Documents",
        "pptx": "Documents",
        "txt": "Documents",
        "rtf": "Documents",
        "odt": "Documents",
        "ods": "Documents",
        "odp": "Documents",
        "csv": "Documents",
        "md": "Documents",
        # Videos
        "mp4": "Videos",
        "avi": "Videos",
        "mkv": "Videos",
        "mov": "Videos",
        "wmv": "Videos",
        "flv": "Videos",
        "webm": "Videos",
        "m4v": "Videos",
        # Audio
        "mp3": "Audio",
        "wav": "Audio",
        "flac": "Audio",
        "aac": "Audio",
        "ogg": "Audio",
        "wma": "Audio",
        "m4a": "Audio",
        # Archives
        "zip": "Archives",
        "rar": "Archives",
        "7z": "Archives",
        "tar": "Archives",
        "gz": "Archives",
        "bz2": "Archives",
        # Code
        "py": "Code",
        "js": "Code",
        "ts": "Code",
        "html": "Code",
        "css": "Code",
        "java": "Code",
        "cpp": "Code",
        "c": "Code",
        "h": "Code",
        "rs": "Code",
        "go": "Code",
        "rb": "Code",
        "php": "Code",
        "swift": "Code",
        "kt": "Code",
        "json": "Code",
        "xml": "Code",
        "yaml": "Code",
        "yml": "Code",
        # Executables
        "exe": "Programs",
        "msi": "Programs",
        "bat": "Programs",
        "cmd": "Programs",
        "ps1": "Programs",
        "sh": "Programs",
        # Fonts
        "ttf": "Fonts",
        "otf": "Fonts",
        "woff": "Fonts",
        "woff2": "Fonts",
    }

    @property
    def name(self) -> str:
        return "organize_by_type"

    @property
    def description(self) -> str:
        return (
            "Organize files in a directory into subfolders by type. "
            "Creates folders like Images/, Documents/, Videos/ and sorts "
            "files into them automatically."
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
                "custom_mapping": {
                    "type": "object",
                    "description": "Optional custom extension->folder mapping to override defaults",
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
        custom = kwargs.get("custom_mapping", {})

        if not self._validate_directory(path):
            return ToolResult(success=False, message=f"Directory not accessible: {path}")

        mapping = {**self.CATEGORY_MAP, **custom}
        plan: dict[str, list[str]] = {}

        for entry in os.scandir(path):
            try:
                if not entry.is_file(follow_symlinks=False):
                    continue
                ext = Path(entry.name).suffix.lstrip(".").lower()
                category = mapping.get(ext, "Other")
                plan.setdefault(category, []).append(entry.name)
            except OSError:
                continue

        if not plan:
            return ToolResult(success=False, message="No files to organize.")

        total = sum(len(v) for v in plan.values())
        lines = [f"Will organize {total} files into {len(plan)} folders:"]
        for category in sorted(plan.keys()):
            files = plan[category]
            lines.append(f"  📁 {category}/ ({len(files)} files)")
            for f in files[:5]:
                lines.append(f"      {f}")
            if len(files) > 5:
                lines.append(f"      ... and {len(files) - 5} more")

        return ToolResult(
            success=True,
            message=f"Ready to organize {total} files",
            requires_approval=True,
            preview=lines,
            data=plan,
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        path = kwargs.get("path", "")
        custom = kwargs.get("custom_mapping", {})

        if not self._validate_directory(path):
            return ToolResult(success=False, message=f"Directory not accessible: {path}")

        mapping = {**self.CATEGORY_MAP, **custom}
        moved = 0
        failed = 0
        source_paths = []
        dest_paths = []

        for entry in os.scandir(path):
            try:
                if not entry.is_file(follow_symlinks=False):
                    continue

                ext = Path(entry.name).suffix.lstrip(".").lower()
                category = mapping.get(ext, "Other")
                dest_dir = os.path.join(path, category)

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
                logger.error(f"Organize failed for {entry.name}: {e}")
                failed += 1

        operation = OperationRecord(
            timestamp=datetime.now(),
            operation_type="organize",
            description=f"Organized {moved} files by type in {Path(path).name}",
            source_paths=source_paths,
            dest_paths=dest_paths,
            is_undoable=True,
        )

        message = f"Organized {moved} files into type-based folders."
        if failed:
            message += f" {failed} failed."

        return ToolResult(
            success=moved > 0,
            message=message,
            data={"moved": moved, "failed": failed},
            operation=operation,
        )
