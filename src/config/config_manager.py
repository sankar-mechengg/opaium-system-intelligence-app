"""
OP(AI)UM — Configuration Manager

Handles loading, saving, and updating the encrypted configuration file.
The config is stored as encrypted JSON in AppData/OPAIUM/config.enc.
Provides a singleton-style access pattern for app-wide config.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from loguru import logger

from src.config.constants import AppConstants
from src.config.crypto import CryptoManager
from src.config.defaults import DefaultConfig


def enum_value(value: Any) -> str:
    """Return the string value of an enum-or-string setting."""
    return str(value.value) if hasattr(value, "value") else str(value)


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

    _instance: ConfigManager | None = None

    def __new__(cls) -> ConfigManager:
        """Singleton pattern — one config manager across the app."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False  # type: ignore[attr-defined]
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._crypto = CryptoManager()
        self._settings: DefaultConfig = DefaultConfig()
        self._config_path: Path = AppConstants.CONFIG_FILE
        self._dirty: bool = False
        self._listeners: list[Any] = []

    @property
    def settings(self) -> DefaultConfig:
        """Get the current configuration settings."""
        return self._settings

    @property
    def crypto(self) -> CryptoManager:
        """Get the crypto manager instance."""
        return self._crypto

    # === Change notification (lightweight, no Qt dependency) ===

    def add_listener(self, callback: Any) -> None:
        """Register a callable invoked after every successful save()."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Any) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self) -> None:
        for cb in list(self._listeners):
            try:
                cb()
            except Exception as e:  # pragma: no cover - defensive
                logger.debug(f"Config listener error: {e}")

    # === Load / Save ===

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
            if self._migrate(data):
                self.save()
            logger.info("Configuration loaded successfully.")
        except ValueError:
            logger.warning("Config decryption failed. Backing up and resetting to defaults.")
            self._backup_corrupt_config()
            self._settings = DefaultConfig()
            self.save()
        except json.JSONDecodeError:
            logger.warning("Config JSON invalid. Backing up and resetting to defaults.")
            self._backup_corrupt_config()
            self._settings = DefaultConfig()
            self.save()
        except Exception as e:
            logger.error(f"Unexpected error loading config: {e}")
            self._settings = DefaultConfig()

    def _migrate(self, raw: dict[str, Any]) -> bool:
        """Apply in-place migrations. Returns True when something changed."""
        changed = False
        version = int(raw.get("config_version", 1) or 1)

        # Old model IDs -> current default
        if self._settings.ai.ai_model in ("gpt-5-2", "gpt-5.2-chat"):
            logger.info(f"Migrating AI model to {AppConstants.DEFAULT_AI_MODEL}")
            self._settings.ai.ai_model = AppConstants.DEFAULT_AI_MODEL
            changed = True

        if version < 2:
            # v1 silently defaulted "Start with Windows" to ON without asking. v2 asks the user.
            if "startup" not in raw or "start_with_windows" not in raw.get("startup", {}):
                self._settings.startup.start_with_windows = False
            self._settings.config_version = 2
            changed = True
            logger.info("Config migrated to schema v2.")

        return changed

    def _backup_corrupt_config(self) -> None:
        try:
            backup = self._config_path.with_suffix(".enc.corrupt")
            shutil.copy2(self._config_path, backup)
            logger.info(f"Corrupt config backed up to {backup}")
        except Exception as e:
            logger.debug(f"Could not back up corrupt config: {e}")

    def save(self) -> None:
        """Save current configuration to encrypted file (atomic write)."""
        AppConstants.ensure_dirs()

        try:
            json_str = self._settings.model_dump_json(indent=2)
            encrypted_data = self._crypto.encrypt(json_str)
            tmp_path = self._config_path.with_suffix(".enc.tmp")
            tmp_path.write_text(encrypted_data, encoding="utf-8")
            os.replace(tmp_path, self._config_path)
            self._dirty = False
            logger.debug("Configuration saved.")
            self._notify()
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

    # === Convenience accessors ===

    @property
    def theme_value(self) -> str:
        return enum_value(self._settings.appearance.theme)

    def get_api_key(self) -> str:
        """Get the decrypted API key (falls back to the OPENAI_API_KEY environment variable)."""
        encrypted = self._settings.ai.api_key_encrypted
        if not encrypted:
            return os.environ.get("OPENAI_API_KEY", "").strip()
        try:
            return self._crypto.decrypt_api_key(encrypted)
        except ValueError:
            logger.warning("Failed to decrypt API key.")
            return os.environ.get("OPENAI_API_KEY", "").strip()

    def set_api_key(self, api_key: str) -> None:
        """Encrypt and store the OpenAI API key (empty string clears it)."""
        self._settings.ai.api_key_encrypted = self._crypto.encrypt_api_key(api_key) if api_key else ""
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

    @staticmethod
    def wipe_all_user_data() -> list[str]:
        """
        Delete every OP(AI)UM file in AppData (config, auth, salt, databases, backups, logs).
        This is the documented recovery path for a forgotten PIN/password.

        Returns:
            List of paths removed.
        """
        removed: list[str] = []
        root = AppConstants.APPDATA_DIR
        if not root.exists():
            return removed
        for entry in list(root.iterdir()):
            try:
                if entry.is_dir():
                    shutil.rmtree(entry, ignore_errors=True)
                else:
                    entry.unlink(missing_ok=True)
                removed.append(str(entry))
            except Exception as e:
                logger.error(f"Could not remove {entry}: {e}")
        logger.warning(f"All user data wiped ({len(removed)} entries).")
        return removed

    @property
    def is_dirty(self) -> bool:
        """Check if there are unsaved changes."""
        return self._dirty

    def auto_save_if_dirty(self) -> None:
        """Save config if there are pending changes."""
        if self._dirty:
            self.save()
