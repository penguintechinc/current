"""Cache service with L1 (in-memory) and L2 (Redis) caching."""

import json
import logging
from threading import Lock
from typing import Optional

from cachetools import TTLCache
from flask import current_app

from ..dto import CachedURL

logger = logging.getLogger(__name__)


class CacheService:
    """Three-layer cache service for URL lookups.

    L1: In-memory TTLCache (per-worker, ~1ms)
    L2: Redis cache (shared, ~2ms)
    L3: PostgreSQL (via PyDAL, ~5-10ms)

    Uses slotted dataclasses for memory efficiency.
    """

    # L1 cache configuration
    L1_MAX_SIZE = 10_000
    L1_TTL = 300  # 5 minutes

    # L2 cache configuration
    L2_TTL = 3600  # 1 hour

    def __init__(self, redis_client=None):
        """Initialize cache service.

        Args:
            redis_client: Redis client instance. If None, will try to get
                         from Flask app context.
        """
        self._redis = redis_client
        self._l1_cache: TTLCache[str, CachedURL] = TTLCache(
            maxsize=self.L1_MAX_SIZE,
            ttl=self.L1_TTL
        )
        self._l1_lock = Lock()

    @property
    def redis(self):
        """Get Redis client, lazily from app context if needed."""
        if self._redis is None:
            self._redis = current_app.extensions.get("redis")
        return self._redis

    def _make_key(self, domain: str, slug: str) -> str:
        """Create cache key from domain and slug."""
        return f"url:{domain}:{slug}"

    def get_l1(self, domain: str, slug: str) -> Optional[CachedURL]:
        """Get URL from L1 in-memory cache.

        Args:
            domain: Short domain.
            slug: Short code.

        Returns:
            CachedURL if found, None otherwise.
        """
        key = self._make_key(domain, slug)
        with self._l1_lock:
            return self._l1_cache.get(key)

    def set_l1(self, url: CachedURL) -> None:
        """Set URL in L1 in-memory cache.

        Args:
            url: CachedURL to cache.
        """
        key = self._make_key(url.domain, url.slug)
        with self._l1_lock:
            self._l1_cache[key] = url

    def get_l2(self, domain: str, slug: str) -> Optional[CachedURL]:
        """Get URL from L2 Redis cache.

        Args:
            domain: Short domain.
            slug: Short code.

        Returns:
            CachedURL if found, None otherwise.
        """
        if not self.redis:
            return None

        key = self._make_key(domain, slug)
        try:
            data = self.redis.get(key)
            if data:
                return CachedURL.from_cache_dict(json.loads(data))
        except Exception as e:
            logger.warning(f"Redis get error for {key}: {e}")
        return None

    def set_l2(self, url: CachedURL) -> None:
        """Set URL in L2 Redis cache.

        Args:
            url: CachedURL to cache.
        """
        if not self.redis:
            return

        key = self._make_key(url.domain, url.slug)
        try:
            self.redis.set(
                key,
                json.dumps(url.to_cache_dict()),
                ex=self.L2_TTL
            )
        except Exception as e:
            logger.warning(f"Redis set error for {key}: {e}")

    def get(self, domain: str, slug: str) -> Optional[CachedURL]:
        """Get URL from cache (L1 -> L2).

        Does NOT query L3 (database). Use RedirectService for full lookup.

        Args:
            domain: Short domain.
            slug: Short code.

        Returns:
            CachedURL if found in any cache layer, None otherwise.
        """
        # Try L1 first
        url = self.get_l1(domain, slug)
        if url is not None:
            return url

        # Try L2
        url = self.get_l2(domain, slug)
        if url is not None:
            # Populate L1 on L2 hit
            self.set_l1(url)
            return url

        return None

    def set(self, url: CachedURL) -> None:
        """Set URL in both L1 and L2 caches.

        Args:
            url: CachedURL to cache.
        """
        self.set_l1(url)
        self.set_l2(url)

    def invalidate(self, domain: str, slug: str) -> None:
        """Invalidate URL from all cache layers.

        Args:
            domain: Short domain.
            slug: Short code.
        """
        key = self._make_key(domain, slug)

        # Clear L1
        with self._l1_lock:
            self._l1_cache.pop(key, None)

        # Clear L2
        if self.redis:
            try:
                self.redis.delete(key)
            except Exception as e:
                logger.warning(f"Redis delete error for {key}: {e}")

        # Publish invalidation for other workers
        self._publish_invalidation(domain, slug)

    def _publish_invalidation(self, domain: str, slug: str) -> None:
        """Publish cache invalidation to other workers via Redis pub/sub.

        Args:
            domain: Short domain.
            slug: Short code.
        """
        if not self.redis:
            return

        try:
            message = json.dumps({"domain": domain, "slug": slug})
            self.redis.publish("cache:invalidate", message)
        except Exception as e:
            logger.warning(f"Redis publish error: {e}")

    def subscribe_invalidations(self, callback) -> None:
        """Subscribe to cache invalidation messages.

        Should be called from a background thread.

        Args:
            callback: Function to call with (domain, slug) on invalidation.
        """
        if not self.redis:
            return

        try:
            pubsub = self.redis.pubsub()
            pubsub.subscribe("cache:invalidate")

            for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        domain = data.get("domain")
                        slug = data.get("slug")
                        if domain and slug:
                            callback(domain, slug)
                    except Exception as e:
                        logger.warning(f"Invalidation parse error: {e}")
        except Exception as e:
            logger.error(f"Redis subscribe error: {e}")

    def clear_l1(self) -> None:
        """Clear entire L1 cache."""
        with self._l1_lock:
            self._l1_cache.clear()

    def get_l1_stats(self) -> dict:
        """Get L1 cache statistics.

        Returns:
            Dict with cache stats.
        """
        with self._l1_lock:
            return {
                "size": len(self._l1_cache),
                "max_size": self._l1_cache.maxsize,
                "ttl": self._l1_cache.ttl,
            }

    # Real-time click counter methods (using Redis)

    def increment_click_count(self, url_id: int) -> int:
        """Increment real-time click counter.

        Args:
            url_id: URL database ID.

        Returns:
            New click count.
        """
        if not self.redis:
            return 0

        import time
        minute = int(time.time() // 60)
        key = f"rt:clicks:{url_id}:min:{minute}"

        try:
            count = self.redis.incr(key)
            self.redis.expire(key, 3600)  # 1 hour TTL
            return count
        except Exception as e:
            logger.warning(f"Redis incr error for {key}: {e}")
            return 0

    def get_realtime_clicks(self, url_id: int, minutes: int = 60) -> int:
        """Get total clicks in the last N minutes.

        Args:
            url_id: URL database ID.
            minutes: Number of minutes to sum.

        Returns:
            Total clicks in the time period.
        """
        if not self.redis:
            return 0

        import time
        current_minute = int(time.time() // 60)

        total = 0
        for offset in range(minutes):
            minute = current_minute - offset
            key = f"rt:clicks:{url_id}:min:{minute}"
            try:
                count = self.redis.get(key)
                if count:
                    total += int(count)
            except Exception as e:
                logger.warning(f"Redis get error for {key}: {e}")

        return total

    # HyperLogLog for unique visitors

    def add_unique_visitor(self, url_id: int, ip_hash: str, date: str) -> bool:
        """Add visitor to unique set using HyperLogLog.

        Args:
            url_id: URL database ID.
            ip_hash: Hashed IP address.
            date: Date string (YYYY-MM-DD).

        Returns:
            True if this is a new unique visitor.
        """
        if not self.redis:
            return True  # Assume unique if no Redis

        key = f"unique:{url_id}:{date}"
        try:
            # PFADD returns 1 if the cardinality changed (new visitor)
            result = self.redis.pfadd(key, ip_hash)
            self.redis.expire(key, 86400 * 7)  # 7 days TTL
            return result == 1
        except Exception as e:
            logger.warning(f"Redis pfadd error for {key}: {e}")
            return True

    def get_unique_count(self, url_id: int, date: str) -> int:
        """Get unique visitor count for a date.

        Args:
            url_id: URL database ID.
            date: Date string (YYYY-MM-DD).

        Returns:
            Approximate unique visitor count.
        """
        if not self.redis:
            return 0

        key = f"unique:{url_id}:{date}"
        try:
            return self.redis.pfcount(key)
        except Exception as e:
            logger.warning(f"Redis pfcount error for {key}: {e}")
            return 0


# Global cache service instance
_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """Get the global cache service instance.

    Creates a new instance if none exists.

    Returns:
        CacheService instance.
    """
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


def init_cache_service(redis_client=None) -> CacheService:
    """Initialize the global cache service.

    Args:
        redis_client: Redis client instance.

    Returns:
        CacheService instance.
    """
    global _cache_service
    _cache_service = CacheService(redis_client=redis_client)
    return _cache_service
