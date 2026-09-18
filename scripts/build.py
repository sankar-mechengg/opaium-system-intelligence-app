"""
OP(AI)UM — Build Script

Packages the app into a standalone Windows executable using PyInstaller.
The version is read from src/version.py (single source of truth).

Usage: python scripts/build.py [--clean]
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
ASSETS = ROOT / "assets"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
ICON = ASSETS / "icons" / "opaium_logo_nobg.ico"

ENTRY = SRC / "main.py"
APP_NAME = "OPAIUM"


def read_version() -> str:
    text = (SRC / "version.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not match:
        raise SystemExit("Could not read __version__ from src/version.py")
    return match.group(1)


VERSION = read_version()


def clean() -> None:
    """Remove previous build artifacts."""
    for d in (DIST, BUILD):
        if d.exists():
            shutil.rmtree(d)
            print(f"Cleaned: {d}")


def _hidden_imports() -> list[str]:
    third_party = [
        "loguru",
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtSvg",
        "openai",
        "pydantic",
        "pydantic_settings",
        "cryptography",
        "argon2",
        "argon2.low_level",
        "numpy",
        "sounddevice",
        "send2trash",
        "pylnk3",
        "lxml",
        "lxml.etree",
        "markdown2",
        "pygments",
        "pygments.lexers",
        "pygments.formatters",
        "docx",
        "openpyxl",
        "pptx",
        "pdfplumber",
        "pdfminer",
        "pdfminer.high_level",
        "pypdfium2",
        "striprtf",
        "PIL",
        "PIL.Image",
        "winotify",
        "watchdog",
        "watchdog.observers",
        "watchdog.events",
        "psutil",
        "comtypes",
        "pythoncom",
        "pywintypes",
        "win32com",
        "win32com.client",
        "win32com.shell",
        "win32com.shell.shell",
        "win32api",
        "win32con",
        "win32file",
        "xlsxwriter",
        "dotenv",
    ]
    # Every module under src/ is imported lazily somewhere (tools via the registry,
    # panels via the window); list them all so PyInstaller never misses one.
    project = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(ROOT).with_suffix("")
        module = ".".join(rel.parts)
        if module.endswith("__init__"):
            module = module[: -len(".__init__")]
        project.append(module)
    return third_party + project


def build() -> None:
    """Run PyInstaller."""
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        APP_NAME,
        "--onedir",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--add-data",
        f"{ASSETS};assets",
        "--distpath",
        str(DIST),
        "--workpath",
        str(BUILD),
        "--specpath",
        str(BUILD),
    ]
    for mod in _hidden_imports():
        cmd += ["--hidden-import", mod]
    # Not used at runtime; keeps the bundle smaller
    for mod in ("tkinter", "scipy", "matplotlib", "IPython", "pytest"):
        cmd += ["--exclude-module", mod]

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
        # ASCII-only: Windows/GitHub Actions consoles often use cp1252 (no emoji).
        print("\n[OK] Build successful!")
        print(f"   Executable: {exe_path}")
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"   Size: {size_mb:.1f} MB")
        (DIST / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
    else:
        print(f"\n[FAILED] Build failed with code {result.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    if "--clean" in sys.argv:
        clean()
    build()
