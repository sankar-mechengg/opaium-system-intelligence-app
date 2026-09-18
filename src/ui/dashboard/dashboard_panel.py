"""
OP(AI)UM — Dashboard Panel

System-intelligence overview: live CPU / memory / uptime, drive usage,
largest user folders, recent activity, startup programs, Recycle Bin and
undo stats — plus one-click AI actions that jump straight into the chat.
"""

from __future__ import annotations

import contextlib
import os
from datetime import datetime

from loguru import logger
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from src.config.config_manager import ConfigManager
from src.config.constants import AppConstants
from src.core.recent_parser import RecentParser
from src.core.system_stats import DashboardSnapshot, format_size, format_uptime, live_stats, snapshot
from src.ui.dashboard.widgets import DashCard, ListRow, RingGauge, StatTile, UsageBar
from src.ui.widgets.icon_button import IconButton
from src.undo.undo_manager import UndoManager
from src.utils.thread_pool import ThreadPoolManager, Worker
from src.utils.time_utils import TimeUtils

QUICK_ACTIONS: list[tuple[str, str, str, str]] = [
    # (icon, label, question template, folder key)
    ("duplicate", "Find duplicates in Downloads", "Find duplicate files in {downloads}", "downloads"),
    ("search", "Largest files in Downloads", "Find the 20 largest files in {downloads}", "downloads"),
    (
        "broom",
        "Clean empty folders",
        "Find empty folders in {documents} and show me what you would remove",
        "documents",
    ),
    (
        "clock",
        "Stale files on Desktop",
        "Which files on my Desktop ({desktop}) have not been touched in over 6 months?",
        "desktop",
    ),
    ("disk", "Disk usage report", "Give me a disk usage report for all my drives", ""),
    (
        "rocket",
        "Review startup programs",
        "List my Windows startup programs and suggest which ones are safe to disable",
        "",
    ),
]


class DashboardPanel(QWidget):
    """
    Signals:
        open_folder_requested(str): navigate the explorer to this folder.
        ask_ai_requested(str, str): (question, path) for the chat.
        switch_tab_requested(str): switch to a tab id.
    """

    open_folder_requested = Signal(str)
    ask_ai_requested = Signal(str, str)
    switch_tab_requested = Signal(str)

    def __init__(self, config: ConfigManager, undo_manager: UndoManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._undo = undo_manager
        self._recent_parser = RecentParser()
        self._dirty = True
        self._loading = False
        self._snapshot: DashboardSnapshot | None = None
        self._load_token = 0

        self._build_ui()

        self._live_timer = QTimer(self)
        self._live_timer.setInterval(AppConstants.DASHBOARD_LIVE_INTERVAL_MS)
        self._live_timer.timeout.connect(self._update_live)

    # === UI ===

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setObjectName("dashboardScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        # Hero
        hero = QFrame()
        hero.setObjectName("dashHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(22, 18, 22, 18)
        hero_text = QVBoxLayout()
        self._greeting = QLabel(self._greeting_text())
        self._greeting.setObjectName("dashHeroTitle")
        hero_text.addWidget(self._greeting)
        self._hero_sub = QLabel("Your system at a glance. Ask the AI to act on anything you see here.")
        self._hero_sub.setObjectName("dashHeroText")
        self._hero_sub.setWordWrap(True)
        hero_text.addWidget(self._hero_sub)
        hero_layout.addLayout(hero_text, stretch=1)

        self._refresh_btn = IconButton("refresh", "Refresh", role="accent", icon_size=16, object_name="dashActionBtn")
        self._refresh_btn.setFixedHeight(34)
        self._refresh_btn.clicked.connect(lambda: self.refresh(force=True))
        hero_layout.addWidget(self._refresh_btn, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addWidget(hero)

        # Live stats row
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        self._system_card = DashCard("System", icon="cpu", subtitle="live")
        sys_row = QHBoxLayout()
        sys_row.setSpacing(18)
        self._cpu_ring = RingGauge()
        self._mem_ring = RingGauge()
        sys_row.addWidget(self._cpu_ring)
        sys_row.addWidget(self._mem_ring)
        tiles = QVBoxLayout()
        tiles.setSpacing(6)
        self._uptime_tile = StatTile("Uptime")
        self._proc_tile = StatTile("Processes")
        self._mem_tile = StatTile("Memory")
        tiles.addWidget(self._uptime_tile)
        tiles.addWidget(self._mem_tile)
        tiles.addWidget(self._proc_tile)
        sys_row.addLayout(tiles)
        sys_row.addStretch()
        self._system_card.body.addLayout(sys_row)
        grid.addWidget(self._system_card, 0, 0)

        self._drives_card = DashCard("Drives", icon="disk")
        grid.addWidget(self._drives_card, 0, 1)

        self._folders_card = DashCard("Largest user folders", icon="folder", subtitle="scanning…")
        grid.addWidget(self._folders_card, 1, 0)

        self._activity_card = DashCard("Recent activity", icon="clock")
        grid.addWidget(self._activity_card, 1, 1)

        self._startup_card = DashCard("Startup programs", icon="rocket")
        grid.addWidget(self._startup_card, 2, 0)

        self._housekeeping_card = DashCard("Housekeeping", icon="broom")
        grid.addWidget(self._housekeeping_card, 2, 1)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        # Quick AI actions
        self._actions_card = DashCard("Ask the AI", icon="sparkle", subtitle="one click")
        actions_grid = QGridLayout()
        actions_grid.setHorizontalSpacing(10)
        actions_grid.setVerticalSpacing(8)
        for i, (icon, label, template, key) in enumerate(QUICK_ACTIONS):
            btn = IconButton(icon, label, role="accent", icon_size=16, object_name="dashActionBtn")
            btn.setFixedHeight(36)
            btn.clicked.connect(lambda checked=False, t=template, k=key: self._quick_action(t, k))
            actions_grid.addWidget(btn, i // 3, i % 3)
        self._actions_card.body.addLayout(actions_grid)
        layout.addWidget(self._actions_card)

        layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

    @staticmethod
    def _greeting_text() -> str:
        hour = datetime.now().hour
        word = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
        user = os.environ.get("USERNAME", "").strip()
        return f"{word}{', ' + user if user else ''}."

    # === Lifecycle ===

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().showEvent(event)
        self._live_timer.start()
        self._update_live()
        self.refresh()

    def hideEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().hideEvent(event)
        self._live_timer.stop()

    def mark_dirty(self) -> None:
        self._dirty = True

    def refresh(self, force: bool = False) -> None:
        """Reload the heavier snapshot in the background (only when needed)."""
        if self._loading or (not force and not self._dirty and self._snapshot is not None):
            return
        self._loading = True
        self._load_token += 1
        token = self._load_token
        self._folders_card.set_subtitle("scanning…")
        self._greeting.setText(self._greeting_text())

        worker = Worker(self._load_snapshot)
        worker.signals.result.connect(lambda data, t=token: self._on_snapshot(t, data))
        worker.signals.error.connect(lambda err: logger.error(f"Dashboard load error: {err}"))
        worker.signals.finished.connect(self._on_load_finished)
        ThreadPoolManager.run(worker)

    def _load_snapshot(self) -> dict:  # type: ignore[type-arg]
        snap = snapshot(include_folder_sizes=True)
        recent = self._recent_parser.scan(include_files=True, include_folders=True)[:8]
        stats = {}
        with contextlib.suppress(Exception):
            stats = self._undo.journal.get_stats()
        return {"snapshot": snap, "recent": recent, "undo": stats}

    def _on_load_finished(self) -> None:
        self._loading = False

    # === Rendering ===

    def _update_live(self) -> None:
        stats = live_stats()
        if not stats.available:
            self._system_card.set_subtitle("psutil not installed")
            self._cpu_ring.set_value(0, "—", "CPU")
            self._mem_ring.set_value(0, "—", "RAM")
            return
        self._system_card.set_subtitle(datetime.now().strftime("%H:%M:%S"))
        self._cpu_ring.set_value(stats.cpu_percent, sub=f"CPU · {stats.cpu_count} threads")
        self._mem_ring.set_value(stats.memory_percent, sub="RAM")
        self._uptime_tile.set_value(format_uptime(stats.uptime))
        self._proc_tile.set_value(str(stats.process_count))
        self._mem_tile.set_value(f"{format_size(stats.memory_used)} / {format_size(stats.memory_total)}")

    def _on_snapshot(self, token: int, data: object) -> None:
        if token != self._load_token or not isinstance(data, dict):
            return
        snap: DashboardSnapshot = data["snapshot"]
        self._snapshot = snap
        self._dirty = False

        # Drives
        self._drives_card.clear_body()
        if not snap.drives:
            self._drives_card.body.addWidget(self._muted("No drives detected."))
        for d in snap.drives:
            bar = UsageBar(
                f"{d.letter}:  {d.label}",
                f"{d.display_free} free of {d.display_total}  ·  {d.filesystem}",
                d.percent_used,
            )
            bar.clicked.connect(lambda letter=d.letter: self.open_folder_requested.emit(f"{letter}:\\"))
            self._drives_card.body.addWidget(bar)
        self._drives_card.set_subtitle(f"{len(snap.drives)} drive{'s' if len(snap.drives) != 1 else ''}")

        # Folder sizes
        self._folders_card.clear_body()
        total = sum(f.size_bytes for f in snap.folder_sizes) or 1
        for f in snap.folder_sizes[:6]:
            bar = UsageBar(
                f.name, f"{format_size(f.size_bytes)}  ·  {f.file_count:,} files", f.size_bytes / total * 100
            )
            bar.clicked.connect(lambda p=f.path: self.open_folder_requested.emit(p))
            self._folders_card.body.addWidget(bar)
        if not snap.folder_sizes:
            self._folders_card.body.addWidget(self._muted("No user folders found."))
        self._folders_card.set_subtitle(f"{format_size(sum(f.size_bytes for f in snap.folder_sizes))} total")

        # Recent activity
        self._activity_card.clear_body()
        recent = data.get("recent") or []
        for item in recent:
            row = ListRow(
                item.name,
                TimeUtils.format_relative(item.accessed_at),
                item.path,
                icon="folder" if item.is_folder else "file",
            )
            row.clicked.connect(self._open_recent)
            self._activity_card.body.addWidget(row)
        if not recent:
            self._activity_card.body.addWidget(self._muted("Nothing opened recently."))
        self._activity_card.set_subtitle(f"{len(recent)} shown")

        # Startup programs
        self._startup_card.clear_body()
        entries = snap.startup_entries
        for e in entries[:6]:
            src = {"registry_user": "User", "registry_machine": "Machine", "startup_folder": "Startup folder"}.get(
                e.source, e.source
            )
            row = ListRow(e.name, src, e.command, icon="rocket")
            row.clicked.connect(
                lambda cmd: self.ask_ai_requested.emit(
                    f"What is this startup entry and is it safe to disable? {cmd}", ""
                )
            )
            self._startup_card.body.addWidget(row)
        if len(entries) > 6:
            more = IconButton(
                "sparkle",
                f"Review all {len(entries)} with AI",
                role="accent",
                icon_size=14,
                object_name="dashActionBtn",
            )
            more.setFixedHeight(30)
            more.clicked.connect(
                lambda: self.ask_ai_requested.emit("List all my Windows startup programs and flag anything unusual", "")
            )
            self._startup_card.body.addWidget(more)
        if not entries:
            self._startup_card.body.addWidget(self._muted("No startup entries found."))
        self._startup_card.set_subtitle(f"{len(entries)} entr{'ies' if len(entries) != 1 else 'y'}")

        # Housekeeping
        self._housekeeping_card.clear_body()
        undo = data.get("undo") or {}
        tiles = QHBoxLayout()
        tiles.setSpacing(24)
        tiles.addWidget(StatTile("Recycle Bin items", f"{snap.recycle_count:,}"))
        tiles.addWidget(StatTile("Recycle Bin size", format_size(snap.recycle_size)))
        tiles.addWidget(StatTile("Undoable operations", str(undo.get("undoable", 0))))
        tiles.addWidget(StatTile("Operations logged", str(undo.get("total", 0))))
        tiles.addStretch()
        self._housekeeping_card.body.addLayout(tiles)
        actions = QHBoxLayout()
        bin_btn = IconButton(
            "recycle", "Ask AI about the Recycle Bin", role="accent", icon_size=14, object_name="dashActionBtn"
        )
        bin_btn.setFixedHeight(30)
        bin_btn.clicked.connect(
            lambda: self.ask_ai_requested.emit(
                "What's in my Recycle Bin and how much space would emptying it free?", ""
            )
        )
        actions.addWidget(bin_btn)
        hist_btn = IconButton("history", "Open History", role="accent", icon_size=14, object_name="dashActionBtn")
        hist_btn.setFixedHeight(30)
        hist_btn.clicked.connect(lambda: self.switch_tab_requested.emit("history"))
        actions.addWidget(hist_btn)
        actions.addStretch()
        self._housekeeping_card.body.addLayout(actions)

    @staticmethod
    def _muted(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("dashListItemMeta")
        return label

    # === Actions ===

    def _open_recent(self, path: str) -> None:
        if os.path.isdir(path):
            self.open_folder_requested.emit(path)
        else:
            try:
                os.startfile(path)  # type: ignore[attr-defined]
            except Exception as e:
                logger.error(f"Open failed: {e}")

    def _quick_action(self, template: str, key: str) -> None:
        profile = os.environ.get("USERPROFILE", "")
        folders = {
            "downloads": os.path.join(profile, "Downloads"),
            "documents": os.path.join(profile, "Documents"),
            "desktop": os.path.join(profile, "Desktop"),
        }
        question = template.format(**folders)
        self.ask_ai_requested.emit(question, folders.get(key, ""))
