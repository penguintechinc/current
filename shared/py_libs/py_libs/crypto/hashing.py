"""
Password hashing utilities.

Provides secure password hashing with:
- Argon2id (recommended, memory-hard)
- bcrypt (fallback, widely compatible)

Follows OWASP password storage recommendations.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# Import optional dependencies
try:
    import argon2
    from argon2 import PasswordHasher as Argon2Hasher
    from argon2.exceptions import (
        InvalidHashError,
        VerificationError,
        VerifyMismatchError,
    )

    ARGON2_AVAILABLE = True
except ImportError:
    ARGON2_AVAILABLE = False

try:
    import bcrypt

    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False


class HashAlgorithm(Enum):
    """Supported password hashing algorithms."""

    ARGON2ID = "argon2id"
    BCRYPT = "bcrypt"


@dataclass(slots=True, frozen=True)
class Argon2Options:
    """
    Configuration options for Argon2id hashing.

    Default values follow OWASP recommendations for 2024+.
    """

    time_cost: int = 3  # Number of iterations
    memory_cost: int = 65536  # Memory in KB (64MB)
    parallelism: int = 4  # Number of parallel threads
    hash_len: int = 32  # Output hash length in bytes
    salt_len: int = 16  # Salt length in bytes

    @classmethod
    def low_memory(cls) -> Argon2Options:
        """Lower memory settings for constrained environments."""
        return cls(time_cost=4, memory_cost=32768, parallelism=2)

    @classmethod
    def high_security(cls) -> Argon2Options:
        """Higher security settings for sensitive applications."""
        return cls(time_cost=4, memory_cost=131072, parallelism=4)


@dataclass(slots=True, frozen=True)
class BcryptOptions:
    """Configuration options for bcrypt hashing."""

    rounds: int = 12  # Cost factor (2^rounds iterations)

    @classmethod
    def fast(cls) -> BcryptOptions:
        """Faster settings for development/testing."""
        return cls(rounds=10)

    @classmethod
    def high_security(cls) -> BcryptOptions:
        """Higher security settings."""
        return cls(rounds=14)


class PasswordHasher(ABC):
    """Abstract base class for password hashers."""

    @abstractmethod
    def hash(self, password: str) -> str:
        """Hash a password and return the hash string."""
        ...

    @abstractmethod
    def verify(self, password: str, hash_str: str) -> bool:
        """Verify a password against a hash. Returns True if valid."""
        ...

    @abstractmethod
    def needs_rehash(self, hash_str: str) -> bool:
        """Check if a hash needs to be upgraded to new parameters."""
        ...


class Argon2PasswordHasher(PasswordHasher):
    """
    Argon2id password hasher.

    Argon2id is the recommended algorithm for password hashing as of 2024.
    It is memory-hard, making it resistant to GPU and ASIC attacks.

    Example:
        hasher = Argon2PasswordHasher()
        hash_str = hasher.hash("my_password")
        is_valid = hasher.verify("my_password", hash_str)
    """

    def __init__(self, options: Optional[Argon2Options] = None) -> None:
        if not ARGON2_AVAILABLE:
            raise ImportError(
                "argon2-cffi is required for Argon2 hashing. "
                "Install with: pip install argon2-cffi"
            )

        self.options = options or Argon2Options()
        self._hasher = Argon2Hasher(
            time_cost=self.options.time_cost,
            memory_cost=self.options.memory_cost,
            parallelism=self.options.parallelism,
            hash_len=self.options.hash_len,
            salt_len=self.options.salt_len,
            type=argon2.Type.ID,  # Argon2id
        )

    def hash(self, password: str) -> str:
        """
        Hash a password using Argon2id.

        Args:
            password: Plain text password

        Returns:
            Argon2id hash string in PHC format
        """
        return self._hasher.hash(password)

    def verify(self, password: str, hash_str: str) -> bool:
        """
        Verify a password against an Argon2id hash.

        Args:
            password: Plain text password to verify
            hash_str: Argon2id hash string

        Returns:
            True if password matches, False otherwise
        """
        try:
            self._hasher.verify(hash_str, password)
            return True
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, hash_str: str) -> bool:
        """
        Check if a hash was created with older parameters.

        Args:
            hash_str: Argon2id hash string

        Returns:
            True if hash should be upgraded
        """
        try:
            return self._hasher.check_needs_rehash(hash_str)
        except (InvalidHashError, ValueError):
            return True


class BcryptPasswordHasher(PasswordHasher):
    """
    bcrypt password hasher.

    bcrypt is a widely-supported password hashing algorithm.
    Use this as a fallback when Argon2 is not available.

    Example:
        hasher = BcryptPasswordHasher()
        hash_str = hasher.hash("my_password")
        is_valid = hasher.verify("my_password", hash_str)
    """

    def __init__(self, options: Optional[BcryptOptions] = None) -> None:
        if not BCRYPT_AVAILABLE:
            raise ImportError(
                "bcrypt is required for bcrypt hashing. "
                "Install with: pip install bcrypt"
            )

        self.options = options or BcryptOptions()

    def hash(self, password: str) -> str:
        """
        Hash a password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            bcrypt hash string
        """
        salt = bcrypt.gensalt(rounds=self.options.rounds)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def verify(self, password: str, hash_str: str) -> bool:
        """
        Verify a password against a bcrypt hash.

        Args:
            password: Plain text password to verify
            hash_str: bcrypt hash string

        Returns:
            True if password matches, False otherwise
        """
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"),
                hash_str.encode("utf-8"),
            )
        except (ValueError, TypeError):
            return False

    def needs_rehash(self, hash_str: str) -> bool:
        """
        Check if a hash was created with older rounds.

        Args:
            hash_str: bcrypt hash string

        Returns:
            True if hash should be upgraded
        """
        try:
            # Extract rounds from bcrypt hash (format: $2b$XX$...)
            match = re.match(r"^\$2[aby]?\$(\d+)\$", hash_str)
            if not match:
                return True
            current_rounds = int(match.group(1))
            return current_rounds < self.options.rounds
        except (ValueError, TypeError):
            return True


def get_default_hasher() -> PasswordHasher:
    """
    Get the default password hasher.

    Prefers Argon2id if available, falls back to bcrypt.

    Returns:
        PasswordHasher instance

    Raises:
        ImportError: If neither argon2-cffi nor bcrypt is installed
    """
    if ARGON2_AVAILABLE:
        return Argon2PasswordHasher()
    elif BCRYPT_AVAILABLE:
        return BcryptPasswordHasher()
    else:
        raise ImportError(
            "No password hashing library available. "
            "Install argon2-cffi (recommended) or bcrypt: "
            "pip install argon2-cffi"
        )


def hash_password(password: str, algorithm: Optional[HashAlgorithm] = None) -> str:
    """
    Hash a password using the specified or default algorithm.

    Args:
        password: Plain text password
        algorithm: Hashing algorithm (defaults to Argon2id if available)

    Returns:
        Password hash string

    Example:
        >>> hash_str = hash_password("my_secure_password")
        >>> hash_str.startswith("$argon2")
        True
    """
    if algorithm == HashAlgorithm.BCRYPT:
        hasher = BcryptPasswordHasher()
    elif algorithm == HashAlgorithm.ARGON2ID:
        hasher = Argon2PasswordHasher()
    else:
        hasher = get_default_hasher()

    return hasher.hash(password)


def verify_password(password: str, hash_str: str) -> bool:
    """
    Verify a password against a hash.

    Automatically detects the hash algorithm from the hash string.

    Args:
        password: Plain text password to verify
        hash_str: Password hash string

    Returns:
        True if password matches, False otherwise

    Example:
        >>> hash_str = hash_password("my_password")
        >>> verify_password("my_password", hash_str)
        True
        >>> verify_password("wrong_password", hash_str)
        False
    """
    if hash_str.startswith("$argon2"):
        if not ARGON2_AVAILABLE:
            return False
        hasher = Argon2PasswordHasher()
    elif hash_str.startswith("$2"):
        if not BCRYPT_AVAILABLE:
            return False
        hasher = BcryptPasswordHasher()
    else:
        return False

    return hasher.verify(password, hash_str)


def needs_rehash(hash_str: str) -> bool:
    """
    Check if a password hash needs to be upgraded.

    Args:
        hash_str: Password hash string

    Returns:
        True if hash should be upgraded to current parameters
    """
    if hash_str.startswith("$argon2"):
        if not ARGON2_AVAILABLE:
            return True
        hasher = Argon2PasswordHasher()
    elif hash_str.startswith("$2"):
        if not BCRYPT_AVAILABLE:
            return True
        hasher = BcryptPasswordHasher()
    else:
        return True

    return hasher.needs_rehash(hash_str)


def hash_data(data: bytes, algorithm: str = "sha256") -> str:
    """
    Hash arbitrary data using a cryptographic hash function.

    Args:
        data: Bytes to hash
        algorithm: Hash algorithm (sha256, sha384, sha512, sha3_256)

    Returns:
        Hexadecimal hash string

    Example:
        >>> hash_data(b"hello world")
        'b94d27b9...'
    """
    if algorithm == "sha256":
        return hashlib.sha256(data).hexdigest()
    elif algorithm == "sha384":
        return hashlib.sha384(data).hexdigest()
    elif algorithm == "sha512":
        return hashlib.sha512(data).hexdigest()
    elif algorithm == "sha3_256":
        return hashlib.sha3_256(data).hexdigest()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")


def hmac_sign(data: bytes, key: bytes, algorithm: str = "sha256") -> str:
    """
    Create an HMAC signature for data.

    Args:
        data: Data to sign
        key: Secret key
        algorithm: Hash algorithm

    Returns:
        Hexadecimal HMAC signature

    Example:
        >>> hmac_sign(b"message", b"secret_key")
        '4a5e3c...'
    """
    if algorithm == "sha256":
        return hmac.new(key, data, hashlib.sha256).hexdigest()
    elif algorithm == "sha384":
        return hmac.new(key, data, hashlib.sha384).hexdigest()
    elif algorithm == "sha512":
        return hmac.new(key, data, hashlib.sha512).hexdigest()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")


def hmac_verify(data: bytes, key: bytes, signature: str, algorithm: str = "sha256") -> bool:
    """
    Verify an HMAC signature.

    Args:
        data: Original data
        key: Secret key
        signature: HMAC signature to verify
        algorithm: Hash algorithm

    Returns:
        True if signature is valid
    """
    expected = hmac_sign(data, key, algorithm)
    return hmac.compare_digest(expected, signature)
