"""Click event dataclass for async analytics processing."""

from dataclasses import dataclass, field
from typing import Optional
import time
import hashlib


@dataclass(slots=True)
class ClickEvent:
    """Click event for async processing.

    Uses slots=True for 30-50% memory reduction. Not frozen because
    we may need to update fields before processing.

    Attributes:
        url_id: Database ID of the short URL.
        timestamp: Unix timestamp of the click.
        ip_hash: SHA256 hash of IP address for privacy.
        country: ISO 3166-1 alpha-2 country code.
        region: Region/state name.
        city: City name.
        device_type: One of 'mobile', 'tablet', 'desktop'.
        browser: Browser family (e.g., 'Chrome', 'Firefox').
        browser_version: Browser version string.
        os: Operating system family (e.g., 'Windows', 'iOS').
        os_version: OS version string.
        referrer: Full referrer URL.
        referrer_domain: Domain extracted from referrer.
        user_agent: Full user agent string.
        is_unique: Whether this is first click from this IP.
        is_bot: Whether the request is from a known bot.
    """

    url_id: int
    timestamp: float = field(default_factory=time.time)
    ip_hash: str = ""
    country: str = ""
    region: str = ""
    city: str = ""
    device_type: str = "desktop"
    browser: str = ""
    browser_version: str = ""
    os: str = ""
    os_version: str = ""
    referrer: str = ""
    referrer_domain: str = ""
    user_agent: str = ""
    is_unique: bool = True
    is_bot: bool = False

    @staticmethod
    def hash_ip(ip_address: str, salt: str = "") -> str:
        """Hash IP address for privacy.

        Args:
            ip_address: The IP address to hash.
            salt: Optional salt for additional security.

        Returns:
            SHA256 hash of the IP address.
        """
        data = f"{ip_address}{salt}".encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def to_redis_dict(self) -> dict:
        """Convert to dictionary for Redis Streams."""
        return {
            "url_id": str(self.url_id),
            "timestamp": str(self.timestamp),
            "ip_hash": self.ip_hash,
            "country": self.country,
            "region": self.region,
            "city": self.city,
            "device_type": self.device_type,
            "browser": self.browser,
            "browser_version": self.browser_version,
            "os": self.os,
            "os_version": self.os_version,
            "referrer": self.referrer,
            "referrer_domain": self.referrer_domain,
            "is_unique": "1" if self.is_unique else "0",
            "is_bot": "1" if self.is_bot else "0",
        }

    @classmethod
    def from_redis_dict(cls, data: dict) -> "ClickEvent":
        """Create ClickEvent from Redis Streams data."""
        return cls(
            url_id=int(data.get("url_id", 0)),
            timestamp=float(data.get("timestamp", 0)),
            ip_hash=data.get("ip_hash", ""),
            country=data.get("country", ""),
            region=data.get("region", ""),
            city=data.get("city", ""),
            device_type=data.get("device_type", "desktop"),
            browser=data.get("browser", ""),
            browser_version=data.get("browser_version", ""),
            os=data.get("os", ""),
            os_version=data.get("os_version", ""),
            referrer=data.get("referrer", ""),
            referrer_domain=data.get("referrer_domain", ""),
            is_unique=data.get("is_unique", "1") == "1",
            is_bot=data.get("is_bot", "0") == "1",
        )

    def to_db_dict(self) -> dict:
        """Convert to dictionary for database insert."""
        from datetime import datetime

        return {
            "short_url_id": self.url_id,
            "clicked_at": datetime.fromtimestamp(self.timestamp),
            "ip_hash": self.ip_hash,
            "country": self.country,
            "region": self.region,
            "city": self.city,
            "device_type": self.device_type,
            "browser": self.browser,
            "browser_version": self.browser_version,
            "os": self.os,
            "os_version": self.os_version,
            "referrer": self.referrer[:500] if self.referrer else "",
            "referrer_domain": self.referrer_domain,
            "is_unique": self.is_unique,
            "is_bot": self.is_bot,
        }


@dataclass(slots=True)
class QRConfig:
    """QR code configuration for customization.

    Attributes:
        foreground_color: Hex color for QR modules (default black).
        background_color: Hex color for background (default white).
        logo_url: Optional URL to logo image to embed.
        logo_size: Logo size as percentage of QR size (10-50).
        error_correction: Error correction level (L, M, Q, H).
        style: Module style (square, rounded, dots).
        size: Output image size in pixels.
        frame_style: Optional frame style.
        frame_text: Optional text for frame.
    """

    foreground_color: str = "#000000"
    background_color: str = "#FFFFFF"
    logo_url: Optional[str] = None
    logo_size: int = 30
    error_correction: str = "M"
    style: str = "square"
    size: int = 400
    frame_style: Optional[str] = None
    frame_text: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "foreground_color": self.foreground_color,
            "background_color": self.background_color,
            "logo_url": self.logo_url,
            "logo_size": self.logo_size,
            "error_correction": self.error_correction,
            "style": self.style,
            "size": self.size,
            "frame_style": self.frame_style,
            "frame_text": self.frame_text,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QRConfig":
        """Create QRConfig from dictionary."""
        return cls(
            foreground_color=data.get("foreground_color", "#000000"),
            background_color=data.get("background_color", "#FFFFFF"),
            logo_url=data.get("logo_url"),
            logo_size=data.get("logo_size", 30),
            error_correction=data.get("error_correction", "M"),
            style=data.get("style", "square"),
            size=data.get("size", 400),
            frame_style=data.get("frame_style"),
            frame_text=data.get("frame_text"),
        )
