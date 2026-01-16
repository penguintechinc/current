"""
Crypto module - Cryptographic utilities.

Provides:
- tokens: Secure token generation
- hashing: Password hashing (Argon2id, bcrypt)
- encryption: AES-256-GCM encryption
"""

from py_libs.crypto.tokens import (
    generate_token,
    generate_hex_token,
    generate_api_key,
    generate_timestamped_token,
    extract_timestamp,
    is_token_expired,
    generate_signed_token,
    verify_signed_token,
    generate_password_reset_token,
    verify_password_reset_token,
    generate_email_verification_token,
    verify_email_verification_token,
    constant_time_compare,
    TokenOptions,
)

from py_libs.crypto.hashing import (
    hash_password,
    verify_password,
    needs_rehash,
    hash_data,
    hmac_sign,
    hmac_verify,
    get_default_hasher,
    HashAlgorithm,
    Argon2Options,
    BcryptOptions,
    Argon2PasswordHasher,
    BcryptPasswordHasher,
    PasswordHasher,
    ARGON2_AVAILABLE,
    BCRYPT_AVAILABLE,
)

from py_libs.crypto.encryption import (
    encrypt,
    decrypt,
    encrypt_with_password,
    decrypt_with_password,
    generate_key,
    generate_key_from_password,
    generate_key_from_password_scrypt,
    AESGCMEncryptor,
    PasswordBasedEncryptor,
    EncryptionResult,
    CRYPTOGRAPHY_AVAILABLE,
    KEY_SIZE,
    NONCE_SIZE,
)

__all__ = [
    # Token generation
    "generate_token",
    "generate_hex_token",
    "generate_api_key",
    "generate_timestamped_token",
    "extract_timestamp",
    "is_token_expired",
    "generate_signed_token",
    "verify_signed_token",
    "generate_password_reset_token",
    "verify_password_reset_token",
    "generate_email_verification_token",
    "verify_email_verification_token",
    "constant_time_compare",
    "TokenOptions",
    # Password hashing
    "hash_password",
    "verify_password",
    "needs_rehash",
    "hash_data",
    "hmac_sign",
    "hmac_verify",
    "get_default_hasher",
    "HashAlgorithm",
    "Argon2Options",
    "BcryptOptions",
    "Argon2PasswordHasher",
    "BcryptPasswordHasher",
    "PasswordHasher",
    "ARGON2_AVAILABLE",
    "BCRYPT_AVAILABLE",
    # Encryption
    "encrypt",
    "decrypt",
    "encrypt_with_password",
    "decrypt_with_password",
    "generate_key",
    "generate_key_from_password",
    "generate_key_from_password_scrypt",
    "AESGCMEncryptor",
    "PasswordBasedEncryptor",
    "EncryptionResult",
    "CRYPTOGRAPHY_AVAILABLE",
    "KEY_SIZE",
    "NONCE_SIZE",
]
