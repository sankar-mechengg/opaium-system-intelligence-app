"""
OP(AI)UM — Folder Operations Tool

Complete folder operations: create, delete, move, copy, rename folders.
Provides full control over directory management.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger
from send2trash import send2trash

from src.ai.tools.base_tool import BaseTool, ToolResult
from src.core.models import OperationRecord


class FolderOperationsTool(BaseTool):
    @property
    def name(self) -> str:
        return "folder_operations"

    @property
    def description(self) -> str:
        return (
            "Perform operations on folders: create, delete (to recycle bin), "
            "move, copy, or rename folders. Supports both empty and non-empty folders."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "Operation to perform",
                    "enum": ["create", "delete", "move", "copy", "rename"],
                },
                "path": {
                    "type": "string",
                    "description": "Source folder path",
                },
                "destination": {
                    "type": "string",
                    "description": "Destination path (for move, copy, rename operations)",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "For delete: remove non-empty folders. For copy: include subdirectories",
                    "default": True,
                },
            },
            "required": ["operation", "path"],
        }

    @property
    def is_destructive(self) -> bool:
        return True

    def preview(self, **kwargs: Any) -> ToolResult:
        operation = kwargs.get("operation", "")
        path = kwargs.get("path", "")
        destination = kwargs.get("destination", "")

        path_obj = Path(path)

        if operation == "create":
            if path_obj.exists():
                return ToolResult(success=False, message=f"Folder already exists: {path}")
            return ToolResult(
                success=True,
                message=f"Will create folder: {path}",
                requires_approval=False,
            )

        if not path_obj.exists():
            return ToolResult(success=False, message=f"Folder not found: {path}")

        if not path_obj.is_dir():
            return ToolResult(success=False, message=f"Path is not a folder: {path}")

        # Count contents
        try:
            total_items = sum(1 for _ in path_obj.rglob("*"))
            total_size = sum(f.stat().st_size for f in path_obj.rglob("*") if f.is_file())
        except Exception:
            total_items = 0
            total_size = 0

        from src.utils.path_utils import PathUtils

        size_str = PathUtils.format_size(total_size)

        preview_lines = []

        if operation == "delete":
            is_empty = total_items == 0
            if is_empty:
                preview_lines.append("Will delete empty folder to Recycle Bin:")
            else:
                preview_lines.append("Will delete folder to Recycle Bin:")
                preview_lines.append(f"  Contains: {total_items} items ({size_str})")
            preview_lines.append(f"  Path: {path}")

        elif operation == "move":
            if not destination:
                return ToolResult(success=False, message="Destination path required for move")
            preview_lines.append("Will move folder:")
            preview_lines.append(f"  From: {path}")
            preview_lines.append(f"  To: {destination}")
            preview_lines.append(f"  Contents: {total_items} items ({size_str})")

        elif operation == "copy":
            if not destination:
                return ToolResult(success=False, message="Destination path required for copy")
            preview_lines.append("Will copy folder:")
            preview_lines.append(f"  From: {path}")
            preview_lines.append(f"  To: {destination}")
            preview_lines.append(f"  Contents: {total_items} items ({size_str})")

        elif operation == "rename":
            if not destination:
                return ToolResult(success=False, message="New name required for rename")
            dest_path = Path(destination)
            if not dest_path.is_absolute():
                # Treat as relative name, keep same parent
                dest_path = path_obj.parent / destination
            preview_lines.append("Will rename folder:")
            preview_lines.append(f"  From: {path_obj.name}")
            preview_lines.append(f"  To: {dest_path.name}")
            preview_lines.append(f"  Contents: {total_items} items ({size_str})")

        return ToolResult(
            success=True,
            message="\n".join(preview_lines),
            requires_approval=True,
            preview=preview_lines,
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        operation = kwargs.get("operation", "")
        path = kwargs.get("path", "")
        destination = kwargs.get("destination", "")
        recursive = kwargs.get("recursive", True)

        path_obj = Path(path)

        try:
            if operation == "create":
                return self._create_folder(path_obj)
            elif operation == "delete":
                return self._delete_folder(path_obj, recursive)
            elif operation == "move":
                return self._move_folder(path_obj, destination)
            elif operation == "copy":
                return self._copy_folder(path_obj, destination, recursive)
            elif operation == "rename":
                return self._rename_folder(path_obj, destination)
            else:
                return ToolResult(success=False, message=f"Unknown operation: {operation}")
        except Exception as e:
            logger.error(f"Folder operation failed: {e}")
            return ToolResult(success=False, message=f"Operation failed: {str(e)}")

    def _create_folder(self, path: Path) -> ToolResult:
        """Create a new folder."""
        if path.exists():
            return ToolResult(success=False, message=f"Folder already exists: {path}")

        try:
            path.mkdir(parents=True, exist_ok=False)
            logger.info(f"Created folder: {path}")

            operation = OperationRecord(
                timestamp=datetime.now(),
                operation_type="create_folder",
                description=f"Created folder: {path.name}",
                dest_paths=[str(path)],
                is_undoable=True,
            )

            return ToolResult(
                success=True,
                message=f"Created folder: {path}",
                operation=operation,
            )
        except Exception as e:
            return ToolResult(success=False, message=f"Failed to create folder: {str(e)}")

    def _delete_folder(self, path: Path, recursive: bool) -> ToolResult:
        """Delete a folder to Recycle Bin."""
        if not path.exists():
            return ToolResult(success=False, message=f"Folder not found: {path}")

        if not path.is_dir():
            return ToolResult(success=False, message=f"Path is not a folder: {path}")

        try:
            # Check if empty
            is_empty = not any(path.iterdir())

            if not is_empty and not recursive:
                return ToolResult(
                    success=False,
                    message="Folder is not empty. Use recursive=true to delete non-empty folders.",
                )

            # Use send2trash for safe deletion
            send2trash(str(path))
            logger.info(f"Deleted folder to Recycle Bin: {path}")

            operation = OperationRecord(
                timestamp=datetime.now(),
                operation_type="delete_folder",
                description=f"Deleted folder to Recycle Bin: {path.name}",
                source_paths=[str(path)],
                is_undoable=False,  # Recovery via Recycle Bin
                metadata={"method": "recycle_bin", "was_empty": is_empty},
            )

            return ToolResult(
                success=True,
                message=f"Deleted folder to Recycle Bin: {path.name}",
                operation=operation,
            )
        except Exception as e:
            logger.error(f"Failed to delete folder: {e}")
            return ToolResult(success=False, message=f"Failed to delete folder: {str(e)}")

    def _move_folder(self, source: Path, destination: str) -> ToolResult:
        """Move a folder to a new location."""
        if not source.exists():
            return ToolResult(success=False, message=f"Source folder not found: {source}")

        dest_path = Path(destination)

        # If destination exists and is a directory, move into it
        if dest_path.exists() and dest_path.is_dir():
            dest_path = dest_path / source.name

        if dest_path.exists():
            return ToolResult(success=False, message=f"Destination already exists: {dest_path}")

        try:
            shutil.move(str(source), str(dest_path))
            logger.info(f"Moved folder: {source} -> {dest_path}")

            operation = OperationRecord(
                timestamp=datetime.now(),
                operation_type="move_folder",
                description=f"Moved folder: {source.name} to {dest_path.parent.name}",
                source_paths=[str(source)],
                dest_paths=[str(dest_path)],
                is_undoable=True,
            )

            return ToolResult(
                success=True,
                message=f"Moved folder to: {dest_path}",
                operation=operation,
            )
        except Exception as e:
            return ToolResult(success=False, message=f"Failed to move folder: {str(e)}")

    def _copy_folder(self, source: Path, destination: str, recursive: bool) -> ToolResult:
        """Copy a folder to a new location."""
        if not source.exists():
            return ToolResult(success=False, message=f"Source folder not found: {source}")

        dest_path = Path(destination)

        # If destination exists and is a directory, copy into it
        if dest_path.exists() and dest_path.is_dir():
            dest_path = dest_path / source.name

        if dest_path.exists():
            return ToolResult(success=False, message=f"Destination already exists: {dest_path}")

        try:
            if recursive:
                shutil.copytree(str(source), str(dest_path))
            else:
                dest_path.mkdir(parents=True)
                for item in source.iterdir():
                    if item.is_file():
                        shutil.copy2(str(item), str(dest_path))

            logger.info(f"Copied folder: {source} -> {dest_path}")

            operation = OperationRecord(
                timestamp=datetime.now(),
                operation_type="copy_folder",
                description=f"Copied folder: {source.name} to {dest_path.parent.name}",
                source_paths=[str(source)],
                dest_paths=[str(dest_path)],
                is_undoable=False,
            )

            return ToolResult(
                success=True,
                message=f"Copied folder to: {dest_path}",
                operation=operation,
            )
        except Exception as e:
            return ToolResult(success=False, message=f"Failed to copy folder: {str(e)}")

    def _rename_folder(self, source: Path, new_name: str) -> ToolResult:
        """Rename a folder."""
        if not source.exists():
            return ToolResult(success=False, message=f"Folder not found: {source}")

        # Handle both absolute and relative names
        dest_path = Path(new_name)
        if not dest_path.is_absolute():
            dest_path = source.parent / new_name

        if dest_path.exists():
            return ToolResult(success=False, message=f"A folder with that name already exists: {dest_path.name}")

        try:
            source.rename(dest_path)
            logger.info(f"Renamed folder: {source.name} -> {dest_path.name}")

            operation = OperationRecord(
                timestamp=datetime.now(),
                operation_type="rename_folder",
                description=f"Renamed folder: {source.name} -> {dest_path.name}",
                source_paths=[str(source)],
                dest_paths=[str(dest_path)],
                is_undoable=True,
            )

            return ToolResult(
                success=True,
                message=f"Renamed folder to: {dest_path.name}",
                operation=operation,
            )
        except Exception as e:
            return ToolResult(success=False, message=f"Failed to rename folder: {str(e)}")
