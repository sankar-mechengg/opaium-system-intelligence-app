"""
OP(AI)UM — Application-wide Constants

Centralized constants for paths, intervals, version information,
and other immutable values used throughout the application.
"""

import os
import sys
from pathlib import Path

from src.version import __version__


class AppConstants:
    """Immutable application constants."""

    # === App Identity ===
    APP_NAME = "OP(AI)UM"
    APP_FULL_NAME = "Omniscient Processor for Adaptive Intelligence & Unified Management"
    APP_VERSION = __version__
    APP_AUTHOR = "Sankar Balasubramanian"
    APP_ORG = "Sankar Balasubramanian"
    GITHUB_REPO = "sankar-mechengg/opaium-system-intelligence-app"
    GITHUB_URL = f"https://github.com/{GITHUB_REPO}"
    RELEASES_URL = f"{GITHUB_URL}/releases"
    RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    ISSUES_URL = f"{GITHUB_URL}/issues"

    # === Paths ===
    # Base directory of the application (handles both dev and frozen .exe)
    if getattr(sys, "frozen", False):
        APP_DIR = Path(sys.executable).parent
        # PyInstaller >= 6 unpacks bundled data into _internal (exposed as sys._MEIPASS)
        RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
    else:
        APP_DIR = Path(__file__).resolve().parent.parent.parent
        RESOURCE_DIR = APP_DIR

    # User data directory in AppData
    APPDATA_DIR = Path(os.environ.get("APPDATA", "")) / "OPAIUM"
    CONFIG_FILE = APPDATA_DIR / "config.enc"
    AUTH_FILE = APPDATA_DIR / "auth.enc"
    TRACKING_DB_FILE = APPDATA_DIR / "tracking.db"
    UNDO_DB_FILE = APPDATA_DIR / "undo_journal.db"
    CONVERSATIONS_DB_FILE = APPDATA_DIR / "conversations.db"
    LOG_FILE = APPDATA_DIR / "opaium.log"
    LOG_DIR = APPDATA_DIR / "logs"
    BACKUP_DIR = APPDATA_DIR / "backups"
    CACHE_DIR = APPDATA_DIR / "cache"

    # Assets
    ASSETS_DIR = RESOURCE_DIR / "assets"
    ICONS_DIR = ASSETS_DIR / "icons"
    SVG_ICONS_DIR = ICONS_DIR / "svg"
    THEMES_DIR = ASSETS_DIR / "themes"
    SOUNDS_DIR = ASSETS_DIR / "sounds"

    # Logo and icons
    LOGO_PATH = ICONS_DIR / "opaium_logo_nobg.png"
    LOGO_ICO_PATH = ICONS_DIR / "opaium_logo_nobg.ico"
    TRAY_ICON_PATH = ICONS_DIR / "tray_icon.png"

    # Windows Recent folder
    WINDOWS_RECENT_DIR = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Recent"

    # === Time Intervals (seconds) ===
    DEFAULT_REFRESH_INTERVAL = 300  # 5 minutes
    MIN_REFRESH_INTERVAL = 30
    MAX_REFRESH_INTERVAL = 3600  # 1 hour
    UPDATE_CHECK_INTERVAL_HOURS = 24
    DASHBOARD_LIVE_INTERVAL_MS = 2000

    # === Time Grouping Thresholds (days) ===
    GROUP_RECENT_DAYS = 2
    GROUP_WEEK_DAYS = 7
    GROUP_MONTH_DAYS = 30

    # === Undo System ===
    UNDO_PURGE_DAYS = 2
    UNDO_PURGE_CHECK_INTERVAL = 3600  # Check every hour
    MAX_BACKUP_FILE_BYTES = 50 * 1024 * 1024  # Only back up files <= 50 MB before overwrite

    # === AI Configuration ===
    DEFAULT_AI_MODEL = "gpt-5.2-2025-12-11"
    AVAILABLE_AI_MODELS = [
        "gpt-5.2-2025-12-11",
        "gpt-5.2",
        "gpt-5.1",
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
        "gpt-4.1",
        "gpt-4.1-mini",
        "gpt-4.1-nano",
        "gpt-4o",
        "gpt-4o-mini",
        "o4-mini",
    ]
    DEFAULT_TRANSCRIPTION_MODEL = "gpt-4o-transcribe"
    AVAILABLE_TRANSCRIPTION_MODELS = ["gpt-4o-transcribe", "whisper-1"]
    MAX_CONVERSATION_HISTORY = 60  # Messages per session
    AI_REQUEST_TIMEOUT = 90  # seconds
    AI_MAX_TOOL_ROUNDS = 8
    APPROVAL_TIMEOUT_SECONDS = 600  # How long a tool call waits for the user to approve

    # === UI Constants ===
    MIN_WINDOW_WIDTH = 1024
    MIN_WINDOW_HEIGHT = 680
    DEFAULT_WINDOW_WIDTH = 1400
    DEFAULT_WINDOW_HEIGHT = 900
    CARD_WIDTH = 160
    CARD_HEIGHT = 140
    TREE_PANEL_WIDTH = 240
    PREVIEW_PANEL_WIDTH = 280
    DEFAULT_GLOBAL_HOTKEY = "Ctrl+Shift+Space"

    # === File Scanning ===
    MAX_SCAN_DEPTH = 10  # Maximum recursion depth for folder scanning
    MAX_FILES_DISPLAY = 5000  # Max files to display at once
    HIDDEN_PREFIXES = (".", "$")
    SYSTEM_FOLDERS = {
        "System Volume Information",
        "$Recycle.Bin",
        "Windows",
        "ProgramData",
        "Recovery",
        "Config.Msi",
    }

    # === Auth ===
    MIN_PIN_LENGTH = 4
    MAX_PIN_LENGTH = 8
    MIN_PASSWORD_LENGTH = 6
    MAX_PASSWORD_LENGTH = 128
    AUTH_SALT_LENGTH = 16
    AUTH_FREE_ATTEMPTS = 5  # Failed attempts before the progressive lockout kicks in
    AUTH_LOCKOUT_BASE_SECONDS = 30

    # === Encryption ===
    CONFIG_ENCRYPTION_KEY_ENV = "OPAIUM_CONFIG_KEY"

    # === Startup Registry ===
    STARTUP_REGISTRY_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
    STARTUP_REGISTRY_VALUE = "OPAIUM"

    @classmethod
    def ensure_dirs(cls) -> None:
        """Create all required application directories if they don't exist."""
        for d in (cls.APPDATA_DIR, cls.LOG_DIR, cls.BACKUP_DIR, cls.CACHE_DIR):
            d.mkdir(parents=True, exist_ok=True)
