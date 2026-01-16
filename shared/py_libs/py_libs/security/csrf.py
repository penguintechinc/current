"""
CSRF protection utilities.

Provides CSRF token generation and validation for:
- Form submissions
- AJAX requests
- API endpoints
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple


@dataclass(slots=True, frozen=True)
class CSRFConfig:
    """Configuration for CSRF protection."""

    secret_key: str
    token_length: int = 32
    max_age: int = 3600  # 1 hour
    header_name: str = "X-CSRF-Token"
    cookie_name: str = "csrf_token"
    cookie_secure: bool = True
    cookie_httponly: bool = True
    cookie_samesite: str = "Strict"
    safe_methods: Tuple[str, ...] = ("GET", "HEAD", "OPTIONS", "TRACE")


class CSRFProtection:
    """
    CSRF protection handler.

    Generates and validates CSRF tokens using HMAC signatures.

    Example:
        csrf = CSRFProtection(CSRFConfig(secret_key="your-secret"))

        # Generate token
        token = csrf.generate_token()

        # Validate token
        if not csrf.validate_token(token):
            return {"error": "Invalid CSRF token"}, 403
    """

    def __init__(self, config: CSRFConfig) -> None:
        self.config = config

    def generate_token(self, session_id: Optional[str] = None) -> str:
        """
        Generate a new CSRF token.

        Args:
            session_id: Optional session ID to bind token to session

        Returns:
            CSRF token string

        The token format is: {timestamp}:{random}:{signature}
        """
        timestamp = str(int(time.time()))
        random_part = secrets.token_urlsafe(self.config.token_length)

        # Create signature
        message = f"{timestamp}:{random_part}"
        if session_id:
            message += f":{session_id}"

        signature = self._sign(message)

        return f"{timestamp}:{random_part}:{signature}"

    def validate_token(
        self,
        token: str,
        session_id: Optional[str] = None,
    ) -> bool:
        """
        Validate a CSRF token.

        Args:
            token: CSRF token to validate
            session_id: Session ID if token was bound to session

        Returns:
            True if token is valid, False otherwise
        """
        try:
            parts = token.split(":")
            if len(parts) != 3:
                return False

            timestamp, random_part, signature = parts

            # Check timestamp
            token_time = int(timestamp)
            current_time = int(time.time())

            if current_time - token_time > self.config.max_age:
                return False  # Token expired

            if token_time > current_time + 60:
                return False  # Token from the future (clock skew)

            # Verify signature
            message = f"{timestamp}:{random_part}"
            if session_id:
                message += f":{session_id}"

            expected_sig = self._sign(message)

            return hmac.compare_digest(signature, expected_sig)

        except (ValueError, TypeError):
            return False

    def _sign(self, message: str) -> str:
        """Create HMAC signature for message."""
        return hmac.new(
            self.config.secret_key.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()[:32]

    def get_cookie_options(self) -> dict:
        """Get cookie options for setting CSRF cookie."""
        return {
            "key": self.config.cookie_name,
            "secure": self.config.cookie_secure,
            "httponly": self.config.cookie_httponly,
            "samesite": self.config.cookie_samesite,
            "max_age": self.config.max_age,
        }


class CSRFMiddleware:
    """
    ASGI middleware for CSRF protection.

    Example:
        app = Quart(__name__)
        csrf = CSRFProtection(CSRFConfig(secret_key="secret"))
        app = CSRFMiddleware(app, csrf)
    """

    def __init__(
        self,
        app: Any,
        csrf: CSRFProtection,
        exempt_paths: Optional[set] = None,
    ) -> None:
        self.app = app
        self.csrf = csrf
        self.exempt_paths = exempt_paths or set()

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        """ASGI interface."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        path = scope.get("path", "")

        # Skip safe methods
        if method in self.csrf.config.safe_methods:
            await self.app(scope, receive, send)
            return

        # Skip exempt paths
        if path in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        # Extract CSRF token from headers
        headers = dict(scope.get("headers", []))
        header_name = self.csrf.config.header_name.lower().encode()
        token = headers.get(header_name, b"").decode()

        if not token:
            # Try cookie
            cookie_header = headers.get(b"cookie", b"").decode()
            for part in cookie_header.split(";"):
                if "=" in part:
                    name, value = part.strip().split("=", 1)
                    if name == self.csrf.config.cookie_name:
                        token = value
                        break

        # Validate token
        if not self.csrf.validate_token(token):
            # Return 403 Forbidden
            await send(
                {
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b'{"error": "CSRF token missing or invalid"}',
                }
            )
            return

        await self.app(scope, receive, send)


def csrf_protect(
    csrf: CSRFProtection,
    exempt: bool = False,
) -> Callable:
    """
    Decorator for CSRF protection on routes.

    Example:
        csrf = CSRFProtection(CSRFConfig(secret_key="secret"))

        @app.route("/api/data", methods=["POST"])
        @csrf_protect(csrf)
        async def post_data():
            return {"status": "ok"}
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if exempt:
                return await func(*args, **kwargs)

            # Get request
            try:
                from quart import request
            except ImportError:
                # If no request context, skip CSRF check
                return await func(*args, **kwargs)

            # Skip safe methods
            if request.method in csrf.config.safe_methods:
                return await func(*args, **kwargs)

            # Get token from header or form
            token = request.headers.get(csrf.config.header_name)
            if not token:
                form = await request.form
                token = form.get("csrf_token", "")

            # Validate
            if not csrf.validate_token(token):
                return {"error": "CSRF token missing or invalid"}, 403

            return await func(*args, **kwargs)

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator


def generate_csrf_token(secret_key: str, session_id: Optional[str] = None) -> str:
    """
    Simple function to generate a CSRF token.

    Args:
        secret_key: Secret key for signing
        session_id: Optional session ID

    Returns:
        CSRF token string
    """
    csrf = CSRFProtection(CSRFConfig(secret_key=secret_key))
    return csrf.generate_token(session_id)


def validate_csrf_token(
    token: str,
    secret_key: str,
    session_id: Optional[str] = None,
    max_age: int = 3600,
) -> bool:
    """
    Simple function to validate a CSRF token.

    Args:
        token: CSRF token to validate
        secret_key: Secret key used for signing
        session_id: Session ID if token was bound
        max_age: Maximum age in seconds

    Returns:
        True if valid
    """
    csrf = CSRFProtection(CSRFConfig(secret_key=secret_key, max_age=max_age))
    return csrf.validate_token(token, session_id)
