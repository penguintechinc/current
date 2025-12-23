"""Cached URL dataclass for high-performance redirect lookups."""

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True, frozen=True)
class CachedURL:
    """Immutable cached URL for redirect lookups.

    Uses slots=True for 30-50% memory reduction and frozen=True
    for immutability (safe for caching).

    Attributes:
        id: Database primary key.
        domain: Short domain (e.g., "short.io").
        slug: Short code (e.g., "abc123").
        original_url: Target URL to redirect to.
        ios_url: Optional iOS-specific redirect URL.
        android_url: Optional Android-specific redirect URL.
        expires_at: Optional Unix timestamp for expiration.
        password_hash: Optional bcrypt hash if password protected.
        max_clicks: Optional maximum click limit.
        click_count: Current number of clicks.
        is_active: Whether the URL is active.
    """

    id: int
    domain: str
    slug: str
    original_url: str
    ios_url: Optional[str] = None
    android_url: Optional[str] = None
    expires_at: Optional[int] = None
    password_hash: Optional[str] = None
    max_clicks: Optional[int] = None
    click_count: int = 0
    is_active: bool = True

    def is_expired(self, current_timestamp: int) -> bool:
        """Check if URL has expired."""
        if self.expires_at is None:
            return False
        return current_timestamp > self.expires_at

    def is_click_limit_reached(self) -> bool:
        """Check if click limit has been reached."""
        if self.max_clicks is None:
            return False
        return self.click_count >= self.max_clicks

    def is_password_protected(self) -> bool:
        """Check if URL requires password."""
        return self.password_hash is not None

    def get_redirect_url(self, device_type: Optional[str] = None) -> str:
        """Get the appropriate redirect URL based on device type.

        Args:
            device_type: One of 'ios', 'android', or None for default.

        Returns:
            The appropriate URL for the device type.
        """
        if device_type == "ios" and self.ios_url:
            return self.ios_url
        if device_type == "android" and self.android_url:
            return self.android_url
        return self.original_url

    def to_cache_dict(self) -> dict:
        """Convert to dictionary for Redis caching."""
        return {
            "id": self.id,
            "domain": self.domain,
            "slug": self.slug,
            "original_url": self.original_url,
            "ios_url": self.ios_url,
            "android_url": self.android_url,
            "expires_at": self.expires_at,
            "password_hash": self.password_hash,
            "max_clicks": self.max_clicks,
            "click_count": self.click_count,
            "is_active": self.is_active,
        }

    @classmethod
    def from_cache_dict(cls, data: dict) -> "CachedURL":
        """Create CachedURL from Redis cache dictionary."""
        return cls(
            id=data["id"],
            domain=data["domain"],
            slug=data["slug"],
            original_url=data["original_url"],
            ios_url=data.get("ios_url"),
            android_url=data.get("android_url"),
            expires_at=data.get("expires_at"),
            password_hash=data.get("password_hash"),
            max_clicks=data.get("max_clicks"),
            click_count=data.get("click_count", 0),
            is_active=data.get("is_active", True),
        )

    @classmethod
    def from_db_row(cls, row: dict, domain: str) -> "CachedURL":
        """Create CachedURL from database row."""
        return cls(
            id=row["id"],
            domain=domain,
            slug=row["slug"],
            original_url=row["original_url"],
            ios_url=row.get("ios_url"),
            android_url=row.get("android_url"),
            expires_at=int(row["expires_at"].timestamp()) if row.get("expires_at") else None,
            password_hash=row.get("password"),
            max_clicks=row.get("max_clicks"),
            click_count=row.get("click_count", 0),
            is_active=row.get("is_active", True),
        )
