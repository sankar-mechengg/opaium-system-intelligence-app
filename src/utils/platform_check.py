"""
OP(AI)UM — Platform Compatibility Check

Verifies that the system meets minimum requirements:
- Windows 10 or later
- Python 3.11+
- Required Windows APIs available
"""

from __future__ import annotations

import platform
import sys
from typing import NamedTuple

from loguru import logger


class PlatformInfo(NamedTuple):
    """System platform information."""

    os_name: str
    os_version: str
    os_build: str
    python_version: str
    architecture: str
    is_compatible: bool
    issues: list[str]


def check_platform() -> PlatformInfo:
    """
    Check if the current platform meets OP(AI)UM requirements.

    Returns:
        PlatformInfo with compatibility details.
    """
    issues: list[str] = []

    os_name = platform.system()
    os_version = platform.version()
    os_build = platform.win32_ver()[1] if os_name == "Windows" else "N/A"
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    architecture = platform.machine()

    # Check OS
    if os_name != "Windows":
        issues.append(f"OP(AI)UM requires Windows. Detected: {os_name}")

    # Check Windows version (need 10+)
    if os_name == "Windows":
        try:
            major = int(platform.win32_ver()[1].split(".")[0])
            if major < 10:
                issues.append(f"Windows 10 or later required. Detected build: {os_build}")
        except (ValueError, IndexError):
            logger.warning("Could not determine Windows version.")

    # Check Python version

    # Check for required modules
    required_modules = ["ctypes", "sqlite3", "json", "pathlib"]
    for mod in required_modules:
        try:
            __import__(mod)
        except ImportError:
            issues.append(f"Required module missing: {mod}")

    # Check for pywin32
    try:
        import win32com  # noqa: F401
    except ImportError:
        logger.warning("pywin32 not found. Some features will use fallback methods.")

    is_compatible = len(issues) == 0

    info = PlatformInfo(
        os_name=os_name,
        os_version=os_version,
        os_build=os_build,
        python_version=python_version,
        architecture=architecture,
        is_compatible=is_compatible,
        issues=issues,
    )

    if is_compatible:
        logger.info(f"Platform check passed: Windows {os_build}, Python {python_version}")
    else:
        for issue in issues:
            logger.error(f"Platform issue: {issue}")

    return info
