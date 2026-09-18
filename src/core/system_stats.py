"""
OP(AI)UM — System Statistics

Live CPU / memory / uptime figures (psutil) and background folder-size
scans used by the dashboard. All heavy work is meant to run on the thread pool.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

from src.core.disk_utils import DiskUtils, DriveInfo
from src.core.startup_manager import StartupEntry, StartupManager
from src.utils.path_utils import PathUtils


@dataclass
class LiveStats:
    cpu_percent: float = 0.0
    cpu_count: int = 0
    memory_percent: float = 0.0
    memory_used: int = 0
    memory_total: int = 0
    uptime: timedelta = field(default_factory=lambda: timedelta(0))
    process_count: int = 0
    available: bool = False


@dataclass
class FolderSize:
    path: str
    name: str
    size_bytes: int
    file_count: int


@dataclass
class DashboardSnapshot:
    drives: list[DriveInfo] = field(default_factory=list)
    folder_sizes: list[FolderSize] = field(default_factory=list)
    startup_entries: list[StartupEntry] = field(default_factory=list)
    recycle_count: int = 0
    recycle_size: int = 0


def live_stats() -> LiveStats:
    """Cheap, near-instant stats for the live tiles."""
    try:
        import psutil
    except ImportError:
        return LiveStats(available=False)
    try:
        vm = psutil.virtual_memory()
        boot = datetime.fromtimestamp(psutil.boot_time())
        return LiveStats(
            cpu_percent=float(psutil.cpu_percent(interval=None)),
            cpu_count=int(psutil.cpu_count(logical=True) or 0),
            memory_percent=float(vm.percent),
            memory_used=int(vm.used),
            memory_total=int(vm.total),
            uptime=datetime.now() - boot,
            process_count=len(psutil.pids()),
            available=True,
        )
    except Exception as e:
        logger.debug(f"psutil stats failed: {e}")
        return LiveStats(available=False)


def folder_size(path: str, max_files: int = 400_000) -> FolderSize:
    total = 0
    count = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            # Skip reparse points / junctions to avoid loops
            dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
            for f in filenames:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                    count += 1
                except OSError:
                    continue
                if count >= max_files:
                    raise StopIteration
    except StopIteration:
        pass
    except (OSError, PermissionError):
        pass
    return FolderSize(path=path, name=Path(path).name or path, size_bytes=total, file_count=count)


def user_folders() -> list[str]:
    profile = os.environ.get("USERPROFILE", "")
    if not profile:
        return []
    names = ["Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music"]
    folders = [os.path.join(profile, n) for n in names]
    # OneDrive redirection
    one_drive = os.environ.get("ONEDRIVE", "")
    if one_drive and os.path.isdir(one_drive):
        folders.append(one_drive)
    return [f for f in folders if os.path.isdir(f)]


def snapshot(include_folder_sizes: bool = True) -> DashboardSnapshot:
    """Heavier snapshot for the dashboard (run on a worker thread)."""
    snap = DashboardSnapshot()
    try:
        snap.drives = DiskUtils.get_all_drives()
    except Exception as e:
        logger.debug(f"Drive listing failed: {e}")
    try:
        snap.startup_entries = StartupManager.get_all_entries()
    except Exception as e:
        logger.debug(f"Startup listing failed: {e}")
    try:
        from src.core.recycle_bin import RecycleBinManager

        info = RecycleBinManager.get_info()
        snap.recycle_count = info.item_count
        snap.recycle_size = info.total_size_bytes
    except Exception:
        pass
    if include_folder_sizes:
        sizes = [folder_size(p) for p in user_folders()]
        snap.folder_sizes = sorted(sizes, key=lambda s: s.size_bytes, reverse=True)
    return snap


def format_uptime(delta: timedelta) -> str:
    total = int(delta.total_seconds())
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def format_size(n: int) -> str:
    return PathUtils.format_size(n)
