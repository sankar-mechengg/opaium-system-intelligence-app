"""
OP(AI)UM — Path Utilities

Helpers for path normalization, validation, existence checking,
and safe path operations across the Windows file system.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from loguru import logger

from src.config.constants import AppConstants


class PathUtils:
    """Utility methods for path operations."""

    @staticmethod
    def normalize(path: str | Path) -> Path:
        """
        Normalize a path: resolve, expand user/env vars, convert to absolute.

        Args:
            path: Raw path string or Path object.

        Returns:
            Normalized absolute Path.
        """
        path_str = str(path)
        path_str = os.path.expandvars(path_str)
        path_str = os.path.expanduser(path_str)
        return Path(path_str).resolve()

    @staticmethod
    def exists_and_accessible(path: str | Path) -> bool:
        """
        Check if a path exists and is accessible (not permission-denied).

        Args:
            path: Path to check.

        Returns:
            True if path exists and can be read.
        """
        try:
            p = Path(path)
            return p.exists() and os.access(str(p), os.R_OK)
        except (OSError, PermissionError):
            return False

    @staticmethod
    def is_system_or_hidden(path: str | Path) -> bool:
        """
        Check if a path is a system or hidden folder.

        Args:
            path: Path to check.

        Returns:
            True if the folder should be filtered out.
        """
        p = Path(path)
        name = p.name

        # Check against known system folder names
        if name in AppConstants.SYSTEM_FOLDERS:
            return True

        # Check hidden prefix
        if name.startswith(AppConstants.HIDDEN_PREFIXES):
            return True

        # Check Windows file attributes
        try:
            import ctypes
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(p))  # type: ignore[union-attr]
            if attrs == -1:
                return False
            FILE_ATTRIBUTE_HIDDEN = 0x02
            FILE_ATTRIBUTE_SYSTEM = 0x04
            return bool(attrs & (FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM))
        except Exception:
            return False

    @staticmethod
    def get_folder_size(path: str | Path) -> int:
        """
        Calculate total size of a folder in bytes.

        Args:
            path: Folder path.

        Returns:
            Total size in bytes, or 0 if inaccessible.
        """
        total = 0
        try:
            for dirpath, _, filenames in os.walk(str(path)):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total += os.path.getsize(fp)
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            pass
        return total

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """
        Format byte count into human-readable string.

        Args:
            size_bytes: Size in bytes.

        Returns:
            Formatted string (e.g., "1.5 GB", "256 KB").
        """
        if size_bytes < 0:
            return "0 B"

        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(size_bytes)

        for unit in units:
            if size < 1024.0:
                if unit == "B":
                    return f"{int(size)} {unit}"
                return f"{size:.1f} {unit}"
            size /= 1024.0

        return f"{size:.1f} PB"

    @staticmethod
    def get_file_extension(path: str | Path) -> str:
        """Get lowercase file extension without dot."""
        return Path(path).suffix.lstrip(".").lower()

    @staticmethod
    def get_drive_letter(path: str | Path) -> Optional[str]:
        """
        Extract drive letter from a Windows path.

        Returns:
            Drive letter (e.g., 'C') or None.
        """
        p = str(Path(path).resolve())
        if len(p) >= 2 and p[1] == ":":
            return p[0].upper()
        return None

    @staticmethod
    def is_same_drive(path1: str | Path, path2: str | Path) -> bool:
        """Check if two paths are on the same drive."""
        d1 = PathUtils.get_drive_letter(path1)
        d2 = PathUtils.get_drive_letter(path2)
        return d1 is not None and d1 == d2

    @staticmethod
    def safe_name(name: str) -> str:
        """
        Sanitize a string for use as a filename.

        Args:
            name: Raw string.

        Returns:
            Sanitized filename-safe string.
        """
        invalid_chars = '<>:"/\\|?*'
        result = name
        for char in invalid_chars:
            result = result.replace(char, "_")
        return result.strip(". ")

    @staticmethod
    def count_items(path: str | Path) -> tuple[int, int]:
        """
        Count folders and files directly inside a directory.

        Args:
            path: Directory path.

        Returns:
            Tuple of (folder_count, file_count).
        """
        folders = 0
        files = 0
        try:
            for entry in os.scandir(str(path)):
                try:
                    if entry.is_dir(follow_symlinks=False):
                        folders += 1
                    elif entry.is_file(follow_symlinks=False):
                        files += 1
                except (OSError, PermissionError):
                    continue
        except (OSError, PermissionError):
            pass
        return folders, files
