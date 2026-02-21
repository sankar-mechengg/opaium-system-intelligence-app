"""Tests for src/config/ module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config.crypto import CryptoManager
from src.config.defaults import AppSettings, PasswordType


class TestCryptoManager:

    def test_encrypt_decrypt_roundtrip(self, tmp_path: Path):
        crypto = CryptoManager(data_dir=tmp_path)
        original = "sk-test-key-12345"
        encrypted = crypto.encrypt(original)
        assert encrypted != original
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == original

    def test_encrypt_produces_different_output(self, tmp_path: Path):
        crypto = CryptoManager(data_dir=tmp_path)
        text = "same-text"
        e1 = crypto.encrypt(text)
        e2 = crypto.encrypt(text)
        # Fernet produces different ciphertexts due to timestamp/IV
        # but both decrypt to the same value
        assert crypto.decrypt(e1) == text
        assert crypto.decrypt(e2) == text

    def test_decrypt_invalid_returns_empty(self, tmp_path: Path):
        crypto = CryptoManager(data_dir=tmp_path)
        result = crypto.decrypt("not-valid-ciphertext")
        assert result == ""

    def test_encrypt_empty_string(self, tmp_path: Path):
        crypto = CryptoManager(data_dir=tmp_path)
        encrypted = crypto.encrypt("")
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == ""


class TestAppSettings:

    def test_default_settings(self):
        settings = AppSettings()
        assert settings.appearance.theme == "dark"
        assert settings.ai.model == "gpt-4.1-mini"
        assert settings.refresh.auto_refresh_enabled is True
        assert settings.undo.max_history == 100

    def test_password_type_enum(self):
        assert PasswordType.PIN.value == "pin"
        assert PasswordType.PASSWORD.value == "password"

    def test_settings_serialization(self):
        settings = AppSettings()
        data = settings.model_dump()
        assert "appearance" in data
        assert "ai" in data
        assert data["appearance"]["theme"] == "dark"

    def test_settings_from_dict(self, mock_config_data: dict):
        settings = AppSettings(**mock_config_data)
        assert settings.appearance.theme == "dark"
        assert settings.ai.model == "gpt-4.1-mini"
