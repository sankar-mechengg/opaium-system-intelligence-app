"""
OP(AI)UM — Theme Manager

Token-based design system. A single QSS template (assets/themes/base.qss)
references design tokens as `@token_name`; this module renders the template
with the light or dark palette, follows the Windows system theme when
requested, and notifies widgets that need to re-tint icons.
"""

from __future__ import annotations

import re
from typing import Any

from loguru import logger
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from src.config.constants import AppConstants

# --- Palettes -----------------------------------------------------------------

DARK_TOKENS: dict[str, str] = {
    "bg_crust": "#11111B",
    "bg_mantle": "#181825",
    "bg_base": "#1E1E2E",
    "bg_surface0": "#262637",
    "bg_surface1": "#313244",
    "bg_surface2": "#45475A",
    "bg_overlay": "#585B70",
    "bg_hover": "#2A2A3E",
    "border": "#2E2E42",
    "border_strong": "#45475A",
    "text": "#CDD6F4",
    "text_sub": "#BAC2DE",
    "text_muted": "#9399B2",
    "text_faint": "#6C7086",
    "accent": "#89B4FA",
    "accent_hover": "#A6C8FF",
    "accent_pressed": "#74A0F0",
    "accent_text": "#11111B",
    "accent_soft": "rgba(137, 180, 250, 0.14)",
    "accent_border": "rgba(137, 180, 250, 0.35)",
    "teal": "#89DCEB",
    "teal_soft": "rgba(137, 220, 235, 0.14)",
    "green": "#A6E3A1",
    "green_soft": "rgba(166, 227, 161, 0.14)",
    "yellow": "#F9E2AF",
    "yellow_soft": "rgba(249, 226, 175, 0.12)",
    "peach": "#FAB387",
    "peach_soft": "rgba(250, 179, 135, 0.14)",
    "red": "#F38BA8",
    "red_soft": "rgba(243, 139, 168, 0.14)",
    "mauve": "#CBA6F7",
    "mauve_soft": "rgba(203, 166, 247, 0.14)",
    "selection": "#3B3F5C",
    "scroll_handle": "#45475A",
    "scroll_handle_hover": "#6C7086",
    "code_bg": "#181825",
    "user_bubble": "rgba(137, 180, 250, 0.16)",
    "user_bubble_border": "rgba(137, 180, 250, 0.35)",
    "user_bubble_text": "#DCE8FF",
    "tooltip_bg": "#313244",
    "icon": "#BAC2DE",
    "icon_muted": "#6C7086",
    "shadow": "rgba(0, 0, 0, 0.45)",
}

LIGHT_TOKENS: dict[str, str] = {
    "bg_crust": "#E9EBF2",
    "bg_mantle": "#F3F4F9",
    "bg_base": "#FBFBFE",
    "bg_surface0": "#F1F2F8",
    "bg_surface1": "#E6E8F0",
    "bg_surface2": "#D6D9E4",
    "bg_overlay": "#B4B8C8",
    "bg_hover": "#EDEFF6",
    "border": "#E1E3EC",
    "border_strong": "#CBCFDC",
    "text": "#1F2430",
    "text_sub": "#3B4152",
    "text_muted": "#5F6679",
    "text_faint": "#8A90A3",
    "accent": "#3B6FE0",
    "accent_hover": "#2F5FCC",
    "accent_pressed": "#2A54B5",
    "accent_text": "#FFFFFF",
    "accent_soft": "rgba(59, 111, 224, 0.10)",
    "accent_border": "rgba(59, 111, 224, 0.35)",
    "teal": "#0F8FA8",
    "teal_soft": "rgba(15, 143, 168, 0.12)",
    "green": "#2E8B57",
    "green_soft": "rgba(46, 139, 87, 0.12)",
    "yellow": "#B7791F",
    "yellow_soft": "rgba(183, 121, 31, 0.12)",
    "peach": "#D9731F",
    "peach_soft": "rgba(217, 115, 31, 0.12)",
    "red": "#D6336C",
    "red_soft": "rgba(214, 51, 108, 0.12)",
    "mauve": "#7C4DFF",
    "mauve_soft": "rgba(124, 77, 255, 0.12)",
    "selection": "#D7E3FC",
    "scroll_handle": "#C6CAD8",
    "scroll_handle_hover": "#9AA0B4",
    "code_bg": "#EEF0F6",
    "user_bubble": "rgba(59, 111, 224, 0.10)",
    "user_bubble_border": "rgba(59, 111, 224, 0.30)",
    "user_bubble_text": "#1F2F5A",
    "tooltip_bg": "#FFFFFF",
    "icon": "#3B4152",
    "icon_muted": "#8A90A3",
    "shadow": "rgba(20, 24, 40, 0.18)",
}

_TOKEN_RE = re.compile(r"@([A-Za-z_][A-Za-z0-9_]*)")


class ThemeManager(QObject):
    """
    Applies the design system to the QApplication and tracks the effective theme.

    Signals:
        theme_applied(str): Effective theme name ("light" or "dark") after each apply.
    """

    theme_applied = Signal(str)

    _instance: ThemeManager | None = None

    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
        self._app = app
        self._mode = "system"
        self._effective = "dark"
        self._tokens: dict[str, str] = dict(DARK_TOKENS)
        self._template: str | None = None

        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_system_scheme_changed)

    # === Singleton access ===

    @classmethod
    def instance(cls) -> ThemeManager | None:
        return cls._instance

    @classmethod
    def install(cls, app: QApplication) -> ThemeManager:
        if cls._instance is None:
            cls._instance = ThemeManager(app)
        return cls._instance

    # === Public API ===

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def effective(self) -> str:
        return self._effective

    @property
    def is_dark(self) -> bool:
        return self._effective == "dark"

    @property
    def tokens(self) -> dict[str, str]:
        return self._tokens

    def color(self, name: str, fallback: str = "#888888") -> str:
        return self._tokens.get(name, fallback)

    @staticmethod
    def system_prefers_dark() -> bool:
        try:
            scheme = QGuiApplication.styleHints().colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return True
            if scheme == Qt.ColorScheme.Light:
                return False
        except Exception:
            pass
        # Fallback: inspect the palette
        try:
            pal = QGuiApplication.palette()
            return pal.color(QPalette.ColorRole.Window).lightness() < 128
        except Exception:
            return False

    def apply(self, mode: Any | None = None) -> str:
        """
        Apply a theme mode: "system", "light" or "dark" (enum or string).
        Returns the effective theme.
        """
        if mode is not None:
            self._mode = str(mode.value) if hasattr(mode, "value") else str(mode)
        effective = self._resolve(self._mode)
        self._effective = effective
        self._tokens = dict(DARK_TOKENS if effective == "dark" else LIGHT_TOKENS)
        self._tokens["svg_dir"] = self._prepare_qss_icons(effective)

        try:
            from src.utils.icon_provider import SvgIcons

            SvgIcons.clear_cache()
        except Exception:
            pass

        stylesheet = self._render()
        self._app.setStyleSheet(stylesheet)
        self._app.setProperty("opaiumTheme", effective)
        logger.info(f"Theme applied: {self._mode} -> {effective}")
        self.theme_applied.emit(effective)
        return effective

    def reload(self) -> None:
        """Re-read the template from disk (development helper)."""
        self._template = None
        self.apply()

    # === Internals ===

    @staticmethod
    def _resolve(mode: str) -> str:
        if mode == "dark":
            return "dark"
        if mode == "light":
            return "light"
        return "dark" if ThemeManager.system_prefers_dark() else "light"

    def _load_template(self) -> str:
        if self._template is None:
            path = AppConstants.THEMES_DIR / "base.qss"
            try:
                self._template = path.read_text(encoding="utf-8")
            except Exception as e:
                logger.error(f"Theme template missing ({path}): {e}")
                self._template = ""
        return self._template

    def _render(self) -> str:
        template = self._load_template()
        tokens = self._tokens

        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            return tokens.get(key, match.group(0))

        return _TOKEN_RE.sub(repl, template)

    # QSS `url()` images cannot be recolored, so tinted copies of the few icons
    # referenced from the stylesheet are written to the cache dir per theme.
    _QSS_ICONS: dict[str, str] = {
        "chevron-down": "icon",
        "chevron-up": "icon",
        "chevron-right": "icon",
        "check": "accent_text",
        "dot": "accent_text",
    }

    def _prepare_qss_icons(self, effective: str) -> str:
        out_dir = AppConstants.CACHE_DIR / f"qss-icons-{effective}"
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            for name, token_name in self._QSS_ICONS.items():
                src = AppConstants.SVG_ICONS_DIR / f"{name}.svg"
                dst = out_dir / f"{name}.svg"
                if not src.exists():
                    continue
                color = self._tokens.get(token_name, "#888888")
                svg = src.read_text(encoding="utf-8").replace("currentColor", color)
                if not dst.exists() or dst.read_text(encoding="utf-8") != svg:
                    dst.write_text(svg, encoding="utf-8")
        except Exception as e:
            logger.debug(f"QSS icon preparation failed: {e}")
        return out_dir.as_posix()

    def _on_system_scheme_changed(self, *_args: Any) -> None:
        if self._mode == "system":
            self.apply()


def current_tokens() -> dict[str, str]:
    """Tokens of the active theme (dark tokens when no manager is installed)."""
    mgr = ThemeManager.instance()
    return mgr.tokens if mgr else dict(DARK_TOKENS)


def token(name: str, fallback: str = "#888888") -> str:
    return current_tokens().get(name, fallback)


def is_dark() -> bool:
    mgr = ThemeManager.instance()
    return mgr.is_dark if mgr else True
