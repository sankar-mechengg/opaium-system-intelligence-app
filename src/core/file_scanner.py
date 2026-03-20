"""
OP(AI)UM — File & Folder Scanner

Scans directories to extract detailed file/folder metadata.
Used by the explorer views and the AI tools for operations
like counting, sizing, and organizing files.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.config.constants import AppConstants
from src.core.models import FileItem, FolderItem
from src.utils.path_utils import PathUtils


class FileScanner:
    """
    Scans directories for files and folders with metadata.
    Supports both shallow (single level) and recursive scanning.
    """

    def __init__(self, show_hidden: bool = False) -> None:
        self._show_hidden = show_hidden

    def scan_directory(
        self,
        path: str | Path,
        recursive: bool = False,
        max_depth: int = AppConstants.MAX_SCAN_DEPTH,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> tuple[list[FolderItem], list[FileItem]]:
        """
        Scan a directory and return its contents.

        Args:
            path: Directory to scan.
            recursive: Whether to scan subdirectories.
            max_depth: Maximum recursion depth.
            progress_callback: Optional callback(current, total).

        Returns:
            Tuple of (folder_list, file_list).
        """
        path = Path(path)
        if not path.is_dir():
            logger.warning(f"Not a directory: {path}")
            return [], []

        folders: list[FolderItem] = []
        files: list[FileItem] = []

        if recursive:
            self._scan_recursive(path, folders, files, 0, max_depth, progress_callback)
        else:
            self._scan_shallow(path, folders, files, progress_callback)

        return folders, files

    def _scan_shallow(
        self,
        path: Path,
        folders: list[FolderItem],
        files: list[FileItem],
        progress_callback: Callable[[int, int], None] | None,
    ) -> None:
        """Scan a single directory level."""
        try:
            entries = list(os.scandir(str(path)))
            total = len(entries)

            for i, entry in enumerate(entries):
                if progress_callback:
                    progress_callback(i + 1, total)

                try:
                    if not self._show_hidden and PathUtils.is_system_or_hidden(entry.path):
                        continue

                    if entry.is_dir(follow_symlinks=False):
                        folder = self._create_folder_item(entry)
                        if folder:
                            folders.append(folder)
                    elif entry.is_file(follow_symlinks=False):
                        file = self._create_file_item(entry)
                        if file:
                            files.append(file)

                except (OSError, PermissionError) as e:
                    logger.debug(f"Skipping {entry.name}: {e}")
                    continue

        except (OSError, PermissionError) as e:
            logger.error(f"Cannot scan {path}: {e}")

    def _scan_recursive(
        self,
        path: Path,
        folders: list[FolderItem],
        files: list[FileItem],
        current_depth: int,
        max_depth: int,
        progress_callback: Callable[[int, int], None] | None,
    ) -> None:
        """Recursively scan directories."""
        if current_depth > max_depth:
            return

        try:
            for entry in os.scandir(str(path)):
                try:
                    if not self._show_hidden and PathUtils.is_system_or_hidden(entry.path):
                        continue

                    if entry.is_dir(follow_symlinks=False):
                        folder = self._create_folder_item(entry, depth=current_depth)
                        if folder:
                            folders.append(folder)
                            # Recurse
                            self._scan_recursive(
                                Path(entry.path),
                                folders,
                                files,
                                current_depth + 1,
                                max_depth,
                                progress_callback,
                            )
                    elif entry.is_file(follow_symlinks=False):
                        file = self._create_file_item(entry)
                        if file:
                            files.append(file)

                except (OSError, PermissionError):
                    continue

        except (OSError, PermissionError) as e:
            logger.debug(f"Cannot access {path}: {e}")

    def _create_folder_item(
        self,
        entry: os.DirEntry,
        depth: int = 0,
    ) -> FolderItem | None:
        """Create a FolderItem from a directory entry."""
        try:
            stat = entry.stat(follow_symlinks=False)
            folder_count, file_count = PathUtils.count_items(entry.path)

            return FolderItem(
                path=entry.path,
                name=entry.name,
                parent_path=str(Path(entry.path).parent),
                folder_count=folder_count,
                file_count=file_count,
                created_at=datetime.fromtimestamp(stat.st_ctime),
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                accessed_at=datetime.fromtimestamp(stat.st_atime),
                is_hidden=PathUtils.is_system_or_hidden(entry.path),
                depth=depth,
            )
        except (OSError, PermissionError):
            return None

    def _create_file_item(self, entry: os.DirEntry) -> FileItem | None:
        """Create a FileItem from a file entry."""
        try:
            stat = entry.stat(follow_symlinks=False)
            ext = Path(entry.name).suffix.lstrip(".").lower()
            ti = FileItem.classify_extension(ext)

            return FileItem(
                path=entry.path,
                name=entry.name,
                extension=ext,
                parent_path=str(Path(entry.path).parent),
                size_bytes=stat.st_size,
                created_at=datetime.fromtimestamp(stat.st_ctime),
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                accessed_at=datetime.fromtimestamp(stat.st_atime),
                is_image=ti["is_image"],
                is_document=ti["is_document"],
                is_video=ti["is_video"],
                is_audio=ti["is_audio"],
                is_archive=ti["is_archive"],
            )
        except (OSError, PermissionError):
            return None

    @staticmethod
    def get_file_hash(file_path: str | Path, algorithm: str = "md5") -> str | None:
        """
        Calculate hash of a file for duplicate detection.

        Args:
            file_path: Path to the file.
            algorithm: Hash algorithm ('md5', 'sha256').

        Returns:
            Hex digest string or None.
        """
        try:
            hasher = hashlib.new(algorithm)
            with open(str(file_path), "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (OSError, PermissionError):
            return None

    @staticmethod
    def get_type_summary(path: str | Path) -> dict[str, int]:
        """
        Get a summary of file types in a directory.

        Args:
            path: Directory to analyze.

        Returns:
            Dict mapping extension → count.
        """
        summary: dict[str, int] = {}
        try:
            for entry in os.scandir(str(path)):
                try:
                    if entry.is_file(follow_symlinks=False):
                        ext = Path(entry.name).suffix.lstrip(".").lower()
                        ext = ext if ext else "(no extension)"
                        summary[ext] = summary.get(ext, 0) + 1
                except (OSError, PermissionError):
                    continue
        except (OSError, PermissionError):
            pass
        return dict(sorted(summary.items(), key=lambda x: x[1], reverse=True))

    @staticmethod
    def find_empty_folders(
        path: str | Path,
        recursive: bool = True,
    ) -> list[str]:
        """
        Find empty folders within a directory.

        Returns:
            List of paths to empty folders.
        """
        empty: list[str] = []
        try:
            for dirpath, dirnames, filenames in os.walk(str(path), topdown=False):
                if not dirnames and not filenames:
                    empty.append(dirpath)
        except (OSError, PermissionError):
            pass
        return empty

    @staticmethod
    def find_large_files(
        path: str | Path,
        min_size_bytes: int,
        recursive: bool = True,
    ) -> list[FileItem]:
        """Find files larger than the specified threshold."""
        large_files: list[FileItem] = []
        try:
            walker = os.walk(str(path)) if recursive else [(str(path), [], os.listdir(str(path)))]
            for dirpath, _, filenames in walker:
                for fname in filenames:
                    fpath = os.path.join(dirpath, fname)
                    try:
                        size = os.path.getsize(fpath)
                        if size >= min_size_bytes:
                            stat = os.stat(fpath)
                            ext = Path(fname).suffix.lstrip(".").lower()
                            ti = FileItem.classify_extension(ext)
                            large_files.append(
                                FileItem(
                                    path=fpath,
                                    name=fname,
                                    extension=ext,
                                    parent_path=dirpath,
                                    size_bytes=size,
                                    modified_at=datetime.fromtimestamp(stat.st_mtime),
                                    is_image=ti["is_image"],
                                    is_document=ti["is_document"],
                                    is_video=ti["is_video"],
                                    is_audio=ti["is_audio"],
                                    is_archive=ti["is_archive"],
                                )
                            )
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            pass

        large_files.sort(key=lambda f: f.size_bytes, reverse=True)
        return large_files
