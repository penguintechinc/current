"""User management Pydantic models."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .common import PaginationMeta

# Valid roles matching Flask-Security-Too setup
VALID_ROLES = Literal["admin", "maintainer", "viewer"]


class CreateUserRequest(BaseModel):
    """Create user request payload (Admin only)."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    full_name: str = Field(default="", max_length=255, description="User full name")
    role: VALID_ROLES = Field(default="viewer", description="User role")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "newuser@example.com",
                "password": "securepassword123",
                "full_name": "Jane Doe",
                "role": "viewer",
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
        try:
            from py_libs.validation.password import (IsStrongPassword,
                                                     PasswordOptions)

            validator = IsStrongPassword(options=PasswordOptions.moderate())
            result = validator(v)
            if not result.is_valid:
                raise ValueError(result.error or "Password does not meet requirements")
        except ImportError:
            if len(v) < 8:
                raise ValueError("Password must be at least 8 characters")
        return v


class UpdateUserRequest(BaseModel):
    """Update user request payload (Admin only)."""

    email: Optional[EmailStr] = Field(None, description="New email address")
    password: Optional[str] = Field(
        None, min_length=8, description="New password (min 8 characters)"
    )
    full_name: Optional[str] = Field(None, max_length=255, description="New full name")
    role: Optional[VALID_ROLES] = Field(None, description="New role")
    is_active: Optional[bool] = Field(None, description="Active status")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "Jane Smith",
                "role": "maintainer",
                "is_active": True,
            }
        }
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: Optional[str]) -> Optional[str]:
        """Normalize email to lowercase and strip whitespace."""
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_full_name(cls, v: Optional[str]) -> Optional[str]:
        """Strip whitespace from full name."""
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: Optional[str]) -> Optional[str]:
        """Validate password meets strength requirements if provided."""
        if v is None:
            return v
        try:
            from py_libs.validation.password import (IsStrongPassword,
                                                     PasswordOptions)

            validator = IsStrongPassword(options=PasswordOptions.moderate())
            result = validator(v)
            if not result.is_valid:
                raise ValueError(result.error or "Password does not meet requirements")
        except ImportError:
            if len(v) < 8:
                raise ValueError("Password must be at least 8 characters")
        return v


class UserListItem(BaseModel):
    """User item in list responses."""

    id: int = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    full_name: str = Field(default="", description="User full name")
    role: str = Field(..., description="User role")
    is_active: bool = Field(default=True, description="Whether user is active")
    created_at: Optional[datetime] = Field(None, description="Account creation time")
    updated_at: Optional[datetime] = Field(None, description="Last update time")
    last_login_at: Optional[datetime] = Field(None, description="Last login time")

    model_config = ConfigDict(from_attributes=True)


class UserDetailResponse(UserListItem):
    """Detailed user response for single user endpoints."""

    login_count: Optional[int] = Field(None, description="Total login count")
    confirmed_at: Optional[datetime] = Field(
        None, description="Email confirmation time"
    )


class PaginatedUsersResponse(BaseModel):
    """Paginated users list response."""

    users: List[UserListItem] = Field(..., description="List of users")
    pagination: PaginationMeta = Field(..., description="Pagination info")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "users": [
                    {
                        "id": 1,
                        "email": "admin@example.com",
                        "full_name": "Admin User",
                        "role": "admin",
                        "is_active": True,
                    }
                ],
                "pagination": {
                    "page": 1,
                    "per_page": 20,
                    "total": 1,
                    "pages": 1,
                },
            }
        }
    )


class UserCreatedResponse(BaseModel):
    """Response after creating a user."""

    message: str = Field(default="User created successfully")
    user: UserListItem = Field(..., description="Created user data")


class UserUpdatedResponse(BaseModel):
    """Response after updating a user."""

    message: str = Field(default="User updated successfully")
    user: UserListItem = Field(..., description="Updated user data")


class UserDeletedResponse(BaseModel):
    """Response after deleting a user."""

    message: str = Field(default="User deleted successfully")


class RolesResponse(BaseModel):
    """Available roles response."""

    roles: List[str] = Field(..., description="List of valid roles")
    descriptions: dict[str, str] = Field(..., description="Role descriptions")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "roles": ["admin", "maintainer", "viewer"],
                "descriptions": {
                    "admin": "Full access: user CRUD, settings, all features",
                    "maintainer": "Read/write access to resources, no user management",
                    "viewer": "Read-only access to resources",
                },
            }
        }
    )
