"""
OP(AI)UM — Development Runner

Launches the application in development mode with
hot-reload friendly settings and debug logging.

Usage: python scripts/run_dev.py
       Press Ctrl+C to stop.
"""

import os
import signal
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["OPAIUM_ENV"] = "development"
os.environ["OPAIUM_LOG_LEVEL"] = "DEBUG"


def _handle_sigint(signum, frame):
    """Handle Ctrl+C gracefully."""
    print("\n  Stopping OP(AI)UM...")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app:
        app.quit()
    sys.exit(0)


def main() -> None:
    signal.signal(signal.SIGINT, _handle_sigint)

    print("=" * 50)
    print("  OP(AI)UM -- Development Mode")
    print("=" * 50)
    print(f"  Root: {ROOT}")
    print(f"  Python: {sys.version}")
    print(f"  Press Ctrl+C to stop")
    print()

    missing = []
    for pkg in ["PySide6", "openai", "loguru", "pydantic"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    try:
        __import__("argon2")
    except ImportError:
        missing.append("argon2-cffi")

    if missing:
        print(f"WARNING: Missing packages: {', '.join(missing)}")
        print(f"   Run: pip install -r requirements.txt")
        sys.exit(1)

    from src.main import main as app_main
    app_main()


if __name__ == "__main__":
    main()
