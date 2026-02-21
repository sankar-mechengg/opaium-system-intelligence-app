"""
OP(AI)UM — Startup Program Manager

Lists and manages programs configured to start with Windows.
Reads from the registry Run keys and Startup folder.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple

from loguru import logger


class StartupEntry(NamedTuple):
    """A Windows startup program entry."""
    name: str
    command: str
    source: str  # 'registry_user', 'registry_machine', 'startup_folder'
    enabled: bool


class StartupManager:
    """
    Manages Windows startup programs.

    Reads from:
    1. HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run
    2. HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run
    3. User's Startup folder
    """

    @staticmethod
    def get_all_entries() -> list[StartupEntry]:
        """Get all startup entries from all sources."""
        entries: list[StartupEntry] = []

        # Registry: Current User
        entries.extend(StartupManager._read_registry_run(user_level=True))

        # Registry: Local Machine
        entries.extend(StartupManager._read_registry_run(user_level=False))

        # Startup folder
        entries.extend(StartupManager._read_startup_folder())

        return entries

    @staticmethod
    def _read_registry_run(user_level: bool = True) -> list[StartupEntry]:
        """Read startup entries from registry."""
        entries: list[StartupEntry] = []
        try:
            import winreg

            root = winreg.HKEY_CURRENT_USER if user_level else winreg.HKEY_LOCAL_MACHINE
            source = "registry_user" if user_level else "registry_machine"
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"

            try:
                key = winreg.OpenKey(root, key_path, 0, winreg.KEY_READ)
            except FileNotFoundError:
                return entries

            try:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        entries.append(StartupEntry(
                            name=name,
                            command=value,
                            source=source,
                            enabled=True,
                        ))
                        i += 1
                    except OSError:
                        break
            finally:
                winreg.CloseKey(key)

        except ImportError:
            logger.debug("winreg not available.")
        except Exception as e:
            logger.error(f"Failed to read registry startup entries: {e}")

        return entries

    @staticmethod
    def _read_startup_folder() -> list[StartupEntry]:
        """Read startup entries from the Startup folder."""
        entries: list[StartupEntry] = []

        startup_path = Path(os.environ.get("APPDATA", "")) / (
            "Microsoft\\Windows\\Start Menu\\Programs\\Startup"
        )

        if not startup_path.exists():
            return entries

        try:
            for item in startup_path.iterdir():
                if item.suffix.lower() in (".lnk", ".exe", ".bat", ".cmd"):
                    entries.append(StartupEntry(
                        name=item.stem,
                        command=str(item),
                        source="startup_folder",
                        enabled=True,
                    ))
        except Exception as e:
            logger.error(f"Failed to read Startup folder: {e}")

        return entries

    @staticmethod
    def get_summary() -> dict[str, int]:
        """Get a summary count of startup entries by source."""
        entries = StartupManager.get_all_entries()
        summary: dict[str, int] = {
            "total": len(entries),
            "registry_user": 0,
            "registry_machine": 0,
            "startup_folder": 0,
        }
        for entry in entries:
            summary[entry.source] = summary.get(entry.source, 0) + 1
        return summary
