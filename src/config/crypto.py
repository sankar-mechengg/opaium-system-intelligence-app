"""
OP(AI)UM — Encryption Utilities

Handles encryption/decryption of the config file and sensitive data
like the OpenAI API key. Uses Fernet symmetric encryption with a
machine-specific key derived from Windows DPAPI + a local salt.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

from src.config.constants import AppConstants


class CryptoManager:
    """
    Manages encryption and decryption of sensitive application data.

    The encryption key is derived from a combination of:
    1. A randomly generated salt stored alongside the config
    2. The machine's hostname + username (machine-binding)

    This means the config file is only decryptable on the same
    machine by the same user.
    """

    SALT_FILE = AppConstants.APPDATA_DIR / ".salt"

    def __init__(self) -> None:
        self._fernet: Fernet | None = None

    def _get_machine_identifier(self) -> bytes:
        """Generate a machine-specific identifier."""
        machine_id = f"{os.environ.get('COMPUTERNAME', 'unknown')}"
        machine_id += f":{os.environ.get('USERNAME', 'unknown')}"
        machine_id += f":{os.environ.get('USERDOMAIN', 'unknown')}"
        return machine_id.encode("utf-8")

    def _get_or_create_salt(self) -> bytes:
        """Get existing salt or create a new one."""
        if self.SALT_FILE.exists():
            return self.SALT_FILE.read_bytes()
        else:
            salt = secrets.token_bytes(32)
            AppConstants.ensure_dirs()
            self.SALT_FILE.write_bytes(salt)
            # Hide the salt file
            try:
                import ctypes

                ctypes.windll.kernel32.SetFileAttributesW(  # type: ignore[union-attr]
                    str(self.SALT_FILE),
                    0x02,  # FILE_ATTRIBUTE_HIDDEN
                )
            except Exception:
                pass
            return salt

    def _derive_key(self) -> bytes:
        """Derive a Fernet-compatible encryption key."""
        salt = self._get_or_create_salt()
        machine_id = self._get_machine_identifier()

        # PBKDF2 key derivation
        raw_key = hashlib.pbkdf2_hmac(
            "sha256",
            machine_id,
            salt,
            iterations=100_000,
            dklen=32,
        )
        return base64.urlsafe_b64encode(raw_key)

    @property
    def fernet(self) -> Fernet:
        """Get or create the Fernet encryption instance."""
        if self._fernet is None:
            key = self._derive_key()
            self._fernet = Fernet(key)
        return self._fernet

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.

        Args:
            plaintext: The string to encrypt.

        Returns:
            Base64-encoded encrypted string.
        """
        encrypted = self.fernet.encrypt(plaintext.encode("utf-8"))
        return base64.urlsafe_b64encode(encrypted).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            ciphertext: Base64-encoded encrypted string.

        Returns:
            Decrypted plaintext string.

        Raises:
            ValueError: If decryption fails (wrong key, corrupted data).
        """
        try:
            raw = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
            decrypted = self.fernet.decrypt(raw)
            return decrypted.decode("utf-8")
        except (InvalidToken, Exception) as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Failed to decrypt data. Config may be corrupted.") from e

    def encrypt_api_key(self, api_key: str) -> str:
        """Encrypt an API key for storage."""
        return self.encrypt(api_key)

    def decrypt_api_key(self, encrypted_key: str) -> str:
        """Decrypt a stored API key."""
        if not encrypted_key:
            return ""
        return self.decrypt(encrypted_key)

    @staticmethod
    def generate_salt() -> str:
        """Generate a random salt for password hashing."""
        return secrets.token_hex(AppConstants.AUTH_SALT_LENGTH)
