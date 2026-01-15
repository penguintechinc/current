"""Authentication Pydantic models."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    """Login request payload."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "securepassword123",
            }
        }
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email to lowercase and strip whitespace."""
        if isinstance(v, str):
            return v.strip().lower()
        return v


class RegisterRequest(BaseModel):
    """User registration request payload."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    full_name: str = Field(default="", max_length=255, description="User full name")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "newuser@example.com",
                "password": "securepassword123",
                "full_name": "John Doe",
            }
        }
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email to lowercase and strip whitespace."""
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_full_name(cls, v: str) -> str:
        """Strip whitespace from full name."""
        if isinstance(v, str):
            return v.strip()
        return v or ""

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets strength requirements."""
        # Import here to avoid circular imports
        try:
            from py_libs.validation.password import IsStrongPassword, PasswordOptions

            validator = IsStrongPassword(options=PasswordOptions.moderate())
            result = validator(v)
            if not result.is_valid:
                raise ValueError(result.error or "Password does not meet requirements")
        except ImportError:
            # Fallback if py_libs not available
            if len(v) < 8:
                raise ValueError("Password must be at least 8 characters")
        return v


class RefreshTokenRequest(BaseModel):
    """Token refresh request payload."""

    refresh_token: str = Field(..., min_length=1, description="Refresh token")


class UserResponse(BaseModel):
    """User data in responses."""

    id: int = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    full_name: str = Field(default="", description="User full name")
    role: str = Field(..., description="User role")
    is_active: bool = Field(default=True, description="Whether user is active")
    roles: Optional[List[str]] = Field(
        None, description="List of role names (Flask-Security)"
    )
    created_at: Optional[datetime] = Field(None, description="Account creation time")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "email": "user@example.com",
                "full_name": "John Doe",
                "role": "admin",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00",
            }
        },
    )


class TokenResponse(BaseModel):
    """Authentication token response."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    user: UserResponse = Field(..., description="Authenticated user data")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIs...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
                "token_type": "Bearer",
                "expires_in": 3600,
                "user": {
                    "id": 1,
                    "email": "user@example.com",
                    "full_name": "John Doe",
                    "role": "admin",
                },
            }
        }
    )


class RefreshTokenResponse(BaseModel):
    """Token refresh response (no user data)."""

    access_token: str = Field(..., description="New JWT access token")
    refresh_token: str = Field(..., description="New JWT refresh token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")


class LogoutResponse(BaseModel):
    """Logout response."""

    message: str = Field(default="Successfully logged out")
    tokens_revoked: int = Field(default=0, description="Number of tokens revoked")


class RegisterResponse(BaseModel):
    """Registration response."""

    message: str = Field(default="Registration successful")
    user: UserResponse = Field(..., description="Created user data")
