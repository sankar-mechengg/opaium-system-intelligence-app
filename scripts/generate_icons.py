"""
OP(AI)UM — SVG Icon Set Generator

Writes the monochrome, stroke-based icon set used across the UI to
assets/icons/svg/*.svg. Icons use `currentColor` so the theme manager can
tint them at runtime. Re-run after editing the PATHS table.

Usage: python scripts/generate_icons.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "icons" / "svg"

# name -> list of SVG child elements (24x24 viewBox, stroke-based)
PATHS: dict[str, list[str]] = {
    "explorer": ['<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/>'],
    "chat": ['<path d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H9l-4 4v-4H6a2 2 0 0 1-2-2V6z"/>'],
    "history": ['<path d="M3 12a9 9 0 1 0 3-6.7"/>', '<path d="M3 4v5h5"/>', '<path d="M12 8v4l3 2"/>'],
    "dashboard": [
        '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/>',
        '<rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/>',
        '<rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/>',
        '<rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/>',
    ],
    "settings": [
        '<circle cx="12" cy="12" r="3"/>',
        '<path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    ],
    "lock": ['<rect x="5" y="11" width="14" height="10" rx="2"/>', '<path d="M8 11V7a4 4 0 0 1 8 0v4"/>'],
    "unlock": ['<rect x="5" y="11" width="14" height="10" rx="2"/>', '<path d="M8 11V7a4 4 0 0 1 7.5-2"/>'],
    "minimize": ['<path d="M5 12h14"/>'],
    "maximize": ['<rect x="5" y="5" width="14" height="14" rx="1.5"/>'],
    "restore": [
        '<rect x="4" y="8" width="12" height="12" rx="1.5"/>',
        '<path d="M8 8V5.5A1.5 1.5 0 0 1 9.5 4h9A1.5 1.5 0 0 1 20 5.5v9a1.5 1.5 0 0 1-1.5 1.5H16"/>',
    ],
    "close": ['<path d="M6 6l12 12M18 6L6 18"/>'],
    "refresh": ['<path d="M20 12a8 8 0 1 1-2.3-5.7"/>', '<path d="M20 4v5h-5"/>'],
    "back": ['<path d="M15 5l-7 7 7 7"/>'],
    "forward": ['<path d="M9 5l7 7-7 7"/>'],
    "up": ['<path d="M12 19V5"/>', '<path d="M5 12l7-7 7 7"/>'],
    "home": ['<path d="M3 11l9-7 9 7"/>', '<path d="M5 10v10h5v-6h4v6h5V10"/>'],
    "grid": [
        '<rect x="4" y="4" width="6" height="6" rx="1"/>',
        '<rect x="14" y="4" width="6" height="6" rx="1"/>',
        '<rect x="4" y="14" width="6" height="6" rx="1"/>',
        '<rect x="14" y="14" width="6" height="6" rx="1"/>',
    ],
    "list": ['<path d="M9 6h11M9 12h11M9 18h11"/>', '<path d="M4 6h.01M4 12h.01M4 18h.01" stroke-width="2.6"/>'],
    "search": ['<circle cx="11" cy="11" r="6.5"/>', '<path d="M20 20l-4-4"/>'],
    "mic": [
        '<rect x="9" y="3" width="6" height="11" rx="3"/>',
        '<path d="M5 11a7 7 0 0 0 14 0"/>',
        '<path d="M12 18v3"/>',
    ],
    "send": ['<path d="M4 12l16-8-6 16-2.5-6.5L4 12z"/>', '<path d="M11.5 13.5L20 4"/>'],
    "stop": ['<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/>'],
    "folder": ['<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/>'],
    "folder-open": ['<path d="M3 7a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v1"/>', '<path d="M3 11h18l-2 8H5l-2-8z"/>'],
    "folder-plus": [
        '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/>',
        '<path d="M12 10v6M9 13h6"/>',
    ],
    "file": ['<path d="M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/>', '<path d="M14 3v5h5"/>'],
    "trash": [
        '<path d="M4 7h16"/>',
        '<path d="M9 7V4h6v3"/>',
        '<path d="M6 7l1 13h10l1-13"/>',
        '<path d="M10 11v6M14 11v6"/>',
    ],
    "rename": ['<path d="M4 20h4l10-10-4-4L4 16v4z"/>', '<path d="M12.5 7.5l4 4"/>'],
    "chevron-down": ['<path d="M6 9l6 6 6-6"/>'],
    "chevron-up": ['<path d="M6 15l6-6 6 6"/>'],
    "chevron-right": ['<path d="M9 6l6 6-6 6"/>'],
    "chevron-left": ['<path d="M15 6l-6 6 6 6"/>'],
    "check": ['<path d="M5 12.5l4.5 4.5L19 7.5"/>'],
    "dot": ['<circle cx="12" cy="12" r="4" fill="currentColor"/>'],
    "copy": ['<rect x="9" y="9" width="11" height="11" rx="2"/>', '<path d="M5 15V6a2 2 0 0 1 2-2h9"/>'],
    "external": [
        '<path d="M14 4h6v6"/>',
        '<path d="M20 4l-9 9"/>',
        '<path d="M19 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h5"/>',
    ],
    "undo": ['<path d="M9 14L4 9l5-5"/>', '<path d="M4 9h10a6 6 0 0 1 0 12h-3"/>'],
    "warning": ['<path d="M12 4l9 16H3l9-16z"/>', '<path d="M12 10v4M12 17h.01" stroke-width="2.4"/>'],
    "info": ['<circle cx="12" cy="12" r="9"/>', '<path d="M12 11v5M12 8h.01" stroke-width="2.4"/>'],
    "check-circle": ['<circle cx="12" cy="12" r="9"/>', '<path d="M8 12.5l2.5 2.5L16 9.5"/>'],
    "error-circle": ['<circle cx="12" cy="12" r="9"/>', '<path d="M9 9l6 6M15 9l-6 6"/>'],
    "sort": ['<path d="M4 7h10M4 12h7M4 17h4"/>', '<path d="M18 6v12M15 15l3 3 3-3"/>'],
    "filter": ['<path d="M4 5h16l-6 7v6l-4 2v-8L4 5z"/>'],
    "download": ['<path d="M12 4v12"/>', '<path d="M7 11l5 5 5-5"/>', '<path d="M4 20h16"/>'],
    "disk": [
        '<rect x="3" y="5" width="18" height="14" rx="2"/>',
        '<path d="M3 13h18"/>',
        '<path d="M7 16h.01M11 16h.01" stroke-width="2.4"/>',
    ],
    "cpu": [
        '<rect x="7" y="7" width="10" height="10" rx="1.5"/>',
        '<rect x="4" y="4" width="16" height="16" rx="2"/>',
        '<path d="M9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2"/>',
    ],
    "memory": [
        '<rect x="3" y="7" width="18" height="10" rx="2"/>',
        '<path d="M7 7v10M11 7v10M15 7v10M19 7v10" opacity="0.5"/>',
        '<path d="M6 20v1M10 20v1M14 20v1M18 20v1"/>',
    ],
    "rocket": [
        '<path d="M12 3c3 2 5 6 5 10l-2 2h-6l-2-2c0-4 2-8 5-10z"/>',
        '<path d="M9 13l-3 2v3l3-1M15 13l3 2v3l-3-1"/>',
        '<path d="M10.5 18h3l-1.5 3-1.5-3z"/>',
    ],
    "sparkle": [
        '<path d="M12 3l2 5 5 2-5 2-2 5-2-5-5-2 5-2 2-5z"/>',
        '<path d="M19 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8.8-2z"/>',
    ],
    "terminal": ['<rect x="3" y="5" width="18" height="14" rx="2"/>', '<path d="M7 9l3 3-3 3M12 15h5"/>'],
    "eye": ['<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/>', '<circle cx="12" cy="12" r="3"/>'],
    "eye-off": [
        '<path d="M3 3l18 18"/>',
        '<path d="M10.6 5.3A11 11 0 0 1 12 5c6 0 10 7 10 7a17 17 0 0 1-3.2 3.9M6.6 6.6C4 8.5 2 12 2 12s4 7 10 7a9.7 9.7 0 0 0 4.4-1"/>',
    ],
    "plus": ['<path d="M12 5v14M5 12h14"/>'],
    "more": ['<path d="M6 12h.01M12 12h.01M18 12h.01" stroke-width="3"/>'],
    "user": ['<circle cx="12" cy="8" r="4"/>', '<path d="M4 21a8 8 0 0 1 16 0"/>'],
    "robot": [
        '<rect x="4" y="8" width="16" height="11" rx="3"/>',
        '<path d="M12 4v4M9 13h.01M15 13h.01" stroke-width="2.4"/>',
        '<path d="M9 16h6"/>',
    ],
    "play": ['<path d="M7 5l12 7-12 7V5z" fill="currentColor"/>'],
    "pin": ['<path d="M9 4h6l-1 6 3 3v2H7v-2l3-3-1-6z"/>', '<path d="M12 15v6"/>'],
    "clock": ['<circle cx="12" cy="12" r="9"/>', '<path d="M12 7v5l3 2"/>'],
    "duplicate": [
        '<rect x="4" y="4" width="10" height="10" rx="2"/>',
        '<rect x="10" y="10" width="10" height="10" rx="2"/>',
    ],
    "broom": ['<path d="M15 3l6 6"/>', '<path d="M12 6l6 6-8 8H4v-6l8-8z"/>', '<path d="M8 14l2 2"/>'],
    "chart": ['<path d="M4 20V4"/>', '<path d="M4 20h16"/>', '<path d="M8 16v-5M12 16V8M16 16v-3"/>'],
    "recycle": [
        '<path d="M4 7h16"/>',
        '<path d="M9 7V4h6v3"/>',
        '<path d="M6 7l1 13h10l1-13"/>',
        '<path d="M9.5 15.5l2.5 2 2.5-4"/>',
    ],
    "keyboard": [
        '<rect x="3" y="6" width="18" height="12" rx="2"/>',
        '<path d="M7 10h.01M11 10h.01M15 10h.01M7 14h10" stroke-width="2.2"/>',
    ],
    "bell": ['<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4l2-2z"/>', '<path d="M10 20a2 2 0 0 0 4 0"/>'],
    "shield": ['<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z"/>', '<path d="M9 12l2 2 4-4"/>'],
    "open-with": [
        '<rect x="3" y="4" width="18" height="16" rx="2"/>',
        '<path d="M3 9h18"/>',
        '<path d="M8 14l2 2 4-4"/>',
    ],
    "properties": ['<circle cx="12" cy="12" r="9"/>', '<path d="M12 11v5M12 8h.01" stroke-width="2.4"/>'],
    "brain": [
        '<path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 3 3 3 0 0 0 2 3 3 3 0 0 0 3 4h3V4H9z"/>',
        '<path d="M15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 3 3 3 0 0 1-2 3 3 3 0 0 1-3 4h-3V4h3z"/>',
    ],
}

HEADER = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" '
    'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, elements in PATHS.items():
        svg = HEADER + "".join(elements) + "</svg>\n"
        (OUT / f"{name}.svg").write_text(svg, encoding="utf-8")
    print(f"[OK] wrote {len(PATHS)} icons to {OUT}")


if __name__ == "__main__":
    main()
