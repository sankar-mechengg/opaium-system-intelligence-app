"""
OP(AI)UM — Disk Utilities

Provides disk space information, drive listing, and
storage usage analysis for the AI tools.
"""

from __future__ import annotations

import os
import string
from typing import NamedTuple

from loguru import logger

from src.utils.path_utils import PathUtils
from src.utils.windows_api import WindowsAPI


class DriveInfo(NamedTuple):
    """Information about a disk drive."""

    letter: str
    label: str
    filesystem: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent_used: float

    @property
    def display_total(self) -> str:
        return PathUtils.format_size(self.total_bytes)

    @property
    def display_used(self) -> str:
        return PathUtils.format_size(self.used_bytes)

    @property
    def display_free(self) -> str:
        return PathUtils.format_size(self.free_bytes)


class DiskUtils:
    """Disk space and drive management utilities."""

    @staticmethod
    def get_all_drives() -> list[DriveInfo]:
        """
        Get information about all available drives.

        Returns:
            List of DriveInfo for each accessible drive.
        """
        drives: list[DriveInfo] = []

        for letter in string.ascii_uppercase:
            drive_path = f"{letter}:\\"
            if not os.path.exists(drive_path):
                continue

            try:
                import ctypes
                import ctypes.wintypes

                # Get drive type
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive_path)
                # 2=Removable, 3=Fixed, 4=Network, 5=CDROM, 6=RAMDisk
                if drive_type not in (2, 3, 4, 6):
                    continue

                # Get volume information
                vol_name = ctypes.create_unicode_buffer(256)
                fs_name = ctypes.create_unicode_buffer(256)
                serial = ctypes.wintypes.DWORD()
                max_component = ctypes.wintypes.DWORD()
                flags = ctypes.wintypes.DWORD()

                ctypes.windll.kernel32.GetVolumeInformationW(
                    drive_path,
                    vol_name,
                    256,
                    ctypes.byref(serial),
                    ctypes.byref(max_component),
                    ctypes.byref(flags),
                    fs_name,
                    256,
                )

                # Get space
                total, used, free = WindowsAPI.get_disk_free_space(f"{letter}:")

                percent = (used / total * 100) if total > 0 else 0

                drives.append(
                    DriveInfo(
                        letter=letter,
                        label=vol_name.value or f"Drive ({letter}:)",
                        filesystem=fs_name.value or "Unknown",
                        total_bytes=total,
                        used_bytes=used,
                        free_bytes=free,
                        percent_used=round(percent, 1),
                    )
                )

            except Exception as e:
                logger.debug(f"Failed to get info for drive {letter}: {e}")
                continue

        return drives

    @staticmethod
    def get_drive_info(drive_letter: str) -> DriveInfo | None:
        """Get info for a specific drive."""
        drives = DiskUtils.get_all_drives()
        for d in drives:
            if d.letter == drive_letter.upper():
                return d
        return None

    @staticmethod
    def get_folder_disk_usage(path: str) -> dict[str, int | str]:
        """
        Analyze disk usage of a folder and its subfolders.

        Returns:
            Dict with size breakdown.
        """
        result: dict[str, int | str] = {
            "path": path,
            "total_size": 0,
            "file_count": 0,
            "folder_count": 0,
        }

        try:
            for dirpath, dirnames, filenames in os.walk(path):
                result["folder_count"] = int(result["folder_count"]) + len(dirnames)
                for fname in filenames:
                    fpath = os.path.join(dirpath, fname)
                    try:
                        result["total_size"] = int(result["total_size"]) + os.path.getsize(fpath)
                        result["file_count"] = int(result["file_count"]) + 1
                    except (OSError, PermissionError):
                        continue
        except (OSError, PermissionError):
            pass

        result["display_size"] = PathUtils.format_size(int(result["total_size"]))
        return result
