"""Authentication module for URL shortener.

Includes:
- Core JWT authentication (login, register, refresh)
- Enterprise SSO/OAuth integration (license-gated)
"""

from .core import (
    auth_bp,
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
)
from .sso import sso_bp

__all__ = [
    "auth_bp",
    "sso_bp",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
]
