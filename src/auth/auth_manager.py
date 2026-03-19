"""
OP(AI)UM — Authentication Manager

Handles password/PIN creation, hashing (Argon2), and verification.
Passwords are never stored in plaintext — only salted Argon2 hashes.
Auth state is persisted in the encrypted config file.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from loguru import logger

from src.config.config_manager import ConfigManager
from src.config.defaults import PasswordType


class AuthManager:
    """
    Manages authentication for OP(AI)UM.

    Supports both numeric PIN and alphanumeric password modes.
    Uses Argon2id for secure password hashing.
    """

    def __init__(self, config: ConfigManager) -> None:
        self._config = config
        self._hasher = PasswordHasher(
            time_cost=3,
            memory_cost=65536,  # 64 MB
            parallelism=4,
            hash_len=32,
            salt_len=16,
        )
        self._session_authenticated = False

    @property
    def is_configured(self) -> bool:
        """Check if a password/PIN has been set up."""
        return self._config.settings.auth.is_configured

    @property
    def is_authenticated(self) -> bool:
        """Check if the current session is authenticated."""
        return self._session_authenticated

    @property
    def password_type(self) -> PasswordType:
        """Get the configured password type (PIN or password)."""
        return PasswordType(self._config.settings.auth.password_type)

    def setup_password(self, password: str, password_type: PasswordType) -> bool:
        """
        Set up a new password or PIN.

        Args:
            password: The plaintext password or PIN.
            password_type: Whether this is a PIN or password.

        Returns:
            True if setup was successful.

        Raises:
            ValueError: If password doesn't meet requirements.
        """
        # Validate based on type
        self._validate_password(password, password_type)

        try:
            # Hash the password with Argon2
            password_hash = self._hasher.hash(password)

            # Store in config
            self._config.settings.auth.password_hash = password_hash
            self._config.settings.auth.password_type = password_type
            self._config.settings.auth.is_configured = True
            self._config.save()

            self._session_authenticated = True
            logger.info(f"Password setup complete. Type: {password_type.value}")
            return True

        except Exception as e:
            logger.error(f"Failed to setup password: {e}")
            return False

    def verify(self, password: str) -> bool:
        """
        Verify a password/PIN against the stored hash.

        Args:
            password: The plaintext password/PIN to verify.

        Returns:
            True if the password matches.
        """
        if not self.is_configured:
            logger.warning("Attempted verification but no password is configured.")
            return False

        stored_hash = self._config.settings.auth.password_hash
        if not stored_hash:
            logger.error("Password hash is empty despite being configured.")
            return False

        try:
            self._hasher.verify(stored_hash, password)

            # Check if rehash is needed (parameters changed)
            if self._hasher.check_needs_rehash(stored_hash):
                logger.info("Rehashing password with updated parameters.")
                new_hash = self._hasher.hash(password)
                self._config.settings.auth.password_hash = new_hash
                self._config.save()

            self._session_authenticated = True
            logger.info("Authentication successful.")
            return True

        except VerifyMismatchError:
            logger.warning("Authentication failed: incorrect password.")
            return False
        except VerificationError as e:
            logger.error(f"Authentication error: {e}")
            return False

    def change_password(
        self,
        current_password: str,
        new_password: str,
        new_type: PasswordType | None = None,
    ) -> bool:
        """
        Change the current password/PIN.

        Args:
            current_password: The current password for verification.
            new_password: The new password to set.
            new_type: Optionally change password type (PIN <-> password).

        Returns:
            True if password was changed successfully.
        """
        # Verify current password first
        if not self.verify(current_password):
            logger.warning("Password change failed: current password incorrect.")
            return False

        # Use current type if not changing
        password_type = new_type or self.password_type

        return self.setup_password(new_password, password_type)

    def reset_auth(self) -> None:
        """
        Reset authentication completely.
        WARNING: This removes all auth protection.
        """
        self._config.settings.auth.password_hash = ""
        self._config.settings.auth.salt = ""
        self._config.settings.auth.is_configured = False
        self._config.save()
        self._session_authenticated = False
        logger.info("Authentication has been reset.")

    def lock_session(self) -> None:
        """Lock the current session (require re-auth)."""
        self._session_authenticated = False
        logger.info("Session locked.")

    def _validate_password(self, password: str, password_type: PasswordType) -> None:
        """
        Validate password meets requirements.

        Raises:
            ValueError: If password doesn't meet requirements.
        """
        from src.config.constants import AppConstants

        if password_type == PasswordType.PIN:
            if not password.isdigit():
                raise ValueError("PIN must contain only digits.")
            if len(password) < AppConstants.MIN_PIN_LENGTH:
                raise ValueError(f"PIN must be at least {AppConstants.MIN_PIN_LENGTH} digits.")
            if len(password) > AppConstants.MAX_PIN_LENGTH:
                raise ValueError(f"PIN must be at most {AppConstants.MAX_PIN_LENGTH} digits.")
        else:
            if len(password) < AppConstants.MIN_PASSWORD_LENGTH:
                raise ValueError(f"Password must be at least {AppConstants.MIN_PASSWORD_LENGTH} characters.")
            if len(password) > AppConstants.MAX_PASSWORD_LENGTH:
                raise ValueError(f"Password must be at most {AppConstants.MAX_PASSWORD_LENGTH} characters.")
