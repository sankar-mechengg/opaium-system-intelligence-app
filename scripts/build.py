"""
OP(AI)UM — Build Script

Packages the app into a standalone Windows executable using PyInstaller.
Usage: python scripts/build.py
"""

import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
ASSETS = ROOT / "assets"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
ICON = ASSETS / "icons" / "opaium.ico"

ENTRY = SRC / "main.py"
APP_NAME = "OPAIUM"
VERSION = "1.0.0"


def clean() -> None:
    """Remove previous build artifacts."""
    import shutil
    for d in [DIST, BUILD]:
        if d.exists():
            shutil.rmtree(d)
            print(f"Cleaned: {d}")


def build() -> None:
    """Run PyInstaller."""
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onedir",
        "--windowed",
        "--noconfirm",
        "--clean",
        # Data files
        "--add-data", f"{ASSETS};assets",
        # Hidden imports for dynamic loading
        "--hidden-import", "src.ai.tools.file_counter",
        "--hidden-import", "src.ai.tools.file_renamer",
        "--hidden-import", "src.ai.tools.file_deleter",
        "--hidden-import", "src.ai.tools.file_mover",
        "--hidden-import", "src.ai.tools.file_copier",
        "--hidden-import", "src.ai.tools.file_sizer",
        "--hidden-import", "src.ai.tools.duplicate_finder",
        "--hidden-import", "src.ai.tools.smart_organizer",
        "--hidden-import", "src.ai.tools.date_organizer",
        "--hidden-import", "src.ai.tools.empty_folder_cleaner",
        "--hidden-import", "src.ai.tools.regex_renamer",
        "--hidden-import", "src.ai.tools.extension_changer",
        "--hidden-import", "src.ai.tools.large_file_finder",
        "--hidden-import", "src.ai.tools.file_age_analyzer",
        "--hidden-import", "src.ai.tools.folder_flattener",
        "--hidden-import", "src.ai.tools.type_summarizer",
        "--hidden-import", "src.ai.tools.metadata_reader",
        "--hidden-import", "src.ai.tools.recycle_bin_tool",
        "--hidden-import", "src.ai.tools.startup_tool",
        "--hidden-import", "src.ai.tools.disk_usage_tool",
        # Paths
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        "--specpath", str(BUILD),
    ]

    if ICON.exists():
        cmd.extend(["--icon", str(ICON)])

    cmd.append(str(ENTRY))

    print(f"Building {APP_NAME} v{VERSION}...")
    print(f"Entry: {ENTRY}")
    print(f"Output: {DIST / APP_NAME}")
    print()

    result = subprocess.run(cmd, cwd=str(ROOT))

    if result.returncode == 0:
        exe_path = DIST / APP_NAME / f"{APP_NAME}.exe"
        print(f"\n✅ Build successful!")
        print(f"   Executable: {exe_path}")
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"   Size: {size_mb:.1f} MB")
    else:
        print(f"\n❌ Build failed with code {result.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    if "--clean" in sys.argv:
        clean()
    build()
