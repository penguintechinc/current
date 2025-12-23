"""Data Transfer Objects with slotted dataclasses for performance."""

from .cached_url import CachedURL
from .click_event import ClickEvent, QRConfig

__all__ = ["CachedURL", "ClickEvent", "QRConfig"]
