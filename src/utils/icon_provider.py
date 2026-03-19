"""
OP(AI)UM — Icon Provider

Extracts file and folder icons from Windows Shell for display
in the card/grid views. Caches icons to avoid repeated system calls.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QFileIconProvider

from src.config.constants import AppConstants


class IconProvider:
    """
    Provides file and folder icons using Qt's native icon provider
    with a caching layer for performance.
    """

    def __init__(self) -> None:
        self._provider = QFileIconProvider()
        self._cache: dict[str, QIcon] = {}
        self._default_folder_icon: QIcon | None = None
        self._default_file_icon: QIcon | None = None
        self._app_icon: QIcon | None = None

    def get_folder_icon(self, path: str | Path | None = None) -> QIcon:
        """
        Get the icon for a folder.

        Args:
            path: Folder path. If None, returns default folder icon.

        Returns:
            QIcon for the folder.
        """
        if path is None:
            return self._get_default_folder_icon()

        cache_key = f"folder:{path}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            from PySide6.QtCore import QFileInfo

            file_info = QFileInfo(str(path))
            icon = self._provider.icon(file_info)
            if not icon.isNull():
                self._cache[cache_key] = icon
                return icon
        except Exception:
            pass

        return self._get_default_folder_icon()

    def get_file_icon(self, path: str | Path) -> QIcon:
        """
        Get the icon for a file based on its extension.

        Args:
            path: File path.

        Returns:
            QIcon for the file type.
        """
        ext = Path(path).suffix.lower()
        cache_key = f"ext:{ext}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            from PySide6.QtCore import QFileInfo

            file_info = QFileInfo(str(path))
            icon = self._provider.icon(file_info)
            if not icon.isNull():
                self._cache[cache_key] = icon
                return icon
        except Exception:
            pass

        return self._get_default_file_icon()

    def get_app_icon(self) -> QIcon:
        """Get the OP(AI)UM application icon."""
        if self._app_icon is not None:
            return self._app_icon

        logo_path = AppConstants.LOGO_PATH
        if logo_path.exists():
            self._app_icon = QIcon(str(logo_path))
        else:
            # Fallback to a generic app icon
            self._app_icon = QIcon.fromTheme("application-x-executable")

        return self._app_icon

    def _get_default_folder_icon(self) -> QIcon:
        """Get the default folder icon."""
        if self._default_folder_icon is None:
            self._default_folder_icon = self._provider.icon(QFileIconProvider.IconType.Folder)
        return self._default_folder_icon

    def _get_default_file_icon(self) -> QIcon:
        """Get the default file icon."""
        if self._default_file_icon is None:
            self._default_file_icon = self._provider.icon(QFileIconProvider.IconType.File)
        return self._default_file_icon

    def clear_cache(self) -> None:
        """Clear the icon cache."""
        self._cache.clear()
        logger.debug("Icon cache cleared.")

    @staticmethod
    def icon_to_pixmap(icon: QIcon, size: int = 48) -> QPixmap:
        """Convert a QIcon to a QPixmap of specified size."""
        return icon.pixmap(QSize(size, size))
