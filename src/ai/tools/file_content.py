"""
OP(AI)UM — File Content Operations Tool

Read, write, append, and modify file contents.
Provides complete file content manipulation capabilities.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from src.ai.tools.base_tool import BaseTool, ToolResult
from src.core.models import OperationRecord
from src.undo.backup_store import BackupStore


class FileContentTool(BaseTool):
    @property
    def name(self) -> str:
        return "file_content"

    @property
    def description(self) -> str:
        return (
            "Read, write, append, or modify file contents. "
            "Supports: TXT, MD, CSV, .py, .tex (plain text); PDF, DOCX, PPTX, XLSX (structured). "
            "Can create new files or modify existing ones. Use read for PDF/DOCX/PPTX/XLSX to get text content."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "Operation to perform",
                    "enum": ["read", "write", "append", "create"],
                },
                "path": {
                    "type": "string",
                    "description": "File path",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write/append (for write, append, create operations)",
                },
                "encoding": {
                    "type": "string",
                    "description": "Text encoding (default: utf-8)",
                    "default": "utf-8",
                },
                "max_size_kb": {
                    "type": "integer",
                    "description": "For read: maximum content size in KB (default: 256KB to stay within model context limits)",
                    "default": 256,
                },
            },
            "required": ["operation", "path"],
        }

    @property
    def is_destructive(self) -> bool:
        return True  # Writing can overwrite files

    def preview(self, **kwargs: Any) -> ToolResult:
        operation = kwargs.get("operation", "")
        path = kwargs.get("path", "")
        content = kwargs.get("content", "")

        path_obj = Path(path)

        if operation == "read":
            if not path_obj.exists():
                return ToolResult(success=False, message=f"File not found: {path}")

            if not path_obj.is_file():
                return ToolResult(success=False, message=f"Path is not a file: {path}")

            size = path_obj.stat().st_size
            from src.utils.path_utils import PathUtils

            return ToolResult(
                success=True,
                message=f"Will read file: {path_obj.name} ({PathUtils.format_size(size)})",
                requires_approval=False,
            )

        elif operation == "create":
            if path_obj.exists():
                return ToolResult(success=False, message=f"File already exists: {path}")

            content_size = len(content.encode()) if content else 0
            from src.utils.path_utils import PathUtils

            preview_lines = [
                f"Will create new file: {path_obj.name}",
                f"  Location: {path_obj.parent}",
                f"  Size: {PathUtils.format_size(content_size)}",
            ]

            return ToolResult(
                success=True,
                message="\n".join(preview_lines),
                requires_approval=True,
                preview=preview_lines,
            )

        elif operation == "write":
            exists = path_obj.exists()
            action = "overwrite" if exists else "create"

            content_size = len(content.encode()) if content else 0
            from src.utils.path_utils import PathUtils

            preview_lines = [
                f"Will {action} file: {path_obj.name}",
                f"  New size: {PathUtils.format_size(content_size)}",
            ]

            if exists:
                old_size = path_obj.stat().st_size
                preview_lines.append(f"  Old size: {PathUtils.format_size(old_size)}")

            return ToolResult(
                success=True,
                message="\n".join(preview_lines),
                requires_approval=True,
                preview=preview_lines,
            )

        elif operation == "append":
            if not path_obj.exists():
                return ToolResult(success=False, message=f"File not found: {path}")

            current_size = path_obj.stat().st_size
            append_size = len(content.encode()) if content else 0
            new_size = current_size + append_size

            from src.utils.path_utils import PathUtils

            preview_lines = [
                f"Will append to file: {path_obj.name}",
                f"  Current: {PathUtils.format_size(current_size)}",
                f"  Adding: {PathUtils.format_size(append_size)}",
                f"  New size: {PathUtils.format_size(new_size)}",
            ]

            return ToolResult(
                success=True,
                message="\n".join(preview_lines),
                requires_approval=True,
                preview=preview_lines,
            )

        return ToolResult(success=False, message=f"Unknown operation: {operation}")

    def execute(self, **kwargs: Any) -> ToolResult:
        self._log_execution(**kwargs)

        operation = kwargs.get("operation", "")
        path = kwargs.get("path", "")
        content = kwargs.get("content", "")
        encoding = kwargs.get("encoding", "utf-8")
        max_size_kb = kwargs.get("max_size_kb", 256)

        path_obj = Path(path)

        try:
            if operation == "read":
                return self._read_file(path_obj, encoding, max_size_kb)
            elif operation == "write":
                return self._write_file(path_obj, content, encoding)
            elif operation == "append":
                return self._append_file(path_obj, content, encoding)
            elif operation == "create":
                return self._create_file(path_obj, content, encoding)
            else:
                return ToolResult(success=False, message=f"Unknown operation: {operation}")
        except Exception as e:
            logger.error(f"File content operation failed: {e}")
            return ToolResult(success=False, message=f"Operation failed: {str(e)}")

    def _read_file(self, path: Path, encoding: str, max_size_kb: int) -> ToolResult:
        """Read file contents (supports PDF, DOCX, PPTX, XLSX, TXT, MD, CSV, .py, .tex)."""
        if not path.exists():
            return ToolResult(success=False, message=f"File not found: {path}")

        if not path.is_file():
            return ToolResult(success=False, message=f"Path is not a file: {path}")

        max_chars = min(max_size_kb * 1024, 200_000)

        try:
            from src.utils.file_readers import can_read_format, read_file_content

            if not can_read_format(path.suffix):
                return ToolResult(
                    success=False,
                    message=f"Format not supported for reading: {path.suffix}. Supported: PDF, DOCX, PPTX, XLSX, TXT, MD, CSV, .py, .tex",
                )

            content = read_file_content(path, encoding=encoding, max_chars=max_chars)
            if content is None:
                return ToolResult(
                    success=False,
                    message="Could not read file. Install pdfplumber/PyPDF2 for PDF, python-docx for DOCX, python-pptx for PPTX, openpyxl for XLSX.",
                )

            lines = content.count("\n")
            chars = len(content)
            truncated = len(content) >= max_chars

            truncation_note = ""
            if truncated:
                truncation_note = f" [TRUNCATED to {max_chars} chars to fit context window]"

            return ToolResult(
                success=True,
                message=f"Read file: {path.name} ({lines} lines, {chars} characters){truncation_note}",
                data={
                    "content": content,
                    "lines": lines,
                    "characters": chars,
                    "encoding": encoding,
                    "truncated": truncated,
                },
            )
        except Exception as e:
            return ToolResult(success=False, message=f"Failed to read file: {str(e)}")

    def _write_file(self, path: Path, content: str, encoding: str) -> ToolResult:
        """Write content to file (overwrites existing). Supports TXT, MD, CSV, .py, .tex, DOCX, XLSX."""
        existed = path.exists()
        backup_path: str | None = None

        try:
            from src.utils.file_readers import can_write_format, write_file_content

            if not can_write_format(path.suffix):
                return ToolResult(
                    success=False,
                    message=f"Format not supported for writing: {path.suffix}. Supported: TXT, MD, CSV, .py, .tex, DOCX, XLSX",
                )

            if existed:
                backup_path = BackupStore().backup(path)

            if not write_file_content(path, content, encoding=encoding):
                return ToolResult(
                    success=False,
                    message="Could not write file. Install python-docx for DOCX, openpyxl for XLSX.",
                )

            logger.info(f"Wrote file: {path}")

            action = "overwrote" if existed else "created"

            operation = OperationRecord(
                timestamp=datetime.now(),
                operation_type="write_file" if existed else "create_file",
                description=f"{'Overwrote' if existed else 'Created'} file: {path.name}",
                dest_paths=[str(path)],
                is_undoable=(not existed) or backup_path is not None,
                metadata={"action": action, "size": len(content), "backup_path": backup_path},
            )

            return ToolResult(
                success=True,
                message=f"Successfully {action} file: {path.name}",
                operation=operation,
            )
        except Exception as e:
            return ToolResult(success=False, message=f"Failed to write file: {str(e)}")

    def _append_file(self, path: Path, content: str, encoding: str) -> ToolResult:
        """Append content to file."""
        if not path.exists():
            return ToolResult(success=False, message=f"File not found: {path}")

        try:
            prev_size = path.stat().st_size
            backup_path = BackupStore().backup(path)
            with open(path, "a", encoding=encoding) as f:
                f.write(content)

            logger.info(f"Appended to file: {path}")

            operation = OperationRecord(
                timestamp=datetime.now(),
                operation_type="append_file",
                description=f"Appended to file: {path.name}",
                dest_paths=[str(path)],
                is_undoable=True,
                metadata={"size_added": len(content), "prev_size": prev_size, "backup_path": backup_path},
            )

            return ToolResult(
                success=True,
                message=f"Successfully appended to file: {path.name}",
                operation=operation,
            )
        except Exception as e:
            return ToolResult(success=False, message=f"Failed to append to file: {str(e)}")

    def _create_file(self, path: Path, content: str, encoding: str) -> ToolResult:
        """Create a new file (fails if exists). Supports TXT, MD, CSV, .py, .tex, DOCX, XLSX."""
        if path.exists():
            return ToolResult(success=False, message=f"File already exists: {path}")

        try:
            from src.utils.file_readers import can_write_format, write_file_content

            if not can_write_format(path.suffix):
                return ToolResult(
                    success=False,
                    message=f"Format not supported: {path.suffix}. Supported: TXT, MD, CSV, .py, .tex, DOCX, XLSX",
                )

            if not write_file_content(path, content, encoding=encoding):
                return ToolResult(
                    success=False,
                    message="Could not create file. Install python-docx for DOCX, openpyxl for XLSX.",
                )

            logger.info(f"Created file: {path}")

            operation = OperationRecord(
                timestamp=datetime.now(),
                operation_type="create_file",
                description=f"Created file: {path.name}",
                dest_paths=[str(path)],
                is_undoable=True,
                metadata={"size": len(content)},
            )

            return ToolResult(
                success=True,
                message=f"Successfully created file: {path.name}",
                operation=operation,
            )
        except Exception as e:
            return ToolResult(success=False, message=f"Failed to create file: {str(e)}")
