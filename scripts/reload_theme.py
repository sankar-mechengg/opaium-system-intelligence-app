"""
OP(AI)UM — Quick Hot-Reload for Themes

Quickly reload just the theme/stylesheet without restarting the app.
Perfect for rapid UI tweaking.

Usage: 
1. Keep your app running
2. In another terminal: python scripts/reload_theme.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def reload_theme():
    """Send a reload signal to the running app via a temp file."""
    reload_file = ROOT / ".theme_reload"
    
    try:
        # Touch the file to trigger reload
        reload_file.write_text("reload")
        print("[OK] Theme reload signal sent!")
        print("   (If the app supports hot-reload, theme will update)")
    except Exception as e:
        print(f"[FAILED] Failed to send reload signal: {e}")


if __name__ == "__main__":
    reload_theme()
