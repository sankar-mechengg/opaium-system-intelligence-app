"""
OP(AI)UM — Default Configuration

Pydantic models defining all configurable settings with their defaults.
These are serialized/deserialized to the encrypted config file.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.config.constants import AppConstants


class ThemeMode(str, Enum):
    """Available theme modes."""
    LIGHT = "light"
    DARK = "dark"


class TranscriptionModel(str, Enum):
    """Available speech transcription models."""
    GPT_4O_TRANSCRIBE = "gpt-4o-transcribe"
    WHISPER_1 = "whisper-1"


class PasswordType(str, Enum):
    """Password type choices."""
    PIN = "pin"
    PASSWORD = "password"


class FolderDepthMode(str, Enum):
    """AI folder scanning depth."""
    SHALLOW = "shallow"
    RECURSIVE = "recursive"


class AppearanceConfig(BaseModel):
    """UI appearance settings."""
    theme: ThemeMode = ThemeMode.LIGHT
    window_width: int = AppConstants.DEFAULT_WINDOW_WIDTH
    window_height: int = AppConstants.DEFAULT_WINDOW_HEIGHT
    window_x: Optional[int] = None
    window_y: Optional[int] = None
    show_hidden_folders: bool = False
    card_width: int = AppConstants.CARD_WIDTH
    card_height: int = AppConstants.CARD_HEIGHT
    card_size_multiplier: float = 1.0


class RefreshConfig(BaseModel):
    """Auto-refresh settings."""
    auto_refresh_enabled: bool = True
    refresh_interval_seconds: int = AppConstants.DEFAULT_REFRESH_INTERVAL


class AIConfig(BaseModel):
    """AI integration settings."""
    api_key_encrypted: str = ""
    ai_model: str = AppConstants.DEFAULT_AI_MODEL
    transcription_model: TranscriptionModel = TranscriptionModel.GPT_4O_TRANSCRIBE
    folder_depth_mode: FolderDepthMode = FolderDepthMode.SHALLOW
    max_conversation_history: int = AppConstants.MAX_CONVERSATION_HISTORY
    request_timeout: int = AppConstants.AI_REQUEST_TIMEOUT


class AuthConfig(BaseModel):
    """Authentication settings."""
    password_type: PasswordType = PasswordType.PIN
    password_hash: str = ""
    salt: str = ""
    is_configured: bool = False


class StartupConfig(BaseModel):
    """Startup and system tray settings."""
    start_with_windows: bool = True
    minimize_to_tray: bool = True
    show_notifications: bool = True


class UndoConfig(BaseModel):
    """Undo system settings."""
    purge_days: int = AppConstants.UNDO_PURGE_DAYS
    max_operations: int = 10000


class DefaultConfig(BaseModel):
    """
    Master configuration model containing all settings.
    This is what gets serialized to the encrypted config file.
    """
    appearance: AppearanceConfig = Field(default_factory=AppearanceConfig)
    refresh: RefreshConfig = Field(default_factory=RefreshConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    startup: StartupConfig = Field(default_factory=StartupConfig)
    undo: UndoConfig = Field(default_factory=UndoConfig)

    # First-run flag
    first_run: bool = True

    # Last known window state
    was_maximized: bool = False

    class Config:
        use_enum_values = True
