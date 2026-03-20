"""
OP(AI)UM — Recycle Bin Manager

Query and manage the Windows Recycle Bin.
Provides information about bin contents and space usage.
"""

from __future__ import annotations

from typing import NamedTuple

from loguru import logger

from src.utils.path_utils import PathUtils


class RecycleBinInfo(NamedTuple):
    """Information about the Recycle Bin."""

    item_count: int
    total_size_bytes: int
    display_size: str


class RecycleBinItem(NamedTuple):
    """A single item in the Recycle Bin."""

    original_path: str
    name: str
    size_bytes: int
    deleted_at: str
    is_folder: bool


class RecycleBinManager:
    """
    Queries and manages the Windows Recycle Bin.
    Uses shell32 COM API for reliable access.
    """

    @staticmethod
    def get_info() -> RecycleBinInfo:
        """
        Get summary information about the Recycle Bin.

        Returns:
            RecycleBinInfo with count and size.
        """
        try:
            import ctypes
            from ctypes import wintypes

            class SHQUERYRBINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("i64Size", ctypes.c_longlong),
                    ("i64NumItems", ctypes.c_longlong),
                ]

            info = SHQUERYRBINFO()
            info.cbSize = ctypes.sizeof(SHQUERYRBINFO)

            result = ctypes.windll.shell32.SHQueryRecycleBinW(
                None,
                ctypes.byref(info),
            )

            if result == 0:  # S_OK
                return RecycleBinInfo(
                    item_count=info.i64NumItems,
                    total_size_bytes=info.i64Size,
                    display_size=PathUtils.format_size(info.i64Size),
                )

        except Exception as e:
            logger.error(f"Failed to query Recycle Bin: {e}")

        return RecycleBinInfo(item_count=0, total_size_bytes=0, display_size="0 B")

    @staticmethod
    def empty(confirm: bool = True) -> bool:
        """
        Empty the Recycle Bin.

        Args:
            confirm: Show Windows confirmation dialog.

        Returns:
            True if successful.
        """
        try:
            import ctypes

            flags = 0
            if not confirm:
                SHERB_NOCONFIRMATION = 0x00000001
                SHERB_NOPROGRESSUI = 0x00000002
                SHERB_NOSOUND = 0x00000004
                flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND

            result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
            success: bool = result == 0
            if success:
                logger.info("Recycle Bin emptied.")
            return success

        except Exception as e:
            logger.error(f"Failed to empty Recycle Bin: {e}")
            return False

    @staticmethod
    def get_items() -> list[RecycleBinItem]:
        """
        List items in the Recycle Bin using COM Shell API.

        Returns:
            List of RecycleBinItem.
        """
        items: list[RecycleBinItem] = []

        try:
            import pythoncom
            from win32com.shell import shell, shellcon

            pythoncom.CoInitialize()
            try:
                desktop = shell.SHGetDesktopFolder()

                # Get Recycle Bin PIDL
                pidl = shell.SHGetSpecialFolderLocation(0, shellcon.CSIDL_BITBUCKET)
                recycle_bin = desktop.BindToObject(pidl, None, shell.IID_IShellFolder)

                # Enumerate items
                enum = recycle_bin.EnumObjects(0, shellcon.SHCONTF_FOLDERS | shellcon.SHCONTF_NONFOLDERS)

                if enum:
                    while True:
                        try:
                            pidls = enum.Next(1)
                            if not pidls:
                                break

                            for item_pidl in pidls:
                                try:
                                    name = recycle_bin.GetDisplayNameOf(
                                        item_pidl,
                                        shellcon.SHGDN_NORMAL,
                                    )
                                    items.append(
                                        RecycleBinItem(
                                            original_path="",
                                            name=name or "<unknown>",
                                            size_bytes=0,
                                            deleted_at="",
                                            is_folder=False,
                                        )
                                    )
                                except Exception:
                                    continue
                        except StopIteration:
                            break
                        except Exception:
                            break

            finally:
                pythoncom.CoUninitialize()

        except ImportError:
            logger.debug("pywin32 not available for Recycle Bin enumeration.")
        except Exception as e:
            logger.error(f"Failed to enumerate Recycle Bin: {e}")

        return items
