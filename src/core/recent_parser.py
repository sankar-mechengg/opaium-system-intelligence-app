"""
OP(AI)UM — Windows Recent Folder Parser

Reads and parses .lnk shortcut files from the Windows Recent folder
(%APPDATA%/Microsoft/Windows/Recent) to discover recently accessed
files and folders. Resolves shortcuts to their actual targets.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from loguru import logger

from src.config.constants import AppConstants
from src.core.models import ItemType, RecentItem
from src.utils.path_utils import PathUtils
from src.utils.time_utils import TimeGroup, TimeUtils
from src.utils.windows_api import WindowsAPI


class RecentParser:
    """
    Parses the Windows Recent folder to extract recently accessed
    files and folders with their timestamps.
    """

    def __init__(self, tracking_db=None) -> None:
        self._recent_dir = AppConstants.WINDOWS_RECENT_DIR
        self._cache: dict[str, RecentItem] = {}
        self._tracking_db = tracking_db

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
    ) -> RecentItem | None:
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
                # Broken link - try to resolve using file ID from tracking DB
                # This handles renamed/moved folders
                return self._try_resolve_broken_link(lnk_path, accessed_at)

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

    def _try_resolve_broken_link(
        self,
        lnk_path: Path,
        accessed_at: datetime,
    ) -> RecentItem | None:
        """
        Try to resolve a broken link using the tracking database.

        This handles cases where a folder/file was renamed or moved.
        Uses the NTFS file ID from the .lnk file to find the current path.
        """
        if not self._tracking_db:
            logger.debug(f"No tracking DB available for resolving {lnk_path.name}")
            return None

        try:
            # Parse the .lnk file to extract the original target info
            import pylnk3

            with pylnk3.open(str(lnk_path)) as lnk:
                # Try to get file reference (NTFS file ID) from the link info
                if not hasattr(lnk, "link_info") or lnk.link_info is None:
                    logger.debug(f"No link info in {lnk_path.name}")
                    return None

                # Get the original target path from link info
                original_path = None
                if hasattr(lnk.link_info, "local_base_path") and lnk.link_info.local_base_path:
                    original_path = lnk.link_info.local_base_path

                if not original_path:
                    logger.debug(f"Could not extract original path from {lnk_path.name}")
                    return None

                # Try to get file ID by checking if we have it in tracking DB for old path
                # This works because we track items when they're accessed
                logger.debug(f"Broken link {lnk_path.name} originally pointed to: {original_path}")

                # Search tracking DB for items with similar names (fuzzy match)
                # or try to get volume serial and file reference if available
                resolved_item = self._search_tracking_db_for_match(original_path, lnk_path.stem, accessed_at)

                return resolved_item

        except ImportError:
            logger.warning("pylnk3 not available - install it for rename detection")
            return None
        except Exception as e:
            logger.debug(f"Failed to resolve broken link {lnk_path.name}: {e}")
            return None

    def _search_tracking_db_for_match(
        self,
        original_path: str,
        link_name: str,
        accessed_at: datetime,
    ) -> RecentItem | None:
        """
        Search the tracking DB for a renamed/moved item.

        Strategy:
        1. Try exact path match (shouldn't work for renamed)
        2. Try fuzzy name match in same parent directory
        3. Try fuzzy name match anywhere
        """
        if not self._tracking_db:
            return None

        try:
            original_path_obj = Path(original_path)
            original_parent = str(original_path_obj.parent)
            original_name = original_path_obj.name.lower()

            # Get all tracked items from DB
            all_tracked = self._tracking_db.get_all_tracked()

            # Strategy 1: Look for items in the same parent directory with similar names
            for tracked in all_tracked:
                current_path = Path(tracked.path)

                # Check if in same parent directory
                if str(current_path.parent).lower() == original_parent.lower():
                    # Check if name is similar (might be renamed)
                    # Even if completely different name, if it's in same dir and only one item,
                    # it might be our renamed folder
                    if current_path.exists():
                        logger.info(f"Found renamed item: {original_path} -> {current_path}")
                        return self._create_resolved_item(current_path, accessed_at, tracked)

            # Strategy 2: Look for items with similar names anywhere
            # Use simple fuzzy matching (contains or partial match)
            for tracked in all_tracked:
                current_path = Path(tracked.path)
                current_name = current_path.name.lower()

                # Check if names are similar (simple substring match)
                if (original_name in current_name or current_name in original_name) and current_path.exists():
                    logger.info(f"Found moved/renamed item: {original_path} -> {current_path}")
                    return self._create_resolved_item(current_path, accessed_at, tracked)

            logger.debug(f"Could not find match in tracking DB for {original_path}")
            return None

        except Exception as e:
            logger.error(f"Error searching tracking DB: {e}")
            return None

    def _create_resolved_item(
        self,
        current_path: Path,
        accessed_at: datetime,
        tracked_record,
    ) -> RecentItem:
        """Create a RecentItem from a resolved path."""
        is_dir = current_path.is_dir()
        item_type = ItemType.FOLDER if is_dir else ItemType.FILE

        # Get metadata
        try:
            stat = current_path.stat()
            size_bytes = stat.st_size if not is_dir else 0
        except OSError:
            size_bytes = 0

        # Get file extension for files
        extension = ""
        if not is_dir:
            extension = current_path.suffix.lstrip(".").lower()

        # Get item counts for folders
        item_count = None
        if is_dir:
            try:
                item_count = PathUtils.count_items(current_path)
            except Exception:
                item_count = (0, 0)

        time_group = TimeUtils.get_time_group(accessed_at)

        return RecentItem(
            path=str(current_path),
            name=current_path.name,
            item_type=item_type,
            accessed_at=accessed_at,
            time_group=time_group,
            size_bytes=size_bytes,
            extension=extension,
            parent_path=str(current_path.parent),
            file_id=tracked_record.file_id if hasattr(tracked_record, "file_id") else None,
            volume_serial=tracked_record.volume_serial if hasattr(tracked_record, "volume_serial") else None,
            lnk_source=None,
            exists=True,
            is_broken=False,
            item_count=item_count,
        )

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
