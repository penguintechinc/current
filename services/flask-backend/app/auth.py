"""
Authentication Endpoints.

Provides authentication endpoints using Flask-Security-Too with Pydantic validation.
Maintains backward API compatibility with the original JWT-based implementation.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from functools import wraps
from typing import Any, Callable

from pydantic import ValidationError
from quart import Blueprint, current_app, g, jsonify, request

from .async_db import run_sync
from .models import (
    get_user_by_email,
    get_user_by_id,
    is_refresh_token_valid,
    revoke_all_user_tokens,
    revoke_refresh_token,
    store_refresh_token,
)
from .schemas import (
    LoginRequest,
    LogoutResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)

auth_bp = Blueprint("auth", __name__)


# Auth decorators for backward compatibility


def auth_required(func: Callable) -> Callable:
    """
    Decorator to require authentication.

    Checks for valid JWT token in Authorization header.
    Sets g.current_user on success.
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Try Flask-Security first (if not in testing mode)
        try:
            from flask_security import current_user

            if current_user is not None and current_user.is_authenticated:
                g.current_user = current_user.as_dict()
                return await func(*args, **kwargs)
        except (ImportError, RuntimeError, AttributeError):
            pass

        # Fallback to JWT validation
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authorization header required"}), 401

        token = auth_header[7:]  # Remove "Bearer " prefix

        try:
            import jwt

            payload = jwt.decode(
                token,
                current_app.config["JWT_SECRET_KEY"],
                algorithms=["HS256"],
            )

            if payload.get("type") != "access":
                return jsonify({"error": "Invalid token type"}), 401

            user_id = int(payload["sub"])
            user = await run_sync(get_user_by_id, user_id)

            if not user or not user.get("is_active"):
                return jsonify({"error": "User not found or deactivated"}), 401

            g.current_user = user
            return await func(*args, **kwargs)

        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

    return wrapper


def admin_required(func: Callable) -> Callable:
    """Decorator to require admin role."""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        user = g.get("current_user")
        if not user:
            return jsonify({"error": "Authentication required"}), 401

        if user.get("role") != "admin":
            return jsonify({"error": "Admin access required"}), 403

        return await func(*args, **kwargs)

    return wrapper


def maintainer_or_admin_required(func: Callable) -> Callable:
    """Decorator to require maintainer or admin role."""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        user = g.get("current_user")
        if not user:
            return jsonify({"error": "Authentication required"}), 401

        if user.get("role") not in ("admin", "maintainer"):
            return jsonify({"error": "Maintainer or admin access required"}), 403

        return await func(*args, **kwargs)

    return wrapper


def get_current_user() -> dict | None:
    """Get current authenticated user from request context."""
    return g.get("current_user")


# Password hashing using py_libs or fallback


def hash_password(password: str) -> str:
    """Hash password using bcrypt (or Argon2id if available)."""
    try:
        from py_libs.crypto.hashing import hash_password as py_hash

        return py_hash(password)
    except ImportError:
        import bcrypt

        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash."""
    try:
        from py_libs.crypto.hashing import verify_password as py_verify

        return py_verify(password, password_hash)
    except ImportError:
        import bcrypt

        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except ValueError:
            return False


# Token creation


def create_access_token(user_id: int, role: str) -> str:
    """Create JWT access token."""
    import jwt

    expires = datetime.utcnow() + current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "exp": expires,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


def create_refresh_token(user_id: int) -> tuple[str, datetime]:
    """Create JWT refresh token and store hash in database."""
    import jwt

    expires = datetime.utcnow() + current_app.config["JWT_REFRESH_TOKEN_EXPIRES"]
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expires,
        "iat": datetime.utcnow(),
    }
    token = jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")

    # Store hash of token in database for revocation
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    store_refresh_token(user_id, token_hash, expires)

    return token, expires


# Auth endpoints


@auth_bp.route("/login", methods=["POST"])
async def login():
    """
    Login endpoint - returns access and refresh tokens.

    Request body (JSON):
        email: User email
        password: User password

    Returns:
        access_token: JWT access token
        refresh_token: JWT refresh token
        token_type: "Bearer"
        expires_in: Token expiration in seconds
        user: User data
    """
    data = await request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    # Validate with Pydantic
    try:
        login_req = LoginRequest(**data)
    except ValidationError as e:
        error_msg = e.errors()[0].get("msg", "Validation error")
        return jsonify({"error": error_msg}), 400

    # Find user (run sync PyDAL in thread pool)
    user = await run_sync(get_user_by_email, login_req.email)
    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    # Verify password
    if not verify_password(login_req.password, user["password_hash"]):
        # Log failed login attempt
        try:
            from py_libs.security.audit import audit_login_failure

            await run_sync(
                audit_login_failure,
                login_req.email,
                ip_address=request.remote_addr,
            )
        except ImportError:
            pass

        return jsonify({"error": "Invalid email or password"}), 401

    # Check if user is active
    if not user.get("is_active"):
        return jsonify({"error": "Account is deactivated"}), 401

    # Generate tokens
    access_token = create_access_token(user["id"], user["role"])
    refresh_token, refresh_expires = await run_sync(create_refresh_token, user["id"])

    # Log successful login
    try:
        from py_libs.security.audit import audit_login_success

        await run_sync(
            audit_login_success,
            str(user["id"]),
            ip_address=request.remote_addr,
        )
    except ImportError:
        pass

    # Build response using Pydantic model
    user_response = UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user.get("full_name", ""),
        role=user["role"],
        is_active=user.get("is_active", True),
    )

    response = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_in=int(current_app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds()),
        user=user_response,
    )

    return jsonify(response.model_dump()), 200


@auth_bp.route("/refresh", methods=["POST"])
async def refresh():
    """
    Refresh access token using refresh token.

    Request body (JSON):
        refresh_token: JWT refresh token

    Returns:
        access_token: New JWT access token
        refresh_token: New JWT refresh token
        token_type: "Bearer"
        expires_in: Token expiration in seconds
    """
    import jwt

    data = await request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    # Validate with Pydantic
    try:
        refresh_req = RefreshTokenRequest(**data)
    except ValidationError as e:
        error_msg = e.errors()[0].get("msg", "Validation error")
        return jsonify({"error": error_msg}), 400

    # Decode token
    try:
        payload = jwt.decode(
            refresh_req.refresh_token,
            current_app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Refresh token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid refresh token"}), 401

    # Verify token type
    if payload.get("type") != "refresh":
        return jsonify({"error": "Invalid token type"}), 401

    # Check if token is revoked
    token_hash = hashlib.sha256(refresh_req.refresh_token.encode()).hexdigest()
    if not await run_sync(is_refresh_token_valid, token_hash):
        return jsonify({"error": "Refresh token has been revoked"}), 401

    # Get user
    user_id = int(payload["sub"])
    user = await run_sync(get_user_by_id, user_id)
    if not user or not user.get("is_active"):
        return jsonify({"error": "User not found or deactivated"}), 401

    # Revoke old refresh token
    await run_sync(revoke_refresh_token, token_hash)

    # Generate new tokens
    access_token = create_access_token(user["id"], user["role"])
    new_refresh_token, refresh_expires = await run_sync(create_refresh_token, user["id"])

    response = RefreshTokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="Bearer",
        expires_in=int(current_app.config["JWT_ACCESS_TOKEN_EXPIRES"].total_seconds()),
    )

    return jsonify(response.model_dump()), 200


@auth_bp.route("/logout", methods=["POST"])
@auth_required
async def logout():
    """
    Logout endpoint - revokes all refresh tokens for user.

    Requires authentication.

    Returns:
        message: Success message
        tokens_revoked: Number of tokens revoked
    """
    user = get_current_user()

    # Revoke all user's refresh tokens
    revoked_count = await run_sync(revoke_all_user_tokens, user["id"])

    response = LogoutResponse(
        message="Successfully logged out",
        tokens_revoked=revoked_count,
    )

    return jsonify(response.model_dump()), 200


@auth_bp.route("/me", methods=["GET"])
@auth_required
async def get_me():
    """
    Get current user profile.

    Requires authentication.

    Returns:
        User profile data
    """
    user = get_current_user()

    response = UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user.get("full_name", ""),
        role=user["role"],
        is_active=user.get("is_active", True),
        created_at=user.get("created_at"),
    )

    return jsonify(response.model_dump(mode="json")), 200


@auth_bp.route("/register", methods=["POST"])
async def register():
    """
    Register new user (creates viewer role by default).

    Request body (JSON):
        email: User email
        password: Password (min 8 characters)
        full_name: Optional full name

    Returns:
        message: Success message
        user: Created user data
    """
    from .models import create_user

    data = await request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    # Validate with Pydantic (includes password strength validation)
    try:
        register_req = RegisterRequest(**data)
    except ValidationError as e:
        error_msg = e.errors()[0].get("msg", "Validation error")
        return jsonify({"error": error_msg}), 400

    # Check if user exists
    existing = await run_sync(get_user_by_email, register_req.email)
    if existing:
        return jsonify({"error": "Email already registered"}), 409

    # Hash password
    password_hash = hash_password(register_req.password)

    # Create user
    user = await run_sync(
        create_user,
        email=register_req.email,
        password_hash=password_hash,
        full_name=register_req.full_name,
        role="viewer",  # Default role for self-registration
    )

    # Build response
    user_response = UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user.get("full_name", ""),
        role=user["role"],
        is_active=True,
    )

    response = RegisterResponse(
        message="Registration successful",
        user=user_response,
    )

    return jsonify(response.model_dump()), 201
