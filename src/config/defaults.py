"""
OP(AI)UM — Default Configuration

Pydantic models defining all configurable settings with their defaults.
These are serialized/deserialized to the encrypted config file.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from src.config.constants import AppConstants


class ThemeMode(StrEnum):
    """Available theme modes."""

    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


class TranscriptionModel(StrEnum):
    """Available speech transcription models."""

    GPT_4O_TRANSCRIBE = "gpt-4o-transcribe"
    WHISPER_1 = "whisper-1"


class PasswordType(StrEnum):
    """Password type choices."""

    PIN = "pin"
    PASSWORD = "password"


class FolderDepthMode(StrEnum):
    """AI folder scanning depth."""

    SHALLOW = "shallow"
    RECURSIVE = "recursive"


class ExplorerView(StrEnum):
    """Explorer presentation mode."""

    GRID = "grid"
    LIST = "list"


class SortField(StrEnum):
    """Explorer sort fields."""

    NAME = "name"
    MODIFIED = "modified"
    SIZE = "size"
    TYPE = "type"


class AppearanceConfig(BaseModel):
    """UI appearance settings."""

    theme: ThemeMode = ThemeMode.SYSTEM
    window_width: int = AppConstants.DEFAULT_WINDOW_WIDTH
    window_height: int = AppConstants.DEFAULT_WINDOW_HEIGHT
    window_x: int | None = None
    window_y: int | None = None
    show_hidden_folders: bool = False
    card_width: int = AppConstants.CARD_WIDTH
    card_height: int = AppConstants.CARD_HEIGHT
    card_size_multiplier: float = 1.0
    explorer_view: ExplorerView = ExplorerView.GRID
    sort_field: SortField = SortField.NAME
    sort_descending: bool = False
    folders_first: bool = True
    animations_enabled: bool = True


class RefreshConfig(BaseModel):
    """Auto-refresh settings."""

    auto_refresh_enabled: bool = True
    refresh_interval_seconds: int = AppConstants.DEFAULT_REFRESH_INTERVAL


class AIConfig(BaseModel):
    """AI integration settings."""

    api_key_encrypted: str = ""
    ai_model: str = AppConstants.DEFAULT_AI_MODEL
    # Empty = official OpenAI endpoint. Any OpenAI-compatible server works
    # (Ollama: http://localhost:11434/v1, LM Studio: http://localhost:1234/v1, OpenRouter, Groq...).
    api_base_url: str = ""
    transcription_model: TranscriptionModel = TranscriptionModel.GPT_4O_TRANSCRIBE
    folder_depth_mode: FolderDepthMode = FolderDepthMode.SHALLOW
    max_conversation_history: int = AppConstants.MAX_CONVERSATION_HISTORY
    request_timeout: int = AppConstants.AI_REQUEST_TIMEOUT
    streaming: bool = True
    confirm_destructive: bool = True
    max_tool_rounds: int = AppConstants.AI_MAX_TOOL_ROUNDS
    voice_auto_send: bool = False


class AuthConfig(BaseModel):
    """Authentication settings."""

    password_type: PasswordType = PasswordType.PIN
    password_hash: str = ""
    salt: str = ""
    is_configured: bool = False
    idle_lock_minutes: int = 0  # 0 = never auto-lock
    lock_on_minimize_to_tray: bool = False


class StartupConfig(BaseModel):
    """Startup and system tray settings."""

    start_with_windows: bool = False
    start_minimized: bool = False
    minimize_to_tray: bool = True
    show_notifications: bool = True
    global_hotkey_enabled: bool = True
    global_hotkey: str = AppConstants.DEFAULT_GLOBAL_HOTKEY


class UndoConfig(BaseModel):
    """Undo system settings."""

    purge_days: int = AppConstants.UNDO_PURGE_DAYS
    max_operations: int = 10000
    keep_content_backups: bool = True


class UpdatesConfig(BaseModel):
    """Update checking settings."""

    check_for_updates: bool = True
    last_check_iso: str = ""
    skipped_version: str = ""


class DefaultConfig(BaseModel):
    """
    Master configuration model containing all settings.
    This is what gets serialized to the encrypted config file.
    """

    model_config = ConfigDict(use_enum_values=True)

    appearance: AppearanceConfig = Field(default_factory=AppearanceConfig)
    refresh: RefreshConfig = Field(default_factory=RefreshConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    startup: StartupConfig = Field(default_factory=StartupConfig)
    undo: UndoConfig = Field(default_factory=UndoConfig)
    updates: UpdatesConfig = Field(default_factory=UpdatesConfig)

    # Schema version for migrations
    config_version: int = 2

    # First-run flag
    first_run: bool = True

    # Last known window state
    was_maximized: bool = False
