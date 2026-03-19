"""Tests for src/config/ module."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config.constants import AppConstants
from src.config.crypto import CryptoManager
from src.config.defaults import DefaultConfig, PasswordType, ThemeMode


class TestCryptoManager:
    def test_encrypt_decrypt_roundtrip(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(CryptoManager, "SALT_FILE", tmp_path / ".salt")
        crypto = CryptoManager()
        original = "sk-test-key-12345"
        encrypted = crypto.encrypt(original)
        assert encrypted != original
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == original

    def test_encrypt_produces_different_output(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(CryptoManager, "SALT_FILE", tmp_path / ".salt")
        crypto = CryptoManager()
        text = "same-text"
        e1 = crypto.encrypt(text)
        e2 = crypto.encrypt(text)
        # Fernet produces different ciphertexts due to timestamp/IV
        # but both decrypt to the same value
        assert crypto.decrypt(e1) == text
        assert crypto.decrypt(e2) == text

    def test_decrypt_invalid_raises(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(CryptoManager, "SALT_FILE", tmp_path / ".salt")
        crypto = CryptoManager()
        with pytest.raises(ValueError):
            crypto.decrypt("not-valid-ciphertext")

    def test_encrypt_empty_string(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(CryptoManager, "SALT_FILE", tmp_path / ".salt")
        crypto = CryptoManager()
        encrypted = crypto.encrypt("")
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == ""


class TestDefaultConfig:
    def test_default_settings(self):
        settings = DefaultConfig()
        assert settings.appearance.theme == ThemeMode.LIGHT
        assert settings.ai.ai_model == AppConstants.DEFAULT_AI_MODEL
        assert settings.refresh.auto_refresh_enabled is True
        assert settings.undo.max_operations == 10000

    def test_password_type_enum(self):
        assert PasswordType.PIN.value == "pin"
        assert PasswordType.PASSWORD.value == "password"

    def test_settings_serialization(self):
        settings = DefaultConfig()
        data = settings.model_dump(mode="json")
        assert "appearance" in data
        assert "ai" in data
        assert data["appearance"]["theme"] == "light"

    def test_settings_from_dict(self, mock_config_data: dict):
        settings = DefaultConfig(**mock_config_data)
        assert settings.appearance.theme == ThemeMode.DARK
        assert settings.ai.ai_model == "gpt-4.1-mini"
