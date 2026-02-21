"""
OP(AI)UM — Development Runner

Launches the application in development mode with
hot-reload friendly settings and debug logging.

Usage: python scripts/run_dev.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["OPAIUM_ENV"] = "development"
os.environ["OPAIUM_LOG_LEVEL"] = "DEBUG"


def main() -> None:
    print("=" * 50)
    print("  OP(AI)UM — Development Mode")
    print("=" * 50)
    print(f"  Root: {ROOT}")
    print(f"  Python: {sys.version}")
    print()

    # Check dependencies
    missing = []
    for pkg in ["PySide6", "openai", "loguru", "pydantic"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    
    # Check argon2 separately (package name is argon2-cffi but imports as argon2)
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
