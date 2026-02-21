"""
OP(AI)UM — LNK Shortcut Resolver

Dedicated module for resolving Windows .lnk shortcut files.
Uses COM Shell API as primary method with pylnk3 as fallback.
Includes batch resolution and caching for performance.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, NamedTuple

from loguru import logger


class LnkInfo(NamedTuple):
    """Resolved information from a .lnk file."""
    target_path: str
    working_dir: str
    arguments: str
    description: str
    icon_location: str
    is_directory: bool
    exists: bool
    created_at: Optional[datetime]
    modified_at: Optional[datetime]


class LnkResolver:
    """
    Resolves .lnk shortcut files to their targets.
    Caches results for performance during bulk operations.
    """

    def __init__(self) -> None:
        self._cache: dict[str, Optional[LnkInfo]] = {}
        self._com_available: Optional[bool] = None

    def resolve(self, lnk_path: str | Path) -> Optional[LnkInfo]:
        """
        Resolve a .lnk file to its target information.

        Args:
            lnk_path: Path to the .lnk file.

        Returns:
            LnkInfo with resolved data, or None if unresolvable.
        """
        lnk_str = str(lnk_path)

        # Check cache
        if lnk_str in self._cache:
            return self._cache[lnk_str]

        result = self._resolve_via_com(lnk_str)
        if result is None:
            result = self._resolve_via_pylnk(lnk_str)

        self._cache[lnk_str] = result
        return result

    def resolve_target_path(self, lnk_path: str | Path) -> Optional[str]:
        """
        Quick method to just get the target path.

        Args:
            lnk_path: Path to the .lnk file.

        Returns:
            Target path string, or None.
        """
        info = self.resolve(lnk_path)
        if info and info.exists:
            return info.target_path
        return None

    def batch_resolve(self, lnk_paths: list[str | Path]) -> dict[str, Optional[LnkInfo]]:
        """
        Resolve multiple .lnk files efficiently.

        Args:
            lnk_paths: List of .lnk file paths.

        Returns:
            Dict mapping lnk path → LnkInfo.
        """
        results: dict[str, Optional[LnkInfo]] = {}

        # Initialize COM once for all resolutions
        com_initialized = False
        try:
            import pythoncom
            pythoncom.CoInitialize()
            com_initialized = True
        except Exception:
            pass

        try:
            for lnk_path in lnk_paths:
                results[str(lnk_path)] = self.resolve(lnk_path)
        finally:
            if com_initialized:
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

        return results

    def _resolve_via_com(self, lnk_path: str) -> Optional[LnkInfo]:
        """Resolve using Windows COM Shell API."""
        if self._com_available is False:
            return None

        try:
            import pythoncom
            from win32com.shell import shell, shellcon

            # Don't re-initialize COM if already initialized
            try:
                pythoncom.CoInitialize()
                should_uninit = True
            except Exception:
                should_uninit = False

            try:
                shortcut = pythoncom.CoCreateInstance(
                    shell.CLSID_ShellLink,
                    None,
                    pythoncom.CLSCTX_INPROC_SERVER,
                    shell.IID_IShellLink,
                )

                persist = shortcut.QueryInterface(pythoncom.IID_IPersistFile)
                persist.Load(lnk_path, 0)

                # Resolve with auto-update and no UI
                try:
                    shortcut.Resolve(0, shellcon.SLR_UPDATE | shellcon.SLR_NO_UI | shellcon.SLR_NOSEARCH)
                except Exception:
                    # Fallback: try without SLR_NOSEARCH
                    try:
                        shortcut.Resolve(0, shellcon.SLR_NO_UI)
                    except Exception:
                        pass

                target_path, _ = shortcut.GetPath(shell.SLGP_RAWPATH)
                working_dir = shortcut.GetWorkingDirectory()
                arguments = shortcut.GetArguments()
                description = shortcut.GetDescription()

                icon_location, _ = shortcut.GetIconLocation()

                is_dir = os.path.isdir(target_path) if target_path else False
                exists = os.path.exists(target_path) if target_path else False

                # Get timestamps from target
                created_at = None
                modified_at = None
                if exists:
                    try:
                        stat = os.stat(target_path)
                        created_at = datetime.fromtimestamp(stat.st_ctime)
                        modified_at = datetime.fromtimestamp(stat.st_mtime)
                    except OSError:
                        pass

                self._com_available = True

                if not target_path:
                    return None

                return LnkInfo(
                    target_path=target_path,
                    working_dir=working_dir or "",
                    arguments=arguments or "",
                    description=description or "",
                    icon_location=icon_location or "",
                    is_directory=is_dir,
                    exists=exists,
                    created_at=created_at,
                    modified_at=modified_at,
                )

            finally:
                if should_uninit:
                    try:
                        pythoncom.CoUninitialize()
                    except Exception:
                        pass

        except ImportError:
            self._com_available = False
            logger.debug("pywin32 COM not available for .lnk resolution.")
            return None
        except Exception as e:
            logger.debug(f"COM resolution failed for {lnk_path}: {e}")
            return None

    def _resolve_via_pylnk(self, lnk_path: str) -> Optional[LnkInfo]:
        """Resolve using pylnk3 as fallback."""
        try:
            import pylnk3

            lnk = pylnk3.parse(lnk_path)

            target_path = lnk.path or ""
            working_dir = lnk.work_dir or ""
            arguments = lnk.arguments or ""
            description = lnk.description or ""
            icon_location = lnk.icon or ""

            # pylnk3 paths may use environment variables
            if target_path:
                target_path = os.path.expandvars(target_path)

            # Try working directory if target doesn't exist
            if not target_path or not os.path.exists(target_path):
                if working_dir and os.path.exists(working_dir):
                    target_path = working_dir

            exists = os.path.exists(target_path) if target_path else False
            is_dir = os.path.isdir(target_path) if exists else False

            created_at = None
            modified_at = None
            if exists:
                try:
                    stat = os.stat(target_path)
                    created_at = datetime.fromtimestamp(stat.st_ctime)
                    modified_at = datetime.fromtimestamp(stat.st_mtime)
                except OSError:
                    pass

            if not target_path:
                return None

            return LnkInfo(
                target_path=target_path,
                working_dir=working_dir,
                arguments=arguments,
                description=description,
                icon_location=icon_location,
                is_directory=is_dir,
                exists=exists,
                created_at=created_at,
                modified_at=modified_at,
            )

        except ImportError:
            logger.error("pylnk3 not available. Cannot resolve .lnk files.")
            return None
        except Exception as e:
            logger.debug(f"pylnk3 resolution failed for {lnk_path}: {e}")
            return None

    def clear_cache(self) -> None:
        """Clear the resolution cache."""
        self._cache.clear()

    def invalidate(self, lnk_path: str | Path) -> None:
        """Remove a specific entry from the cache."""
        self._cache.pop(str(lnk_path), None)
