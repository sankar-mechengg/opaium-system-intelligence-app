"""
OP(AI)UM — Directory Scanner

Lists the direct contents of a folder as RecentItem models for the explorer
browser, with sorting helpers. Designed to run on a worker thread.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.config.constants import AppConstants
from src.core.models import ItemType, RecentItem
from src.utils.path_utils import PathUtils
from src.utils.time_utils import TimeUtils

SORT_NAME = "name"
SORT_MODIFIED = "modified"
SORT_SIZE = "size"
SORT_TYPE = "type"


class DirectoryScanner:
    """Reads one directory level into RecentItem objects."""

    @staticmethod
    def scan(path: str, show_hidden: bool = False, count_folder_items: bool = True) -> list[RecentItem]:
        items: list[RecentItem] = []
        root = Path(path)
        if not root.is_dir():
            return items

        try:
            entries = list(os.scandir(str(root)))
        except PermissionError:
            logger.warning(f"Access denied: {path}")
            raise
        except OSError as e:
            logger.warning(f"Cannot scan {path}: {e}")
            raise

        for entry in entries[: AppConstants.MAX_FILES_DISPLAY]:
            try:
                if not show_hidden and PathUtils.is_system_or_hidden(entry.path):
                    continue
                stat = entry.stat(follow_symlinks=False)
                is_dir = entry.is_dir(follow_symlinks=False)
                modified = datetime.fromtimestamp(stat.st_mtime)
                item_count = None
                if is_dir and count_folder_items:
                    try:
                        item_count = PathUtils.count_items(entry.path)
                    except Exception:
                        item_count = None
                items.append(
                    RecentItem(
                        path=entry.path,
                        name=entry.name,
                        item_type=ItemType.FOLDER if is_dir else ItemType.FILE,
                        accessed_at=modified,
                        time_group=TimeUtils.get_time_group(modified),
                        size_bytes=0 if is_dir else stat.st_size,
                        extension="" if is_dir else Path(entry.name).suffix.lstrip(".").lower(),
                        parent_path=str(root),
                        exists=True,
                        item_count=item_count,
                    )
                )
            except (OSError, PermissionError):
                continue

        return items

    @staticmethod
    def sort(
        items: list[RecentItem],
        field: str = SORT_NAME,
        descending: bool = False,
        folders_first: bool = True,
    ) -> list[RecentItem]:
        def key(item: RecentItem):  # type: ignore[no-untyped-def]
            if field == SORT_MODIFIED:
                return item.accessed_at
            if field == SORT_SIZE:
                return item.size_bytes
            if field == SORT_TYPE:
                return (item.extension, item.name.lower())
            return item.name.lower()

        ordered = sorted(items, key=key, reverse=descending)
        if folders_first:
            ordered = [i for i in ordered if i.is_folder] + [i for i in ordered if not i.is_folder]
        return ordered

    @staticmethod
    def make_item(path: str) -> RecentItem | None:
        """Build a RecentItem for a single path (used after native operations)."""
        p = Path(path)
        try:
            stat = p.stat()
        except OSError:
            return None
        is_dir = p.is_dir()
        modified = datetime.fromtimestamp(stat.st_mtime)
        return RecentItem(
            path=str(p),
            name=p.name or str(p),
            item_type=ItemType.FOLDER if is_dir else ItemType.FILE,
            accessed_at=modified,
            time_group=TimeUtils.get_time_group(modified),
            size_bytes=0 if is_dir else stat.st_size,
            extension="" if is_dir else p.suffix.lstrip(".").lower(),
            parent_path=str(p.parent),
            exists=True,
            item_count=PathUtils.count_items(p) if is_dir else None,
        )
