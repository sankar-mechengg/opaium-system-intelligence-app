"""
OP(AI)UM — Operation Models

Data models representing undoable operations performed by the AI.
Each operation type knows how to serialize itself and describes
what the reverse operation would look like.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class OperationType(StrEnum):
    """Types of undoable file operations."""

    RENAME = "rename"
    BATCH_RENAME = "batch_rename"
    MOVE = "move"
    BATCH_MOVE = "batch_move"
    COPY = "copy"
    BATCH_COPY = "batch_copy"
    DELETE = "delete"
    BATCH_DELETE = "batch_delete"
    ORGANIZE = "organize"
    FLATTEN = "flatten"
    CREATE_FOLDER = "create_folder"
    EXTENSION_CHANGE = "extension_change"
    CREATE_FILE = "create_file"
    WRITE_FILE = "write_file"
    APPEND_FILE = "append_file"


class FileMapping(BaseModel):
    """Maps a source file to its destination after an operation."""

    source: str
    destination: str
    original_name: str = ""
    new_name: str = ""


class Operation(BaseModel):
    """
    A recorded operation that can potentially be undone.

    Stores enough information to reverse the operation:
    - For renames: old name -> new name mapping
    - For moves: source -> destination paths
    - For deletes: original path (sent to Recycle Bin)
    - For copies: paths of created copies
    - For organize: full file mapping of what went where
    """

    id: int | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    operation_type: OperationType
    description: str
    file_mappings: list[FileMapping] = Field(default_factory=list)
    affected_count: int = 0
    is_undone: bool = False
    is_undoable: bool = True
    error_message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def display_time(self) -> str:
        from src.utils.time_utils import TimeUtils

        return TimeUtils.format_relative(self.timestamp)

    @property
    def display_datetime(self) -> str:
        return self.timestamp.strftime("%b %d, %Y at %I:%M %p")

    @property
    def type_label(self) -> str:
        labels = {
            OperationType.RENAME: "Rename",
            OperationType.BATCH_RENAME: "Batch Rename",
            OperationType.MOVE: "Move",
            OperationType.BATCH_MOVE: "Batch Move",
            OperationType.COPY: "Copy",
            OperationType.BATCH_COPY: "Batch Copy",
            OperationType.DELETE: "Delete",
            OperationType.BATCH_DELETE: "Batch Delete",
            OperationType.ORGANIZE: "Smart Organize",
            OperationType.FLATTEN: "Flatten Folder",
            OperationType.CREATE_FOLDER: "Create Folder",
            OperationType.EXTENSION_CHANGE: "Extension Change",
            OperationType.CREATE_FILE: "Create File",
            OperationType.WRITE_FILE: "Write File",
            OperationType.APPEND_FILE: "Append File",
        }
        return labels.get(self.operation_type, self.operation_type.value)

    @property
    def undo_description(self) -> str:
        t = self.operation_type
        n = self.affected_count
        if t in (OperationType.RENAME, OperationType.BATCH_RENAME):
            return f"Restore original names for {n} item(s)"
        elif t in (OperationType.MOVE, OperationType.BATCH_MOVE):
            return f"Move {n} item(s) back to original location(s)"
        elif t in (OperationType.COPY, OperationType.BATCH_COPY):
            return f"Delete {n} copied item(s)"
        elif t in (OperationType.DELETE, OperationType.BATCH_DELETE):
            return f"Restore {n} item(s) from Recycle Bin"
        elif t == OperationType.ORGANIZE:
            return f"Move {n} item(s) back to original locations"
        elif t == OperationType.FLATTEN:
            return f"Restore folder structure for {n} item(s)"
        elif t == OperationType.CREATE_FOLDER:
            return "Remove created folder(s)"
        elif t == OperationType.EXTENSION_CHANGE:
            return f"Restore original extensions for {n} file(s)"
        elif t in (OperationType.CREATE_FILE, OperationType.WRITE_FILE, OperationType.APPEND_FILE):
            return f"Revert file change: {self.description}"
        return f"Undo: {self.description}"
