"""
OP(AI)UM — Time Utilities

Handles time-based grouping of files and folders into
"Last 2 Days", "Last Week", "Last Month" categories.
Also provides human-readable time formatting.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from src.config.constants import AppConstants


class TimeGroup(str, Enum):
    """Time-based grouping categories."""
    LAST_2_DAYS = "Last 2 Days"
    LAST_WEEK = "Last Week"
    LAST_MONTH = "Last Month"
    OLDER = "Older"


class TimeUtils:
    """Utility methods for time-based operations."""

    @staticmethod
    def get_time_group(timestamp: datetime) -> TimeGroup:
        """
        Categorize a timestamp into a time group.

        Args:
            timestamp: The datetime to categorize.

        Returns:
            TimeGroup enum value.
        """
        now = datetime.now()
        delta = now - timestamp

        if delta <= timedelta(days=AppConstants.GROUP_RECENT_DAYS):
            return TimeGroup.LAST_2_DAYS
        elif delta <= timedelta(days=AppConstants.GROUP_WEEK_DAYS):
            return TimeGroup.LAST_WEEK
        elif delta <= timedelta(days=AppConstants.GROUP_MONTH_DAYS):
            return TimeGroup.LAST_MONTH
        else:
            return TimeGroup.OLDER

    @staticmethod
    def format_relative(timestamp: datetime) -> str:
        """
        Format a timestamp as a human-readable relative string.

        Args:
            timestamp: The datetime to format.

        Returns:
            Relative time string (e.g., "2 hours ago", "Yesterday").
        """
        now = datetime.now()
        delta = now - timestamp

        seconds = int(delta.total_seconds())
        if seconds < 0:
            return "Just now"

        if seconds < 60:
            return "Just now"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} min{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 172800:
            return "Yesterday"
        elif seconds < 604800:
            days = seconds // 86400
            return f"{days} days ago"
        elif seconds < 2592000:
            weeks = seconds // 604800
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        else:
            return timestamp.strftime("%b %d, %Y")

    @staticmethod
    def format_datetime(timestamp: datetime) -> str:
        """
        Format a datetime for display.

        Args:
            timestamp: The datetime to format.

        Returns:
            Formatted string (e.g., "Feb 21, 2026 at 3:45 PM").
        """
        return timestamp.strftime("%b %d, %Y at %I:%M %p")

    @staticmethod
    def format_date(timestamp: datetime) -> str:
        """Format date only (e.g., 'Feb 21, 2026')."""
        return timestamp.strftime("%b %d, %Y")

    @staticmethod
    def is_within_days(timestamp: datetime, days: int) -> bool:
        """Check if a timestamp is within the last N days."""
        return (datetime.now() - timestamp) <= timedelta(days=days)

    @staticmethod
    def group_order() -> list[TimeGroup]:
        """Return time groups in display order."""
        return [TimeGroup.LAST_2_DAYS, TimeGroup.LAST_WEEK, TimeGroup.LAST_MONTH, TimeGroup.OLDER]

    @staticmethod
    def parse_timestamp(value: Optional[float]) -> Optional[datetime]:
        """
        Safely parse a Unix timestamp.

        Args:
            value: Unix timestamp as float, or None.

        Returns:
            datetime object or None.
        """
        if value is None:
            return None
        try:
            return datetime.fromtimestamp(value)
        except (OSError, ValueError, OverflowError):
            return None
