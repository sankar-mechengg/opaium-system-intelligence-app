"""
OP(AI)UM — Icon Provider

Two icon sources:
1. Native Windows shell icons for files and folders (QFileIconProvider), cached.
2. The app's monochrome SVG icon set (assets/icons/svg), tinted with the active
   theme's colors and rendered crisp at any DPI.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFileIconProvider

from src.config.constants import AppConstants


class SvgIcons:
    """Tinted SVG icons from the bundled icon set."""

    _svg_cache: dict[str, str] = {}
    _icon_cache: dict[tuple[str, str, int], QIcon] = {}

    @classmethod
    def _load_svg(cls, name: str) -> str | None:
        if name in cls._svg_cache:
            return cls._svg_cache[name]
        path = AppConstants.SVG_ICONS_DIR / f"{name}.svg"
        try:
            data = path.read_text(encoding="utf-8")
        except Exception:
            logger.debug(f"SVG icon not found: {name}")
            data = ""
        cls._svg_cache[name] = data
        return data or None

    @classmethod
    def pixmap(cls, name: str, color: str, size: int = 20) -> QPixmap:
        svg = cls._load_svg(name)
        if not svg:
            return QPixmap()
        ratio = 1.0
        app = QGuiApplication.instance()
        if app is not None:
            try:
                screen = QGuiApplication.primaryScreen()
                ratio = screen.devicePixelRatio() if screen else 1.0
            except Exception:
                ratio = 1.0
        px = int(round(size * ratio))
        image = QImage(px, px, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        renderer = QSvgRenderer(QByteArray(svg.replace("currentColor", color).encode("utf-8")))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(0, 0, px, px))
        painter.end()
        pixmap = QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(ratio)
        return pixmap

    @classmethod
    def icon(cls, name: str, color: str, size: int = 20) -> QIcon:
        key = (name, color, size)
        cached = cls._icon_cache.get(key)
        if cached is not None:
            return cached
        icon = QIcon()
        for s in {size, size * 2}:
            pm = cls.pixmap(name, color, s)
            if not pm.isNull():
                icon.addPixmap(pm)
        cls._icon_cache[key] = icon
        return icon

    @classmethod
    def themed(cls, name: str, role: str = "icon", size: int = 20) -> QIcon:
        """Icon tinted with a theme token (e.g. 'icon', 'accent', 'red')."""
        from src.ui.theme import token

        return cls.icon(name, token(role), size)

    @classmethod
    def clear_cache(cls) -> None:
        cls._icon_cache.clear()


class IconProvider:
    """
    Provides file and folder icons using Qt's native icon provider
    with a caching layer for performance.
    """

    _shared: IconProvider | None = None

    def __init__(self) -> None:
        self._provider = QFileIconProvider()
        self._cache: dict[str, QIcon] = {}
        self._default_folder_icon: QIcon | None = None
        self._default_file_icon: QIcon | None = None
        self._app_icon: QIcon | None = None

    @classmethod
    def shared(cls) -> IconProvider:
        """Process-wide provider so caches are shared between views."""
        if cls._shared is None:
            cls._shared = IconProvider()
        return cls._shared

    def get_folder_icon(self, path: str | Path | None = None) -> QIcon:
        """Get the icon for a folder (default folder icon when path is None)."""
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
        """Get the icon for a file based on its extension (executables/shortcuts by path)."""
        p = Path(path)
        ext = p.suffix.lower()
        by_path = ext in (".exe", ".lnk", ".ico", ".url")
        cache_key = f"path:{p}" if by_path else f"ext:{ext}"

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

        logo_path = AppConstants.LOGO_ICO_PATH if AppConstants.LOGO_ICO_PATH.exists() else AppConstants.LOGO_PATH
        if logo_path.exists():
            self._app_icon = QIcon(str(logo_path))
        else:
            self._app_icon = QIcon.fromTheme("application-x-executable")

        return self._app_icon

    def _get_default_folder_icon(self) -> QIcon:
        if self._default_folder_icon is None:
            self._default_folder_icon = self._provider.icon(QFileIconProvider.IconType.Folder)
        return self._default_folder_icon

    def _get_default_file_icon(self) -> QIcon:
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
