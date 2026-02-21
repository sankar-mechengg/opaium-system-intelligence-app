"""
OP(AI)UM — Windows Recent Folder Parser

Reads and parses .lnk shortcut files from the Windows Recent folder
(%APPDATA%/Microsoft/Windows/Recent) to discover recently accessed
files and folders. Resolves shortcuts to their actual targets.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from src.config.constants import AppConstants
from src.core.models import RecentItem, ItemType
from src.utils.path_utils import PathUtils
from src.utils.time_utils import TimeUtils, TimeGroup
from src.utils.windows_api import WindowsAPI


class RecentParser:
    """
    Parses the Windows Recent folder to extract recently accessed
    files and folders with their timestamps.
    """

    def __init__(self) -> None:
        self._recent_dir = AppConstants.WINDOWS_RECENT_DIR
        self._cache: dict[str, RecentItem] = {}

    def scan(
        self,
        include_files: bool = True,
        include_folders: bool = True,
        max_days: int = AppConstants.GROUP_MONTH_DAYS,
        filter_hidden: bool = True,
    ) -> list[RecentItem]:
        """
        Scan the Windows Recent folder and return resolved items.

        Args:
            include_files: Include recently accessed files.
            include_folders: Include recently accessed folders.
            max_days: Maximum age in days to include.
            filter_hidden: Filter out hidden/system items.

        Returns:
            List of RecentItem sorted by access time (newest first).
        """
        if not self._recent_dir.exists():
            logger.warning(f"Recent folder not found: {self._recent_dir}")
            return []

        items: list[RecentItem] = []
        seen_paths: set[str] = set()
        cutoff = datetime.now().timestamp() - (max_days * 86400)

        try:
            lnk_files = list(self._recent_dir.glob("*.lnk"))
            logger.info(f"Found {len(lnk_files)} .lnk files in Recent folder.")

            for lnk_path in lnk_files:
                item = self._parse_lnk(lnk_path, cutoff, filter_hidden)
                if item is None:
                    continue

                # Filter by type
                if item.is_folder and not include_folders:
                    continue
                if item.is_file and not include_files:
                    continue

                # Deduplicate by resolved path
                normalized = str(Path(item.path).resolve()).lower()
                if normalized in seen_paths:
                    continue
                seen_paths.add(normalized)

                items.append(item)

        except PermissionError:
            logger.error("Permission denied reading Recent folder.")
        except Exception as e:
            logger.error(f"Error scanning Recent folder: {e}")

        # Sort by access time, newest first
        items.sort(key=lambda x: x.accessed_at, reverse=True)

        logger.info(
            f"Resolved {len(items)} recent items "
            f"({sum(1 for i in items if i.is_folder)} folders, "
            f"{sum(1 for i in items if i.is_file)} files)"
        )

        return items

    def _parse_lnk(
        self,
        lnk_path: Path,
        cutoff_timestamp: float,
        filter_hidden: bool,
    ) -> Optional[RecentItem]:
        """
        Parse a single .lnk file and resolve its target.

        Args:
            lnk_path: Path to the .lnk file.
            cutoff_timestamp: Ignore items older than this.
            filter_hidden: Skip hidden/system targets.

        Returns:
            RecentItem or None if invalid/filtered.
        """
        try:
            # Get .lnk modification time as proxy for access time
            lnk_stat = lnk_path.stat()
            lnk_mtime = lnk_stat.st_mtime

            # Filter by age
            if lnk_mtime < cutoff_timestamp:
                return None

            accessed_at = datetime.fromtimestamp(lnk_mtime)

            # Resolve the shortcut target
            target_path = WindowsAPI.resolve_lnk_target(lnk_path)
            if target_path is None:
                # Broken link
                return RecentItem(
                    path=str(lnk_path),
                    name=lnk_path.stem,
                    item_type=ItemType.FOLDER,
                    accessed_at=accessed_at,
                    time_group=TimeUtils.get_time_group(accessed_at),
                    exists=False,
                    is_broken=True,
                    lnk_source=str(lnk_path),
                )

            target = Path(target_path)

            # Filter hidden/system
            if filter_hidden and PathUtils.is_system_or_hidden(target):
                return None

            # Determine type
            is_dir = target.is_dir()
            item_type = ItemType.FOLDER if is_dir else ItemType.FILE

            # Get metadata
            try:
                stat = target.stat()
                size_bytes = stat.st_size if not is_dir else 0
            except OSError:
                size_bytes = 0

            # Get file extension for files
            extension = ""
            if not is_dir:
                extension = target.suffix.lstrip(".").lower()

            # Get item counts for folders
            item_count = None
            if is_dir:
                try:
                    item_count = PathUtils.count_items(target)
                except Exception:
                    item_count = (0, 0)

            # Get NTFS file ID for tracking
            file_id = WindowsAPI.get_file_id(target)
            volume_serial = WindowsAPI.get_volume_serial(target)

            time_group = TimeUtils.get_time_group(accessed_at)

            return RecentItem(
                path=str(target),
                name=target.name,
                item_type=item_type,
                accessed_at=accessed_at,
                time_group=time_group,
                size_bytes=size_bytes,
                extension=extension,
                parent_path=str(target.parent),
                file_id=file_id,
                volume_serial=volume_serial,
                lnk_source=str(lnk_path),
                exists=True,
                is_broken=False,
                item_count=item_count,
            )

        except Exception as e:
            logger.debug(f"Failed to parse {lnk_path.name}: {e}")
            return None

    def get_grouped_items(
        self,
        include_files: bool = True,
        include_folders: bool = True,
    ) -> dict[TimeGroup, list[RecentItem]]:
        """
        Get recent items grouped by time period.

        Returns:
            Dict mapping TimeGroup to list of RecentItems.
        """
        items = self.scan(include_files=include_files, include_folders=include_folders)

        grouped: dict[TimeGroup, list[RecentItem]] = {
            TimeGroup.LAST_2_DAYS: [],
            TimeGroup.LAST_WEEK: [],
            TimeGroup.LAST_MONTH: [],
            TimeGroup.OLDER: [],
        }

        for item in items:
            grouped[item.time_group].append(item)

        # Log group sizes
        for group, group_items in grouped.items():
            if group_items:
                logger.debug(f"{group.value}: {len(group_items)} items")

        return grouped

    def clean_broken_links(self) -> int:
        """
        Remove .lnk files that point to non-existent targets.

        Returns:
            Number of broken links removed.
        """
        removed = 0
        try:
            for lnk_path in self._recent_dir.glob("*.lnk"):
                target = WindowsAPI.resolve_lnk_target(lnk_path)
                if target is None:
                    try:
                        lnk_path.unlink()
                        removed += 1
                        logger.debug(f"Removed broken link: {lnk_path.name}")
                    except OSError:
                        continue
        except Exception as e:
            logger.error(f"Error cleaning broken links: {e}")

        if removed:
            logger.info(f"Cleaned {removed} broken recent shortcuts.")
        return removed
