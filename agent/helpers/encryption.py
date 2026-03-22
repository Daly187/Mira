"""
AES-256 encryption for data at rest.
All personal data stored on disk goes through this layer.
"""

import base64
import os
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionManager:
    """Handles AES-256 encryption/decryption for stored data."""

    def __init__(self, key_path: Path = None):
        self.key_path = key_path
        self._fernet = None

    def initialise(self):
        """Load or generate encryption key."""
        if self.key_path and self.key_path.exists():
            key = self.key_path.read_bytes()
        else:
            key = Fernet.generate_key()
            if self.key_path:
                self.key_path.parent.mkdir(parents=True, exist_ok=True)
                self.key_path.write_bytes(key)
        self._fernet = Fernet(key)

    def encrypt(self, data: str) -> bytes:
        """Encrypt a string, return encrypted bytes."""
        if not self._fernet:
            self.initialise()
        return self._fernet.encrypt(data.encode("utf-8"))

    def decrypt(self, encrypted_data: bytes) -> str:
        """Decrypt bytes back to string."""
        if not self._fernet:
            self.initialise()
        return self._fernet.decrypt(encrypted_data).decode("utf-8")

    def encrypt_file(self, file_path: Path):
        """Encrypt a file in place."""
        data = file_path.read_text(encoding="utf-8")
        encrypted = self.encrypt(data)
        file_path.write_bytes(encrypted)

    def decrypt_file(self, file_path: Path) -> str:
        """Decrypt a file and return contents."""
        encrypted = file_path.read_bytes()
        return self.decrypt(encrypted)

    @staticmethod
    def derive_key_from_password(password: str, salt: bytes = None) -> tuple[bytes, bytes]:
        """Derive an encryption key from a password (for backup encryption)."""
        if salt is None:
            salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt
