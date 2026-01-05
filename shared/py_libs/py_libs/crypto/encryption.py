"""
Encryption utilities using AES-256-GCM.

Provides authenticated encryption for:
- Sensitive data at rest
- API payloads
- Configuration secrets
- Token encryption

AES-256-GCM provides both confidentiality and authenticity.
"""

from __future__ import annotations

import base64
import json
import os
import struct
from dataclasses import dataclass
from typing import Any, Optional, Union

# Import cryptography library
try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    from cryptography.hazmat.primitives import hashes

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False


# Constants
NONCE_SIZE = 12  # 96 bits for GCM
KEY_SIZE = 32  # 256 bits for AES-256
TAG_SIZE = 16  # 128 bits authentication tag
SALT_SIZE = 16  # 128 bits for key derivation


@dataclass(slots=True, frozen=True)
class EncryptionResult:
    """Result of an encryption operation."""

    ciphertext: bytes
    nonce: bytes
    tag: bytes  # Authentication tag (included in ciphertext for GCM)

    def to_bytes(self) -> bytes:
        """Combine all components into a single bytes object."""
        return self.nonce + self.ciphertext

    def to_base64(self) -> str:
        """Encode as base64 string for storage/transmission."""
        return base64.urlsafe_b64encode(self.to_bytes()).decode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> EncryptionResult:
        """Parse from combined bytes format."""
        if len(data) < NONCE_SIZE + TAG_SIZE:
            raise ValueError("Invalid encrypted data: too short")
        nonce = data[:NONCE_SIZE]
        ciphertext = data[NONCE_SIZE:]
        return cls(ciphertext=ciphertext, nonce=nonce, tag=b"")

    @classmethod
    def from_base64(cls, data: str) -> EncryptionResult:
        """Parse from base64 encoded string."""
        raw = base64.urlsafe_b64decode(data)
        return cls.from_bytes(raw)


class AESGCMEncryptor:
    """
    AES-256-GCM authenticated encryption.

    Provides encryption with authentication, ensuring both
    confidentiality and integrity of the data.

    Example:
        encryptor = AESGCMEncryptor(key)
        encrypted = encryptor.encrypt(b"secret data")
        decrypted = encryptor.decrypt(encrypted)
    """

    def __init__(self, key: bytes) -> None:
        """
        Initialize encryptor with a 256-bit key.

        Args:
            key: 32-byte encryption key

        Raises:
            ImportError: If cryptography library is not installed
            ValueError: If key is not 32 bytes
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            raise ImportError(
                "cryptography is required for encryption. "
                "Install with: pip install cryptography"
            )

        if len(key) != KEY_SIZE:
            raise ValueError(f"Key must be {KEY_SIZE} bytes (256 bits)")

        self._key = key
        self._aesgcm = AESGCM(key)

    def encrypt(
        self,
        plaintext: bytes,
        associated_data: Optional[bytes] = None,
    ) -> EncryptionResult:
        """
        Encrypt data using AES-256-GCM.

        Args:
            plaintext: Data to encrypt
            associated_data: Additional authenticated data (not encrypted)

        Returns:
            EncryptionResult containing ciphertext and nonce
        """
        nonce = os.urandom(NONCE_SIZE)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, associated_data)
        return EncryptionResult(ciphertext=ciphertext, nonce=nonce, tag=b"")

    def decrypt(
        self,
        encrypted: Union[EncryptionResult, bytes, str],
        associated_data: Optional[bytes] = None,
    ) -> bytes:
        """
        Decrypt data using AES-256-GCM.

        Args:
            encrypted: EncryptionResult, raw bytes, or base64 string
            associated_data: Additional authenticated data (must match encryption)

        Returns:
            Decrypted plaintext

        Raises:
            ValueError: If decryption fails (wrong key, tampered data, etc.)
        """
        if isinstance(encrypted, str):
            encrypted = EncryptionResult.from_base64(encrypted)
        elif isinstance(encrypted, bytes):
            encrypted = EncryptionResult.from_bytes(encrypted)

        try:
            return self._aesgcm.decrypt(
                encrypted.nonce,
                encrypted.ciphertext,
                associated_data,
            )
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}") from e

    def encrypt_string(
        self,
        plaintext: str,
        associated_data: Optional[bytes] = None,
    ) -> str:
        """
        Encrypt a string and return base64 encoded result.

        Args:
            plaintext: String to encrypt
            associated_data: Optional additional authenticated data

        Returns:
            Base64 encoded encrypted string
        """
        result = self.encrypt(plaintext.encode("utf-8"), associated_data)
        return result.to_base64()

    def decrypt_string(
        self,
        encrypted: str,
        associated_data: Optional[bytes] = None,
    ) -> str:
        """
        Decrypt a base64 encoded string.

        Args:
            encrypted: Base64 encoded encrypted string
            associated_data: Optional additional authenticated data

        Returns:
            Decrypted string
        """
        plaintext = self.decrypt(encrypted, associated_data)
        return plaintext.decode("utf-8")

    def encrypt_json(
        self,
        data: Any,
        associated_data: Optional[bytes] = None,
    ) -> str:
        """
        Encrypt a JSON-serializable object.

        Args:
            data: JSON-serializable data
            associated_data: Optional additional authenticated data

        Returns:
            Base64 encoded encrypted string
        """
        json_str = json.dumps(data, separators=(",", ":"))
        return self.encrypt_string(json_str, associated_data)

    def decrypt_json(
        self,
        encrypted: str,
        associated_data: Optional[bytes] = None,
    ) -> Any:
        """
        Decrypt and parse JSON data.

        Args:
            encrypted: Base64 encoded encrypted string
            associated_data: Optional additional authenticated data

        Returns:
            Parsed JSON data
        """
        json_str = self.decrypt_string(encrypted, associated_data)
        return json.loads(json_str)


def generate_key() -> bytes:
    """
    Generate a random 256-bit encryption key.

    Returns:
        32-byte random key
    """
    return os.urandom(KEY_SIZE)


def generate_key_from_password(
    password: str,
    salt: Optional[bytes] = None,
    iterations: int = 100000,
) -> tuple[bytes, bytes]:
    """
    Derive an encryption key from a password using PBKDF2.

    Args:
        password: Password to derive key from
        salt: Optional salt (generated if not provided)
        iterations: PBKDF2 iterations (default 100000)

    Returns:
        Tuple of (key, salt)

    Example:
        key, salt = generate_key_from_password("my_password")
        # Store salt with encrypted data for later decryption
    """
    if not CRYPTOGRAPHY_AVAILABLE:
        raise ImportError(
            "cryptography is required for key derivation. "
            "Install with: pip install cryptography"
        )

    if salt is None:
        salt = os.urandom(SALT_SIZE)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=iterations,
        backend=default_backend(),
    )

    key = kdf.derive(password.encode("utf-8"))
    return key, salt


def generate_key_from_password_scrypt(
    password: str,
    salt: Optional[bytes] = None,
    n: int = 2**14,
    r: int = 8,
    p: int = 1,
) -> tuple[bytes, bytes]:
    """
    Derive an encryption key from a password using scrypt.

    scrypt is memory-hard, making it more resistant to hardware attacks.

    Args:
        password: Password to derive key from
        salt: Optional salt (generated if not provided)
        n: CPU/memory cost parameter (default 2^14)
        r: Block size parameter
        p: Parallelization parameter

    Returns:
        Tuple of (key, salt)
    """
    if not CRYPTOGRAPHY_AVAILABLE:
        raise ImportError(
            "cryptography is required for key derivation. "
            "Install with: pip install cryptography"
        )

    if salt is None:
        salt = os.urandom(SALT_SIZE)

    kdf = Scrypt(
        salt=salt,
        length=KEY_SIZE,
        n=n,
        r=r,
        p=p,
        backend=default_backend(),
    )

    key = kdf.derive(password.encode("utf-8"))
    return key, salt


class PasswordBasedEncryptor:
    """
    Password-based encryption using AES-256-GCM with PBKDF2 key derivation.

    Automatically handles key derivation and salt management.

    Example:
        encryptor = PasswordBasedEncryptor("my_password")
        encrypted = encryptor.encrypt("secret data")
        decrypted = encryptor.decrypt(encrypted)
    """

    def __init__(
        self,
        password: str,
        iterations: int = 100000,
    ) -> None:
        """
        Initialize with a password.

        Args:
            password: Encryption password
            iterations: PBKDF2 iterations
        """
        self._password = password
        self._iterations = iterations

    def encrypt(self, plaintext: Union[str, bytes]) -> str:
        """
        Encrypt data with password-derived key.

        The salt is included in the output for later decryption.

        Args:
            plaintext: Data to encrypt (string or bytes)

        Returns:
            Base64 encoded encrypted string (includes salt)
        """
        if isinstance(plaintext, str):
            plaintext = plaintext.encode("utf-8")

        # Generate new salt and key for each encryption
        key, salt = generate_key_from_password(
            self._password,
            iterations=self._iterations,
        )

        encryptor = AESGCMEncryptor(key)
        result = encryptor.encrypt(plaintext)

        # Prepend salt to the encrypted data
        # Format: salt (16 bytes) + nonce (12 bytes) + ciphertext
        combined = salt + result.to_bytes()
        return base64.urlsafe_b64encode(combined).decode("utf-8")

    def decrypt(self, encrypted: str) -> bytes:
        """
        Decrypt data encrypted with this password.

        Args:
            encrypted: Base64 encoded encrypted string

        Returns:
            Decrypted bytes

        Raises:
            ValueError: If decryption fails
        """
        combined = base64.urlsafe_b64decode(encrypted)

        if len(combined) < SALT_SIZE + NONCE_SIZE + TAG_SIZE:
            raise ValueError("Invalid encrypted data: too short")

        # Extract salt and encrypted data
        salt = combined[:SALT_SIZE]
        encrypted_data = combined[SALT_SIZE:]

        # Derive key from password and salt
        key, _ = generate_key_from_password(
            self._password,
            salt=salt,
            iterations=self._iterations,
        )

        encryptor = AESGCMEncryptor(key)
        return encryptor.decrypt(encrypted_data)

    def decrypt_string(self, encrypted: str) -> str:
        """Decrypt and return as string."""
        return self.decrypt(encrypted).decode("utf-8")

    def encrypt_json(self, data: Any) -> str:
        """Encrypt JSON-serializable data."""
        json_str = json.dumps(data, separators=(",", ":"))
        return self.encrypt(json_str)

    def decrypt_json(self, encrypted: str) -> Any:
        """Decrypt and parse JSON data."""
        json_str = self.decrypt_string(encrypted)
        return json.loads(json_str)


def encrypt(plaintext: Union[str, bytes], key: bytes) -> str:
    """
    Simple encryption function.

    Args:
        plaintext: Data to encrypt
        key: 32-byte encryption key

    Returns:
        Base64 encoded encrypted string
    """
    if isinstance(plaintext, str):
        plaintext = plaintext.encode("utf-8")

    encryptor = AESGCMEncryptor(key)
    result = encryptor.encrypt(plaintext)
    return result.to_base64()


def decrypt(encrypted: str, key: bytes) -> bytes:
    """
    Simple decryption function.

    Args:
        encrypted: Base64 encoded encrypted string
        key: 32-byte encryption key

    Returns:
        Decrypted bytes
    """
    encryptor = AESGCMEncryptor(key)
    return encryptor.decrypt(encrypted)


def encrypt_with_password(plaintext: Union[str, bytes], password: str) -> str:
    """
    Encrypt data with a password.

    Args:
        plaintext: Data to encrypt
        password: Encryption password

    Returns:
        Base64 encoded encrypted string (includes salt)
    """
    encryptor = PasswordBasedEncryptor(password)
    return encryptor.encrypt(plaintext)


def decrypt_with_password(encrypted: str, password: str) -> bytes:
    """
    Decrypt data with a password.

    Args:
        encrypted: Base64 encoded encrypted string
        password: Encryption password

    Returns:
        Decrypted bytes
    """
    encryptor = PasswordBasedEncryptor(password)
    return encryptor.decrypt(encrypted)
