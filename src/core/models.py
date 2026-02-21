"""
OP(AI)UM — Data Models

Pydantic models representing files, folders, and recent items
used throughout the application. These are the core data structures
passed between the data engine, UI, and AI layers.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from src.utils.time_utils import TimeGroup


class ItemType(str, Enum):
    """Type of filesystem item."""
    FOLDER = "folder"
    FILE = "file"


class RecentItem(BaseModel):
    """
    Represents a recently accessed file or folder.

    This is the primary data model used in the explorer views.
    """
    path: str
    name: str
    item_type: ItemType
    accessed_at: datetime
    time_group: TimeGroup = TimeGroup.OLDER

    # Metadata
    size_bytes: int = 0
    extension: str = ""
    parent_path: str = ""

    # Tracking
    file_id: Optional[int] = None  # NTFS file ID
    volume_serial: Optional[int] = None
    lnk_source: Optional[str] = None  # Path to the .lnk file

    # Status
    exists: bool = True
    is_broken: bool = False

    # Display
    icon_key: str = ""  # Cache key for icon provider
    item_count: Optional[tuple[int, int]] = None  # (folders, files) for folders

    class Config:
        arbitrary_types_allowed = True

    @property
    def display_size(self) -> str:
        """Human-readable size string."""
        from src.utils.path_utils import PathUtils
        return PathUtils.format_size(self.size_bytes)

    @property
    def display_time(self) -> str:
        """Human-readable relative time."""
        from src.utils.time_utils import TimeUtils
        return TimeUtils.format_relative(self.accessed_at)

    @property
    def display_datetime(self) -> str:
        """Formatted date-time string."""
        from src.utils.time_utils import TimeUtils
        return TimeUtils.format_datetime(self.accessed_at)

    @property
    def is_folder(self) -> bool:
        return self.item_type == ItemType.FOLDER

    @property
    def is_file(self) -> bool:
        return self.item_type == ItemType.FILE


class FolderItem(BaseModel):
    """
    Detailed folder information for the explorer tree and
    file operation tools.
    """
    path: str
    name: str
    parent_path: str = ""
    size_bytes: int = 0
    folder_count: int = 0
    file_count: int = 0
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    accessed_at: Optional[datetime] = None
    is_hidden: bool = False
    is_system: bool = False
    depth: int = 0  # Nesting depth in tree

    # NTFS tracking
    file_id: Optional[int] = None
    volume_serial: Optional[int] = None

    @property
    def display_size(self) -> str:
        from src.utils.path_utils import PathUtils
        return PathUtils.format_size(self.size_bytes)

    @property
    def total_items(self) -> int:
        return self.folder_count + self.file_count

    @property
    def display_item_count(self) -> str:
        parts = []
        if self.folder_count > 0:
            parts.append(f"{self.folder_count} folder{'s' if self.folder_count != 1 else ''}")
        if self.file_count > 0:
            parts.append(f"{self.file_count} file{'s' if self.file_count != 1 else ''}")
        return ", ".join(parts) if parts else "Empty"


class FileItem(BaseModel):
    """
    Detailed file information for preview panel and
    file operation tools.
    """
    path: str
    name: str
    extension: str = ""
    parent_path: str = ""
    size_bytes: int = 0
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    accessed_at: Optional[datetime] = None
    is_hidden: bool = False
    is_readonly: bool = False

    # Type info
    mime_type: str = ""
    is_image: bool = False
    is_document: bool = False
    is_video: bool = False
    is_audio: bool = False
    is_archive: bool = False

    @property
    def display_size(self) -> str:
        from src.utils.path_utils import PathUtils
        return PathUtils.format_size(self.size_bytes)

    @classmethod
    def classify_extension(cls, ext: str) -> dict[str, bool]:
        """Classify file type based on extension."""
        ext = ext.lower().lstrip(".")
        image_exts = {"png", "jpg", "jpeg", "gif", "bmp", "webp", "svg", "ico", "tiff"}
        doc_exts = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "md", "rtf", "csv"}
        video_exts = {"mp4", "avi", "mkv", "mov", "wmv", "flv", "webm"}
        audio_exts = {"mp3", "wav", "flac", "aac", "ogg", "wma", "m4a"}
        archive_exts = {"zip", "rar", "7z", "tar", "gz", "bz2", "xz"}

        return {
            "is_image": ext in image_exts,
            "is_document": ext in doc_exts,
            "is_video": ext in video_exts,
            "is_audio": ext in audio_exts,
            "is_archive": ext in archive_exts,
        }


class TrackingRecord(BaseModel):
    """
    Record in the custom tracking database.
    Maps NTFS file IDs to paths for rename/move detection.
    """
    file_id: int
    volume_serial: int
    path: str
    name: str
    item_type: ItemType
    first_seen: datetime
    last_seen: datetime
    access_count: int = 1
    is_active: bool = True


class OperationRecord(BaseModel):
    """
    Record of an AI-performed file operation for the undo journal.
    """
    id: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    operation_type: str  # rename, move, copy, delete, organize, etc.
    description: str  # Human-readable description
    source_paths: list[str] = Field(default_factory=list)
    dest_paths: list[str] = Field(default_factory=list)
    original_names: list[str] = Field(default_factory=list)
    new_names: list[str] = Field(default_factory=list)
    is_undone: bool = False
    is_undoable: bool = True
    metadata: dict = Field(default_factory=dict)
