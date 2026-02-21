"""
OP(AI)UM — Windows API Helpers

Wrappers around Windows COM API, Shell32, and kernel32 functions
for resolving shortcuts, getting file attributes, and system info.
"""

from __future__ import annotations

import os
import ctypes
import ctypes.wintypes
from pathlib import Path
from typing import Optional

from loguru import logger


class WindowsAPI:
    """Windows-specific API wrappers."""

    @staticmethod
    def resolve_lnk_target(lnk_path: str | Path) -> Optional[str]:
        """
        Resolve a .lnk shortcut file to its target path using COM Shell API.

        This is the most reliable method as it handles:
        - Renamed targets (via file ID tracking)
        - Moved targets (within same drive)
        - Network paths

        Args:
            lnk_path: Path to the .lnk file.

        Returns:
            Resolved target path, or None if unresolvable.
        """
        try:
            import pythoncom
            from win32com.shell import shell, shellcon

            pythoncom.CoInitialize()
            try:
                shortcut = pythoncom.CoCreateInstance(
                    shell.CLSID_ShellLink,
                    None,
                    pythoncom.CLSCTX_INPROC_SERVER,
                    shell.IID_IShellLink,
                )

                persist_file = shortcut.QueryInterface(pythoncom.IID_IPersistFile)
                persist_file.Load(str(lnk_path), 0)

                # SLR_UPDATE: Update the link if target has moved
                # SLR_NO_UI: Don't show dialog if target not found
                shortcut.Resolve(0, shellcon.SLR_UPDATE | shellcon.SLR_NO_UI)

                target_path, _ = shortcut.GetPath(shell.SLGP_RAWPATH)

                if target_path and os.path.exists(target_path):
                    return target_path
                return None
            finally:
                pythoncom.CoUninitialize()
        except ImportError:
            logger.warning("pywin32 not available. Falling back to pylnk3.")
            return WindowsAPI._resolve_lnk_fallback(lnk_path)
        except Exception as e:
            logger.debug(f"Failed to resolve .lnk via COM: {lnk_path} -> {e}")
            return WindowsAPI._resolve_lnk_fallback(lnk_path)

    @staticmethod
    def _resolve_lnk_fallback(lnk_path: str | Path) -> Optional[str]:
        """Fallback .lnk resolution using pylnk3."""
        try:
            import pylnk3

            lnk = pylnk3.parse(str(lnk_path))
            target = lnk.path
            if target and os.path.exists(target):
                return target

            # Try with working directory
            work_dir = lnk.work_dir
            if work_dir and os.path.exists(work_dir):
                return work_dir

            return None
        except Exception as e:
            logger.debug(f"pylnk3 fallback failed for {lnk_path}: {e}")
            return None

    @staticmethod
    def get_file_attributes(path: str | Path) -> Optional[int]:
        """
        Get Windows file attributes for a path.

        Returns:
            File attributes bitmask, or None if failed.
        """
        try:
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))  # type: ignore[union-attr]
            return attrs if attrs != -1 else None
        except Exception:
            return None

    @staticmethod
    def is_folder_target(lnk_path: str | Path) -> bool:
        """
        Check if a .lnk file points to a folder (not a file).

        Args:
            lnk_path: Path to the .lnk file.

        Returns:
            True if the target is a directory.
        """
        target = WindowsAPI.resolve_lnk_target(lnk_path)
        if target:
            return os.path.isdir(target)
        return False

    @staticmethod
    def get_file_id(path: str | Path) -> Optional[int]:
        """
        Get the NTFS file ID (unique within a volume).

        This ID persists across renames and moves within the same drive.

        Args:
            path: Path to get ID for.

        Returns:
            File ID as integer, or None.
        """
        try:
            GENERIC_READ = 0x80000000
            FILE_SHARE_READ = 0x01
            OPEN_EXISTING = 3
            FILE_FLAG_BACKUP_SEMANTICS = 0x02000000

            handle = ctypes.windll.kernel32.CreateFileW(  # type: ignore[union-attr]
                str(path),
                GENERIC_READ,
                FILE_SHARE_READ,
                None,
                OPEN_EXISTING,
                FILE_FLAG_BACKUP_SEMANTICS,  # Required for directories
                None,
            )

            if handle == -1:
                return None

            try:

                class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
                    _fields_ = [
                        ("dwFileAttributes", ctypes.wintypes.DWORD),
                        ("ftCreationTime", ctypes.wintypes.FILETIME),
                        ("ftLastAccessTime", ctypes.wintypes.FILETIME),
                        ("ftLastWriteTime", ctypes.wintypes.FILETIME),
                        ("dwVolumeSerialNumber", ctypes.wintypes.DWORD),
                        ("nFileSizeHigh", ctypes.wintypes.DWORD),
                        ("nFileSizeLow", ctypes.wintypes.DWORD),
                        ("nNumberOfLinks", ctypes.wintypes.DWORD),
                        ("nFileIndexHigh", ctypes.wintypes.DWORD),
                        ("nFileIndexLow", ctypes.wintypes.DWORD),
                    ]

                info = BY_HANDLE_FILE_INFORMATION()
                result = ctypes.windll.kernel32.GetFileInformationByHandle(  # type: ignore[union-attr]
                    handle, ctypes.byref(info)
                )

                if result:
                    file_id = (info.nFileIndexHigh << 32) | info.nFileIndexLow
                    return file_id
                return None
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[union-attr]
        except Exception as e:
            logger.debug(f"Failed to get file ID for {path}: {e}")
            return None

    @staticmethod
    def get_volume_serial(path: str | Path) -> Optional[int]:
        """
        Get the volume serial number for the drive containing this path.

        Args:
            path: Any path on the volume.

        Returns:
            Volume serial number, or None.
        """
        try:
            drive = os.path.splitdrive(str(Path(path).resolve()))[0] + "\\"
            serial = ctypes.wintypes.DWORD()
            result = ctypes.windll.kernel32.GetVolumeInformationW(  # type: ignore[union-attr]
                drive,
                None, 0,
                ctypes.byref(serial),
                None, None,
                None, 0,
            )
            return serial.value if result else None
        except Exception:
            return None

    @staticmethod
    def add_to_startup(app_path: str) -> bool:
        """
        Add application to Windows startup via registry.

        Args:
            app_path: Full path to the .exe file.

        Returns:
            True if successful.
        """
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            )
            winreg.SetValueEx(key, "OPAIUM", 0, winreg.REG_SZ, f'"{app_path}"')
            winreg.CloseKey(key)
            logger.info(f"Added to Windows startup: {app_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to add to startup: {e}")
            return False

    @staticmethod
    def remove_from_startup() -> bool:
        """Remove application from Windows startup."""
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            )
            try:
                winreg.DeleteValue(key, "OPAIUM")
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
            logger.info("Removed from Windows startup.")
            return True
        except Exception as e:
            logger.error(f"Failed to remove from startup: {e}")
            return False

    @staticmethod
    def get_disk_free_space(drive: str = "C:") -> tuple[int, int, int]:
        """
        Get disk space information.

        Args:
            drive: Drive letter with colon (e.g., "C:").

        Returns:
            Tuple of (total_bytes, used_bytes, free_bytes).
        """
        try:
            free_bytes = ctypes.c_ulonglong(0)
            total_bytes = ctypes.c_ulonglong(0)
            free_to_caller = ctypes.c_ulonglong(0)

            ctypes.windll.kernel32.GetDiskFreeSpaceExW(  # type: ignore[union-attr]
                drive + "\\",
                ctypes.byref(free_to_caller),
                ctypes.byref(total_bytes),
                ctypes.byref(free_bytes),
            )

            total = total_bytes.value
            free = free_bytes.value
            used = total - free
            return total, used, free
        except Exception:
            return 0, 0, 0
