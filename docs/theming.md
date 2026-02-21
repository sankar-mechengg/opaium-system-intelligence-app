# OP(AI)UM — Theming Guide

## Overview

OP(AI)UM uses Qt Style Sheets (QSS) for theming. Themes are `.qss` files in `assets/themes/`.

## File Structure

```
assets/themes/
├── light.qss    # Pastel light theme
└── dark.qss     # Catppuccin-inspired dark theme
```

## Creating a New Theme

1. Copy `light.qss` or `dark.qss` as a starting point
2. Rename to `mytheme.qss`
3. Modify colors throughout
4. Add the theme name to `AppearanceSettings._theme_combo`

## Key Object Names

All widgets use `setObjectName()` for targeted styling. Key selectors:

### Layout
- `#mainCentral` — Root widget
- `#titleBar` — Custom title bar
- `#explorerSplitter` — Main three-panel splitter

### Explorer
- `#folderCard`, `#fileCard` — Item cards
- `#cardGridScroll` — Scrollable grid area
- `#folderTree` — Navigation tree
- `#previewPanel` — Right-side preview

### Chat
- `#bubble_user`, `#bubble_assistant`, `#bubble_system` — Message bubbles
- `#chatInput` — Text input
- `#sendButton` — Send button
- `#actionChip` — Quick action chips

### Dynamic Properties

Cards support dynamic properties for selection state:

```css
#folderCard[selected="true"] {
    border-color: #4FC3F7;
    background-color: #E3F2FD;
}
```

## Color Palette Recommendations

### Light Theme
- Background: `#F8F9FA` to `#FFFFFF`
- Text: `#333333` to `#6C757D`
- Accent: One primary color (e.g., `#4FC3F7`)
- Borders: `#DEE2E6` to `#E9ECEF`

### Dark Theme
- Background: `#1E1E2E` to `#313244`
- Text: `#CDD6F4` to `#BAC2DE`
- Accent: Lighter tones (e.g., `#89DCEB`)
- Borders: `#313244` to `#45475A`
