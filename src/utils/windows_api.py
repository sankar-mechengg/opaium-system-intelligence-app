"""
OP(AI)UM — Windows API Helpers

Wrappers around Windows COM API, Shell32, and kernel32 functions
for resolving shortcuts, getting file attributes, and system info.
"""

from __future__ import annotations

import contextlib
import ctypes
import ctypes.wintypes
import os
from pathlib import Path
from typing import cast

from loguru import logger


class WindowsAPI:
    """Windows-specific API wrappers."""

    @staticmethod
    def resolve_lnk_target(lnk_path: str | Path, resolve_moved: bool = True) -> str | None:
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
            from win32com.shell import shell

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

                # Fast path: the stored target usually still exists — no Resolve needed.
                target_path, _ = shortcut.GetPath(shell.SLGP_RAWPATH)
                if target_path and os.path.exists(str(target_path)):
                    return cast(str, target_path)
                if not resolve_moved:
                    return None

                # Slow path (target moved/renamed): let the shell track it down.
                # pywin32's shellcon does not export SLR_* flags; SDK values are used.
                # SLR_NO_UI (0x1): never show a dialog; high word = timeout in ms.
                SLR_NO_UI = 0x0001
                timeout_ms = 200
                with contextlib.suppress(Exception):
                    shortcut.Resolve(0, SLR_NO_UI | (timeout_ms << 16))

                target_path, _ = shortcut.GetPath(shell.SLGP_RAWPATH)

                if target_path and os.path.exists(str(target_path)):
                    return cast(str, target_path)
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
    def _resolve_lnk_fallback(lnk_path: str | Path) -> str | None:
        """Fallback .lnk resolution using pylnk3."""
        try:
            import pylnk3

            lnk = pylnk3.parse(str(lnk_path))
            target = lnk.path
            if target and os.path.exists(str(target)):
                return cast(str, target)

            # Try with working directory
            work_dir = lnk.work_dir
            if work_dir and os.path.exists(str(work_dir)):
                return cast(str, work_dir)

            return None
        except Exception as e:
            logger.debug(f"pylnk3 fallback failed for {lnk_path}: {e}")
            return None

    @staticmethod
    def get_file_attributes(path: str | Path) -> int | None:
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
    def get_file_id(path: str | Path) -> int | None:
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
                    file_id = int((info.nFileIndexHigh << 32) | info.nFileIndexLow)
                    return file_id
                return None
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[union-attr]
        except Exception as e:
            logger.debug(f"Failed to get file ID for {path}: {e}")
            return None

    @staticmethod
    def get_volume_serial(path: str | Path) -> int | None:
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
                None,
                0,
                ctypes.byref(serial),
                None,
                None,
                None,
                0,
            )
            return serial.value if result else None
        except Exception:
            return None

    @staticmethod
    def add_to_startup(app_path: str, minimized: bool = True) -> bool:
        """
        Add application to Windows startup via registry (HKCU Run key).

        Args:
            app_path: Full path to the .exe (or the entry script when not frozen).
            minimized: Pass --minimized so the app starts in the tray.

        Returns:
            True if successful.
        """
        try:
            import sys
            import winreg

            if getattr(sys, "frozen", False):
                command = f'"{app_path}"'
            else:
                command = f'"{sys.executable}" "{app_path}"'
            if minimized:
                command += " --minimized"

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            )
            winreg.SetValueEx(key, "OPAIUM", 0, winreg.REG_SZ, command)
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
            with contextlib.suppress(FileNotFoundError):
                winreg.DeleteValue(key, "OPAIUM")
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


# === Known folders ===

# FOLDERID GUIDs (KnownFolders.h) — resolved through the shell so OneDrive /
# policy redirection of Desktop, Documents and Pictures is honoured.
_KNOWN_FOLDER_IDS: dict[str, str] = {
    "Desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
    "Documents": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
    "Downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
    "Pictures": "{33E28130-4E1E-4676-835A-98395C3BC3BB}",
    "Videos": "{18989B1D-99B5-455B-841C-AB7C74E4DDFC}",
    "Music": "{4BD8D571-6D19-48D3-BE97-422220080E43}",
}


def known_folder_path(folder_id: str) -> str | None:
    """Resolve a FOLDERID GUID with SHGetKnownFolderPath. Returns None when unavailable."""
    try:
        import ctypes.wintypes as wt
        import uuid

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wt.DWORD),
                ("Data2", wt.WORD),
                ("Data3", wt.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        u = uuid.UUID(folder_id)
        guid = GUID()
        guid.Data1, guid.Data2, guid.Data3 = u.time_low, u.time_mid, u.time_hi_version
        for i, b in enumerate(u.bytes[8:]):
            guid.Data4[i] = b

        path_ptr = ctypes.c_wchar_p()
        shell32 = ctypes.windll.shell32
        if shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(path_ptr)) != 0:
            return None
        try:
            return path_ptr.value
        finally:
            ctypes.windll.ole32.CoTaskMemFree(path_ptr)
    except Exception:
        return None


def known_user_folders() -> dict[str, str]:
    """Name -> path for the standard user folders that exist, in display order."""
    result: dict[str, str] = {}
    profile = os.environ.get("USERPROFILE", "")
    for name, folder_id in _KNOWN_FOLDER_IDS.items():
        path = known_folder_path(folder_id) or (os.path.join(profile, name) if profile else "")
        if path and os.path.isdir(path):
            result[name] = path
    return result
