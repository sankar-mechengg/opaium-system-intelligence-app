"""
OP(AI)UM — Safety Guards

Two independent protections for destructive AI tool calls:

1. PathGuard — refuses destructive operations that target system-critical
   locations (Windows, Program Files, drive roots, the user profile root,
   OP(AI)UM's own data directory, ...). Always on.

2. ApprovalRequest — a synchronous hand-off between the background tool
   thread and the UI thread. The executor blocks on it until the user
   approves or rejects the previewed operation (or it times out).
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config.constants import AppConstants

# Argument names that carry filesystem paths in tool schemas.
PATH_ARG_KEYS = {
    "directory",
    "path",
    "source",
    "destination",
    "folder",
    "target",
    "source_directory",
    "destination_directory",
    "dest",
    "root",
    "output_directory",
}


class PathGuard:
    """Decides whether a destructive operation may touch a path."""

    _cached_roots: list[Path] | None = None
    _cached_exact: list[Path] | None = None

    @classmethod
    def _build(cls) -> None:
        if cls._cached_roots is not None:
            return

        env = os.environ
        roots: list[Path] = []
        exact: list[Path] = []

        def add_root(value: str | None) -> None:
            if value:
                roots.append(Path(value))

        def add_exact(value: str | None) -> None:
            if value:
                exact.append(Path(value))

        # Whole subtrees that are never a valid target for the AI
        add_root(env.get("SystemRoot") or env.get("WINDIR") or r"C:\Windows")
        add_root(env.get("ProgramFiles"))
        add_root(env.get("ProgramFiles(x86)"))
        add_root(env.get("ProgramW6432"))
        add_root(env.get("ProgramData"))
        roots.append(AppConstants.APPDATA_DIR)
        add_root(env.get("SystemDrive", "C:") + r"\System Volume Information")
        add_root(env.get("SystemDrive", "C:") + r"\$Recycle.Bin")
        add_root(env.get("SystemDrive", "C:") + r"\Recovery")

        # Exact locations: operating directly on them is refused, but children are fine.
        add_exact(env.get("USERPROFILE"))
        add_exact(env.get("APPDATA"))
        add_exact(env.get("LOCALAPPDATA"))
        add_exact(env.get("HOMEDRIVE", "C:") + env.get("HOMEPATH", ""))
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            exact.append(Path(f"{letter}:\\"))
        add_exact(env.get("PUBLIC"))
        if env.get("USERPROFILE"):
            users_root = Path(env["USERPROFILE"]).parent
            exact.append(users_root)

        cls._cached_roots = [p for p in roots if str(p)]
        cls._cached_exact = [p for p in exact if str(p)]

    @staticmethod
    def _norm(path: str | Path) -> str:
        try:
            return os.path.normcase(os.path.normpath(os.path.abspath(str(path))))
        except Exception:
            return os.path.normcase(str(path))

    @classmethod
    def is_protected(cls, path: str | Path) -> bool:
        """True when a destructive operation must not touch `path`."""
        if not path:
            return False
        cls._build()
        assert cls._cached_roots is not None and cls._cached_exact is not None
        target = cls._norm(path)

        for exact in cls._cached_exact:
            if target == cls._norm(exact):
                return True

        for root in cls._cached_roots:
            r = cls._norm(root)
            if target == r or target.startswith(r.rstrip("\\") + "\\"):
                return True

        return False

    @classmethod
    def find_protected(cls, arguments: dict[str, Any]) -> list[str]:
        """Return every path-like argument value that resolves to a protected location."""
        hits: list[str] = []
        for key, value in arguments.items():
            if key not in PATH_ARG_KEYS:
                continue
            if isinstance(value, str) and value.strip():
                if cls.is_protected(value):
                    hits.append(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item.strip() and cls.is_protected(item):
                        hits.append(item)
        return hits

    @classmethod
    def reset_cache(cls) -> None:
        cls._cached_roots = None
        cls._cached_exact = None


@dataclass
class ApprovalRequest:
    """
    Cross-thread approval hand-off.

    The worker thread creates one, the UI thread shows a dialog and calls
    `resolve(True/False)`, and the worker resumes from `wait()`.
    """

    tool_name: str
    arguments: dict[str, Any]
    title: str
    preview_lines: list[str]
    affected_count: int = 0
    _event: threading.Event = field(default_factory=threading.Event, repr=False)
    _approved: bool = field(default=False, repr=False)
    _remember: bool = field(default=False, repr=False)

    def resolve(self, approved: bool, remember_for_session: bool = False) -> None:
        self._approved = approved
        self._remember = remember_for_session
        self._event.set()

    def wait(self, timeout: float | None = None) -> bool:
        """Block until resolved. Returns False on timeout (treated as rejection)."""
        return self._event.wait(timeout)

    @property
    def approved(self) -> bool:
        return self._approved

    @property
    def remember_for_session(self) -> bool:
        return self._remember


class ApprovalBroker:
    """
    Registry that lets the executor (worker thread) request approval and the
    chat panel (UI thread) answer it. The engine wires `handler` to a Qt signal.
    """

    def __init__(self) -> None:
        self._handler: Any | None = None
        self._session_trusted_tools: set[str] = set()
        self._lock = threading.Lock()

    def set_handler(self, handler: Any | None) -> None:
        """handler(request: ApprovalRequest) -> None — must not block; runs on the caller thread."""
        self._handler = handler

    @property
    def has_handler(self) -> bool:
        return self._handler is not None

    def is_trusted(self, tool_name: str) -> bool:
        with self._lock:
            return tool_name in self._session_trusted_tools

    def trust(self, tool_name: str) -> None:
        with self._lock:
            self._session_trusted_tools.add(tool_name)

    def clear_trust(self) -> None:
        with self._lock:
            self._session_trusted_tools.clear()

    def request(self, req: ApprovalRequest, timeout: float = AppConstants.APPROVAL_TIMEOUT_SECONDS) -> bool:
        """Dispatch the request to the UI and block until answered. Returns approval."""
        if self._handler is None:
            # No UI attached (tests / headless): fail closed.
            return False
        self._handler(req)
        if not req.wait(timeout):
            return False
        if req.approved and req.remember_for_session:
            self.trust(req.tool_name)
        return req.approved
