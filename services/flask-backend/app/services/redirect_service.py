"""Redirect service with 3-layer cache lookup."""

import logging
import time
from collections import deque
from functools import lru_cache
from threading import Lock, Thread
from typing import Optional

from flask import current_app

from ..dto import CachedURL, ClickEvent
from ..models import get_db
from .cache_service import get_cache_service

logger = logging.getLogger(__name__)


class RedirectService:
    """High-performance redirect service.

    Implements 3-layer cache lookup:
    - L1: In-memory (cachetools TTLCache)
    - L2: Redis
    - L3: PostgreSQL (PyDAL)

    Async click tracking via deque buffer.
    """

    # Click buffer configuration
    CLICK_BUFFER_SIZE = 10_000
    CLICK_FLUSH_BATCH_SIZE = 100
    CLICK_FLUSH_INTERVAL = 0.1  # 100ms

    def __init__(self):
        """Initialize redirect service."""
        self._click_buffer: deque[ClickEvent] = deque(maxlen=self.CLICK_BUFFER_SIZE)
        self._buffer_lock = Lock()
        self._flush_thread: Optional[Thread] = None
        self._running = False

    def start_background_workers(self) -> None:
        """Start background worker threads."""
        if self._running:
            return

        self._running = True
        self._flush_thread = Thread(target=self._flush_clicks_worker, daemon=True)
        self._flush_thread.start()
        logger.info("Redirect service background workers started")

    def stop_background_workers(self) -> None:
        """Stop background worker threads."""
        self._running = False
        if self._flush_thread:
            self._flush_thread.join(timeout=2.0)
        logger.info("Redirect service background workers stopped")

    def resolve_url(self, domain: str, slug: str) -> Optional[CachedURL]:
        """Resolve short URL using 3-layer cache.

        Args:
            domain: Short domain (e.g., "short.io").
            slug: Short code (e.g., "abc123").

        Returns:
            CachedURL if found and valid, None otherwise.
        """
        cache = get_cache_service()

        # L1 + L2 lookup
        url = cache.get(domain, slug)
        if url is not None:
            if self._is_url_valid(url):
                return url
            return None

        # L3 lookup (database)
        url = self._fetch_from_db(domain, slug)
        if url is not None:
            # Populate caches
            cache.set(url)
            if self._is_url_valid(url):
                return url

        return None

    def _is_url_valid(self, url: CachedURL) -> bool:
        """Check if URL is valid for redirect.

        Args:
            url: CachedURL to validate.

        Returns:
            True if valid for redirect.
        """
        if not url.is_active:
            return False

        current_ts = int(time.time())
        if url.is_expired(current_ts):
            return False

        if url.is_click_limit_reached():
            return False

        return True

    def _fetch_from_db(self, domain: str, slug: str) -> Optional[CachedURL]:
        """Fetch URL from database.

        Args:
            domain: Short domain.
            slug: Short code.

        Returns:
            CachedURL if found, None otherwise.
        """
        try:
            db = get_db()

            # Query with join to get domain info
            query = (
                (db.short_urls.slug == slug) &
                (db.domains.domain == domain) &
                (db.short_urls.domain_id == db.domains.id)
            )

            row = db(query).select(
                db.short_urls.ALL,
                db.domains.domain,
                join=db.domains.on(db.short_urls.domain_id == db.domains.id),
            ).first()

            if not row:
                return None

            return CachedURL.from_db_row(row.short_urls.as_dict(), domain)

        except Exception as e:
            logger.error(f"Database error fetching {domain}/{slug}: {e}")
            return None

    def track_click(self, event: ClickEvent) -> None:
        """Track click event (non-blocking).

        Adds event to buffer for async processing.

        Args:
            event: ClickEvent to track.
        """
        with self._buffer_lock:
            self._click_buffer.append(event)

        # Also increment real-time counter
        cache = get_cache_service()
        cache.increment_click_count(event.url_id)

    def _flush_clicks_worker(self) -> None:
        """Background worker to flush clicks to Redis."""
        while self._running:
            events = []

            # Collect batch of events
            with self._buffer_lock:
                while self._click_buffer and len(events) < self.CLICK_FLUSH_BATCH_SIZE:
                    try:
                        events.append(self._click_buffer.popleft())
                    except IndexError:
                        break

            if events:
                self._flush_events_to_redis(events)

            time.sleep(self.CLICK_FLUSH_INTERVAL)

    def _flush_events_to_redis(self, events: list[ClickEvent]) -> None:
        """Flush events to Redis Streams.

        Args:
            events: List of ClickEvents to flush.
        """
        cache = get_cache_service()
        redis = cache.redis

        if not redis:
            logger.warning("Redis not available, dropping click events")
            return

        try:
            pipe = redis.pipeline()
            for event in events:
                stream_key = f"clicks:{event.url_id}"
                pipe.xadd(stream_key, event.to_redis_dict(), maxlen=10000)
            pipe.execute()
        except Exception as e:
            logger.error(f"Failed to flush clicks to Redis: {e}")


# User-agent parsing with LRU cache
@lru_cache(maxsize=1000)
def parse_user_agent(ua_string: str) -> tuple[str, str, str, str, str]:
    """Parse user agent string with caching.

    Args:
        ua_string: User agent string.

    Returns:
        Tuple of (device_type, browser, browser_version, os, os_version).
    """
    try:
        from user_agents import parse
        ua = parse(ua_string)

        if ua.is_mobile:
            device_type = "mobile"
        elif ua.is_tablet:
            device_type = "tablet"
        else:
            device_type = "desktop"

        return (
            device_type,
            ua.browser.family or "",
            ua.browser.version_string or "",
            ua.os.family or "",
            ua.os.version_string or "",
        )
    except Exception:
        return ("desktop", "", "", "", "")


def detect_device_type(ua_string: str) -> str:
    """Quick device type detection without full UA parsing.

    Args:
        ua_string: User agent string.

    Returns:
        Device type: 'mobile', 'tablet', or 'desktop'.
    """
    ua_lower = ua_string.lower()

    # Mobile patterns
    mobile_patterns = [
        "iphone", "android", "mobile", "blackberry",
        "windows phone", "opera mini", "opera mobi"
    ]

    # Tablet patterns
    tablet_patterns = ["ipad", "tablet", "kindle", "playbook"]

    for pattern in tablet_patterns:
        if pattern in ua_lower:
            return "tablet"

    for pattern in mobile_patterns:
        if pattern in ua_lower:
            # Check it's not a tablet pretending to be mobile
            if "android" in ua_lower and "mobile" not in ua_lower:
                return "tablet"
            return "mobile"

    return "desktop"


def is_bot(ua_string: str) -> bool:
    """Check if user agent is a known bot.

    Args:
        ua_string: User agent string.

    Returns:
        True if bot/crawler detected.
    """
    ua_lower = ua_string.lower()

    bot_patterns = [
        "bot", "crawler", "spider", "slurp", "googlebot",
        "bingbot", "yandex", "baidu", "duckduck", "facebookexternalhit",
        "twitterbot", "linkedinbot", "pinterest", "whatsapp",
        "telegram", "curl", "wget", "python-requests", "scrapy"
    ]

    return any(pattern in ua_lower for pattern in bot_patterns)


def extract_referrer_domain(referrer: str) -> str:
    """Extract domain from referrer URL.

    Args:
        referrer: Full referrer URL.

    Returns:
        Domain portion of URL.
    """
    if not referrer:
        return ""

    try:
        from urllib.parse import urlparse
        parsed = urlparse(referrer)
        return parsed.netloc or ""
    except Exception:
        return ""


# Global redirect service instance
_redirect_service: Optional[RedirectService] = None


def get_redirect_service() -> RedirectService:
    """Get the global redirect service instance.

    Returns:
        RedirectService instance.
    """
    global _redirect_service
    if _redirect_service is None:
        _redirect_service = RedirectService()
    return _redirect_service


def init_redirect_service() -> RedirectService:
    """Initialize the global redirect service.

    Returns:
        RedirectService instance.
    """
    global _redirect_service
    _redirect_service = RedirectService()
    _redirect_service.start_background_workers()
    return _redirect_service
