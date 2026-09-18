# OP(AI)UM — Theming Guide

## Overview

OP(AI)UM ships a token-based design system:

- **`assets/themes/base.qss`** — a single Qt Style Sheet template. Colors are never hard-coded;
  every color is written as a token such as `@accent` or `@bg_surface0`.
- **`src/ui/theme.py`** — the `ThemeManager`. It holds the light and dark palettes
  (`LIGHT_TOKENS`, `DARK_TOKENS`), renders the template with the active palette, follows the
  Windows color scheme when the mode is `system`, and emits `theme_applied(str)` so widgets can
  re-tint their icons.
- **`assets/icons/svg/*.svg`** — a monochrome icon set using `currentColor`. `SvgIcons.themed(name, role)`
  tints an icon with a palette token at runtime; `IconButton` re-tints automatically on theme change.

## Modes

| Mode | Behaviour |
|------|-----------|
| `system` (default) | Follows the Windows *Light / Dark* app setting live |
| `light` | Always light |
| `dark` | Always dark |

The mode is stored in `appearance.theme` and can be changed in **Settings → Appearance** (changes preview
instantly and revert on Cancel).

## Tokens

| Group | Tokens |
|-------|--------|
| Surfaces | `bg_crust`, `bg_mantle`, `bg_base`, `bg_surface0/1/2`, `bg_overlay`, `bg_hover` |
| Borders | `border`, `border_strong` |
| Text | `text`, `text_sub`, `text_muted`, `text_faint` |
| Accent | `accent`, `accent_hover`, `accent_pressed`, `accent_text`, `accent_soft`, `accent_border` |
| Semantic | `teal`, `green`, `yellow`, `peach`, `red`, `mauve` (+ `_soft` variants) |
| Misc | `selection`, `scroll_handle`, `scroll_handle_hover`, `code_bg`, `tooltip_bg`, `icon`, `icon_muted` |
| Chat | `user_bubble`, `user_bubble_border`, `user_bubble_text` |

In Python, read a token with `from src.ui.theme import token; token("accent")`. Custom-painted widgets
(ring gauges, toggles, spinners, avatars) resolve tokens at paint time so they follow theme switches.

## Adding a palette

1. Add a new dict in `src/ui/theme.py` with every key from `DARK_TOKENS`.
2. Extend `ThemeManager._resolve()` and the `THEMES` list in `src/ui/settings/appearance_settings.py`.
3. Add the value to `ThemeMode` in `src/config/defaults.py`.

## Styling a new widget

1. `widget.setObjectName("myWidget")` (and `setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)`
   for plain `QWidget` containers that need a background).
2. Add a rule to `base.qss` using tokens only:

```css
#myWidget {
    background-color: @bg_surface0;
    border: 1px solid @border;
    border-radius: 10px;
}
```

3. For dynamic states use properties: `widget.setProperty("state", "ok")` and `#myWidget[state="ok"] { ... }`,
   then re-polish (`style().unpolish(w); style().polish(w)`).

## Icons

Generate or edit icons in `scripts/generate_icons.py` (24×24 viewBox, stroke-based) and run it to write
`assets/icons/svg`. Icons referenced from QSS (`url(@svg_dir/...)`) are tinted copies that the theme manager
writes to `%APPDATA%\OPAIUM\cache\qss-icons-<theme>` on every apply.
