"""
OP(AI)UM — Application-wide Constants

Centralized constants for paths, intervals, version information,
and other immutable values used throughout the application.
"""

import os
import sys
from pathlib import Path


class AppConstants:
    """Immutable application constants."""

    # === App Identity ===
    APP_NAME = "OP(AI)UM"
    APP_FULL_NAME = "Omniscient Processor for Adaptive Intelligence & Unified Management"
    APP_VERSION = "1.0.0"
    APP_AUTHOR = "Sankar Balasubramanian"
    APP_ORG = "Sankar Balasubramanian"

    # === Paths ===
    # Base directory of the application (handles both dev and frozen .exe)
    if getattr(sys, "frozen", False):
        APP_DIR = Path(sys.executable).parent
    else:
        APP_DIR = Path(__file__).resolve().parent.parent.parent

    # User data directory in AppData
    APPDATA_DIR = Path(os.environ.get("APPDATA", "")) / "OPAIUM"
    CONFIG_FILE = APPDATA_DIR / "config.enc"
    AUTH_FILE = APPDATA_DIR / "auth.enc"
    TRACKING_DB_FILE = APPDATA_DIR / "tracking.db"
    UNDO_DB_FILE = APPDATA_DIR / "undo_journal.db"
    LOG_FILE = APPDATA_DIR / "opaium.log"
    LOG_DIR = APPDATA_DIR / "logs"

    # Assets
    ASSETS_DIR = APP_DIR / "assets"
    ICONS_DIR = ASSETS_DIR / "icons"
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

    # === Time Grouping Thresholds (days) ===
    GROUP_RECENT_DAYS = 2
    GROUP_WEEK_DAYS = 7
    GROUP_MONTH_DAYS = 30

    # === Undo System ===
    UNDO_PURGE_DAYS = 2
    UNDO_PURGE_CHECK_INTERVAL = 3600  # Check every hour

    # === AI Configuration ===
    DEFAULT_AI_MODEL = "gpt-5.2-2025-12-11"
    DEFAULT_TRANSCRIPTION_MODEL = "gpt-4o-transcribe"
    AVAILABLE_TRANSCRIPTION_MODELS = ["gpt-4o-transcribe", "whisper-1"]
    MAX_CONVERSATION_HISTORY = 50  # Messages per session
    AI_REQUEST_TIMEOUT = 60  # seconds

    # === UI Constants ===
    MIN_WINDOW_WIDTH = 1024
    MIN_WINDOW_HEIGHT = 700
    DEFAULT_WINDOW_WIDTH = 1400
    DEFAULT_WINDOW_HEIGHT = 900
    CHAT_BUBBLE_SIZE = 56
    CHAT_PANEL_WIDTH = 420
    CHAT_PANEL_HEIGHT = 550
    CARD_WIDTH = 160
    CARD_HEIGHT = 140
    TREE_PANEL_WIDTH = 260
    PREVIEW_PANEL_WIDTH = 300

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

    # === Encryption ===
    CONFIG_ENCRYPTION_KEY_ENV = "OPAIUM_CONFIG_KEY"

    # === Startup Registry ===
    STARTUP_REGISTRY_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
    STARTUP_REGISTRY_VALUE = "OPAIUM"

    @classmethod
    def ensure_dirs(cls) -> None:
        """Create all required application directories if they don't exist."""
        cls.APPDATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
