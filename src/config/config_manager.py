"""
OP(AI)UM — Configuration Manager

Handles loading, saving, and updating the encrypted configuration file.
The config is stored as encrypted JSON in AppData/OPAIUM/config.enc.
Provides a singleton-style access pattern for app-wide config.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from src.config.constants import AppConstants
from src.config.crypto import CryptoManager
from src.config.defaults import DefaultConfig


class ConfigManager:
    """
    Centralized configuration manager for OP(AI)UM.

    Loads encrypted config from disk, provides read/write access,
    and persists changes. Uses a Pydantic model for validation.

    Usage:
        config = ConfigManager()
        config.load()
        theme = config.settings.appearance.theme
        config.settings.appearance.theme = "dark"
        config.save()
    """

    _instance: Optional[ConfigManager] = None

    def __new__(cls) -> ConfigManager:
        """Singleton pattern — one config manager across the app."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:  # type: ignore[has-type]
            return
        self._initialized = True
        self._crypto = CryptoManager()
        self._settings: DefaultConfig = DefaultConfig()
        self._config_path: Path = AppConstants.CONFIG_FILE
        self._dirty: bool = False

    @property
    def settings(self) -> DefaultConfig:
        """Get the current configuration settings."""
        return self._settings

    @property
    def crypto(self) -> CryptoManager:
        """Get the crypto manager instance."""
        return self._crypto

    def load(self) -> None:
        """
        Load configuration from encrypted file.
        If file doesn't exist or is corrupted, use defaults.
        """
        AppConstants.ensure_dirs()

        if not self._config_path.exists():
            logger.info("No config file found. Using defaults (first run).")
            self._settings = DefaultConfig()
            self.save()
            return

        try:
            encrypted_data = self._config_path.read_text(encoding="utf-8")
            json_str = self._crypto.decrypt(encrypted_data)
            data = json.loads(json_str)
            self._settings = DefaultConfig.model_validate(data)
            logger.info("Configuration loaded successfully.")
        except ValueError:
            logger.warning("Config decryption failed. Resetting to defaults.")
            self._settings = DefaultConfig()
            self.save()
        except json.JSONDecodeError:
            logger.warning("Config JSON invalid. Resetting to defaults.")
            self._settings = DefaultConfig()
            self.save()
        except Exception as e:
            logger.error(f"Unexpected error loading config: {e}")
            self._settings = DefaultConfig()

    def save(self) -> None:
        """Save current configuration to encrypted file."""
        AppConstants.ensure_dirs()

        try:
            json_str = self._settings.model_dump_json(indent=2)
            encrypted_data = self._crypto.encrypt(json_str)
            self._config_path.write_text(encrypted_data, encoding="utf-8")
            self._dirty = False
            logger.debug("Configuration saved.")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise

    def update(self, section: str, key: str, value: Any) -> None:
        """
        Update a specific configuration value.

        Args:
            section: Config section name (e.g., 'appearance', 'ai').
            key: Setting key within the section.
            value: New value to set.

        Example:
            config.update('appearance', 'theme', 'dark')
        """
        section_obj = getattr(self._settings, section, None)
        if section_obj is None:
            raise ValueError(f"Unknown config section: {section}")

        if not hasattr(section_obj, key):
            raise ValueError(f"Unknown key '{key}' in section '{section}'")

        setattr(section_obj, key, value)
        self._dirty = True
        logger.debug(f"Config updated: {section}.{key} = {value}")

    def get_api_key(self) -> str:
        """Get the decrypted OpenAI API key."""
        encrypted = self._settings.ai.api_key_encrypted
        if not encrypted:
            return ""
        try:
            return self._crypto.decrypt_api_key(encrypted)
        except ValueError:
            logger.warning("Failed to decrypt API key.")
            return ""

    def set_api_key(self, api_key: str) -> None:
        """Encrypt and store the OpenAI API key."""
        self._settings.ai.api_key_encrypted = self._crypto.encrypt_api_key(api_key)
        self.save()
        logger.info("API key updated and saved.")

    def is_first_run(self) -> bool:
        """Check if this is the first time the app is launched."""
        return self._settings.first_run

    def mark_first_run_complete(self) -> None:
        """Mark first run as complete."""
        self._settings.first_run = False
        self.save()

    def is_auth_configured(self) -> bool:
        """Check if authentication has been set up."""
        return self._settings.auth.is_configured

    def reset(self) -> None:
        """Reset all configuration to defaults."""
        self._settings = DefaultConfig()
        self.save()
        logger.info("Configuration reset to defaults.")

    @property
    def is_dirty(self) -> bool:
        """Check if there are unsaved changes."""
        return self._dirty

    def auto_save_if_dirty(self) -> None:
        """Save config if there are pending changes."""
        if self._dirty:
            self.save()
