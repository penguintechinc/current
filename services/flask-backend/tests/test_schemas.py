"""Tests for Pydantic schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_login_request_valid():
    """Test valid login request."""
    from app.schemas import LoginRequest

    req = LoginRequest(email="test@example.com", password="password123")
    assert req.email == "test@example.com"
    assert req.password == "password123"


def test_login_request_email_normalization():
    """Test email normalization in login request."""
    from app.schemas import LoginRequest

    req = LoginRequest(email="  TEST@EXAMPLE.COM  ", password="password")
    assert req.email == "test@example.com"


def test_login_request_invalid_email():
    """Test login request with invalid email."""
    from app.schemas import LoginRequest

    with pytest.raises(ValidationError):
        LoginRequest(email="not-an-email", password="password")


def test_register_request_valid():
    """Test valid register request."""
    from app.schemas import RegisterRequest

    req = RegisterRequest(
        email="new@example.com",
        password="securePassword123!",
        full_name="John Doe",
    )
    assert req.email == "new@example.com"
    assert req.full_name == "John Doe"


def test_register_request_password_too_short():
    """Test register request with short password."""
    from app.schemas import RegisterRequest

    with pytest.raises(ValidationError):
        RegisterRequest(
            email="test@example.com",
            password="short",  # Less than 8 chars
        )


def test_create_user_request_valid():
    """Test valid create user request."""
    from app.schemas import CreateUserRequest

    req = CreateUserRequest(
        email="admin@example.com",
        password="securePassword123!",
        full_name="Admin User",
        role="admin",
    )
    assert req.email == "admin@example.com"
    assert req.role == "admin"


def test_create_user_request_invalid_role():
    """Test create user request with invalid role."""
    from app.schemas import CreateUserRequest

    with pytest.raises(ValidationError):
        CreateUserRequest(
            email="test@example.com",
            password="password123!",
            role="superadmin",  # Invalid role
        )


def test_update_user_request_partial():
    """Test partial update user request."""
    from app.schemas import UpdateUserRequest

    # Only updating full_name
    req = UpdateUserRequest(full_name="New Name")
    assert req.full_name == "New Name"
    assert req.email is None
    assert req.role is None


def test_user_response():
    """Test user response model."""
    from app.schemas import UserResponse

    user = UserResponse(
        id=1,
        email="test@example.com",
        full_name="Test User",
        role="viewer",
        is_active=True,
    )

    data = user.model_dump()
    assert data["id"] == 1
    assert data["email"] == "test@example.com"
    assert data["role"] == "viewer"


def test_token_response():
    """Test token response model."""
    from app.schemas import TokenResponse, UserResponse

    user = UserResponse(
        id=1,
        email="test@example.com",
        full_name="Test",
        role="viewer",
    )

    token = TokenResponse(
        access_token="access123",
        refresh_token="refresh123",
        expires_in=3600,
        user=user,
    )

    data = token.model_dump()
    assert data["access_token"] == "access123"
    assert data["token_type"] == "Bearer"
    assert data["user"]["email"] == "test@example.com"
