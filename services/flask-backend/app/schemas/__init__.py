"""Pydantic schema models for Flask/Quart API validation."""

from .auth import (
    LoginRequest,
    LogoutResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)
from .common import (
    ErrorResponse,
    HealthResponse,
    MessageResponse,
    PaginatedResponse,
    PaginationMeta,
    TimestampMixin,
)
from .users import (
    CreateUserRequest,
    PaginatedUsersResponse,
    RolesResponse,
    UpdateUserRequest,
    UserCreatedResponse,
    UserDeletedResponse,
    UserDetailResponse,
    UserListItem,
    UserUpdatedResponse,
)

__all__ = [
    # Auth schemas
    "LoginRequest",
    "RegisterRequest",
    "RefreshTokenRequest",
    "UserResponse",
    "TokenResponse",
    "RefreshTokenResponse",
    "LogoutResponse",
    "RegisterResponse",
    # User schemas
    "CreateUserRequest",
    "UpdateUserRequest",
    "UserListItem",
    "UserDetailResponse",
    "PaginatedUsersResponse",
    "UserCreatedResponse",
    "UserUpdatedResponse",
    "UserDeletedResponse",
    "RolesResponse",
    # Common schemas
    "ErrorResponse",
    "MessageResponse",
    "PaginationMeta",
    "PaginatedResponse",
    "HealthResponse",
    "TimestampMixin",
]
