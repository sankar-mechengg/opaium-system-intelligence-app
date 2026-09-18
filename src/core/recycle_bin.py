"""
OP(AI)UM — Recycle Bin Manager

Query, enumerate, restore from and empty the Windows Recycle Bin.
Uses shell32 for the summary and the Shell.Application COM object for
item-level access (original location, size, restore verb).
"""

from __future__ import annotations

import contextlib
import os
from typing import Any, NamedTuple

from loguru import logger

from src.utils.path_utils import PathUtils

# Shell folder id for the Recycle Bin (ssfBITBUCKET)
_SSF_BITBUCKET = 10
# Column indexes returned by Folder.GetDetailsOf for the Recycle Bin view
_COL_ORIGINAL_LOCATION = 1
_COL_DATE_DELETED = 2
_COL_SIZE = 3


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


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(path.strip()))


class RecycleBinManager:
    """
    Queries and manages the Windows Recycle Bin.
    """

    @staticmethod
    def get_info() -> RecycleBinInfo:
        """Summary information (count and size) for all drives."""
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

            result = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))

            if result == 0:  # S_OK
                return RecycleBinInfo(
                    item_count=int(info.i64NumItems),
                    total_size_bytes=int(info.i64Size),
                    display_size=PathUtils.format_size(int(info.i64Size)),
                )

        except Exception as e:
            logger.error(f"Failed to query Recycle Bin: {e}")

        return RecycleBinInfo(item_count=0, total_size_bytes=0, display_size="0 B")

    @staticmethod
    def empty(confirm: bool = True) -> bool:
        """Empty the Recycle Bin."""
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

    # === COM helpers ===

    @staticmethod
    @contextlib.contextmanager
    def _shell_folder() -> Any:
        """Yield the Recycle Bin Folder object (Shell.Application) inside a COM apartment."""
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        try:
            shell = win32com.client.Dispatch("Shell.Application")
            folder = shell.NameSpace(_SSF_BITBUCKET)
            yield folder
        finally:
            pythoncom.CoUninitialize()

    @staticmethod
    def _parse_size(text: str) -> int:
        """Best-effort parse of a localized size string such as '1.2 MB'."""
        try:
            parts = text.replace("‎", "").split()
            if not parts:
                return 0
            value = float(parts[0].replace(",", ""))
            unit = parts[1].upper() if len(parts) > 1 else "B"
            mult = {"B": 1, "BYTES": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}.get(unit, 1)
            return int(value * mult)
        except Exception:
            return 0

    @staticmethod
    def get_items(limit: int = 500) -> list[RecycleBinItem]:
        """List items in the Recycle Bin with their original locations."""
        items: list[RecycleBinItem] = []
        try:
            with RecycleBinManager._shell_folder() as folder:
                if folder is None:
                    return items
                shell_items = folder.Items()
                count = min(shell_items.Count, limit)
                for i in range(count):
                    try:
                        it = shell_items.Item(i)
                        name = str(it.Name)
                        original_dir = str(folder.GetDetailsOf(it, _COL_ORIGINAL_LOCATION))
                        deleted_at = str(folder.GetDetailsOf(it, _COL_DATE_DELETED))
                        size_text = str(folder.GetDetailsOf(it, _COL_SIZE))
                        items.append(
                            RecycleBinItem(
                                original_path=os.path.join(original_dir, name) if original_dir else name,
                                name=name,
                                size_bytes=RecycleBinManager._parse_size(size_text),
                                deleted_at=deleted_at,
                                is_folder=bool(it.IsFolder),
                            )
                        )
                    except Exception:
                        continue
        except ImportError:
            logger.debug("pywin32 not available for Recycle Bin enumeration.")
        except Exception as e:
            logger.error(f"Failed to enumerate Recycle Bin: {e}")
        return items

    @staticmethod
    def restore(original_paths: list[str]) -> tuple[int, list[str]]:
        """
        Restore items whose original full path matches one of `original_paths`.

        Returns:
            (restored_count, paths_not_found)
        """
        wanted = {_norm(p): p for p in original_paths if p}
        restored = 0
        if not wanted:
            return 0, []

        try:
            with RecycleBinManager._shell_folder() as folder:
                if folder is None:
                    return 0, list(wanted.values())
                shell_items = folder.Items()
                # Iterate newest first so a re-deleted file restores its latest copy.
                indices = list(range(shell_items.Count))
                for i in reversed(indices):
                    if not wanted:
                        break
                    try:
                        it = shell_items.Item(i)
                        name = str(it.Name)
                        original_dir = str(folder.GetDetailsOf(it, _COL_ORIGINAL_LOCATION))
                        full = _norm(os.path.join(original_dir, name)) if original_dir else _norm(name)
                        if full not in wanted:
                            continue
                        if RecycleBinManager._invoke_restore(it):
                            restored += 1
                            wanted.pop(full, None)
                    except Exception as e:
                        logger.debug(f"Recycle Bin item skip: {e}")
                        continue
        except ImportError:
            logger.warning("pywin32 not available — cannot restore from Recycle Bin.")
        except Exception as e:
            logger.error(f"Recycle Bin restore failed: {e}")

        return restored, list(wanted.values())

    @staticmethod
    def _invoke_restore(item: Any) -> bool:
        """Invoke the 'Restore' verb on a Recycle Bin shell item."""
        try:
            verbs = item.Verbs()
            chosen = None
            fallback = None
            for j in range(verbs.Count):
                verb = verbs.Item(j)
                name = str(verb.Name).replace("&", "").strip().lower()
                if name in ("restore", "restaurer", "wiederherstellen", "restaurar", "ripristina", "herstellen"):
                    chosen = verb
                    break
                if fallback is None and name and "delete" not in name and "cut" not in name and "propert" not in name:
                    fallback = verb
            verb = chosen or fallback
            if verb is None:
                return False
            verb.DoIt()
            return True
        except Exception as e:
            logger.debug(f"Restore verb failed: {e}")
            return False
