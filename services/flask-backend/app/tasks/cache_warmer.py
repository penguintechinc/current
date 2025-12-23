"""Cache warmer for popular URLs.

Pre-warms the L1/L2 cache with frequently accessed URLs
to reduce database load and improve response times.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..dto import CachedURL
from ..services.cache_service import get_cache_service

logger = logging.getLogger(__name__)


class CacheWarmer:
    """Pre-warms cache with popular URLs.

    Identifies high-traffic URLs and ensures they're in the L1/L2 cache
    before they're requested, reducing cold-start latency.
    """

    __slots__ = ("_db_getter", "_redis_client", "_top_n")

    DEFAULT_TOP_N = 1000

    def __init__(
        self,
        db_getter: callable,
        redis_client=None,
        top_n: int = DEFAULT_TOP_N,
    ):
        """Initialize cache warmer.

        Args:
            db_getter: Callable returning PyDAL database instance.
            redis_client: Optional Redis client for click counts.
            top_n: Number of top URLs to warm.
        """
        self._db_getter = db_getter
        self._redis_client = redis_client
        self._top_n = top_n

    def warm(self) -> int:
        """Warm cache with popular URLs.

        Returns:
            Number of URLs warmed.
        """
        logger.info("Starting cache warm-up")

        try:
            urls = self._get_popular_urls()
            warmed = self._warm_urls(urls)
            logger.info(f"Warmed {warmed} URLs into cache")
            return warmed

        except Exception as e:
            logger.error(f"Cache warm-up failed: {e}", exc_info=True)
            return 0

    def _get_popular_urls(self) -> list[tuple[int, str, str]]:
        """Get list of popular URLs to warm.

        Combines recent click data with Redis real-time counters
        to identify high-traffic URLs.

        Returns:
            List of (url_id, domain, slug) tuples.
        """
        db = self._db_getter()
        popular = []

        # Strategy 1: URLs with most clicks in last 24 hours (from DB)
        yesterday = datetime.utcnow() - timedelta(days=1)

        try:
            # Get URLs with recent clicks, ordered by count
            recent = db(db.click_events.clicked_at >= yesterday).select(
                db.click_events.short_url_id,
                db.click_events.short_url_id.count().with_alias("click_count"),
                groupby=db.click_events.short_url_id,
                orderby=~db.click_events.short_url_id.count(),
                limitby=(0, self._top_n),
            )

            url_ids = [row.click_events.short_url_id for row in recent]

            if url_ids:
                # Get URL details
                urls = db(db.short_urls.id.belongs(url_ids)).select(
                    db.short_urls.ALL,
                    db.domains.domain,
                    left=db.domains.on(db.short_urls.domain_id == db.domains.id),
                )

                for url in urls:
                    if url.short_urls and url.domains:
                        popular.append(
                            (url.short_urls.id, url.domains.domain, url.short_urls.slug)
                        )

        except Exception as e:
            logger.warning(f"Failed to get popular URLs from DB: {e}")

        # Strategy 2: Add URLs with high real-time counts from Redis
        if self._redis_client and len(popular) < self._top_n:
            try:
                # Scan for real-time counter keys
                cursor = 0
                redis_urls = []

                while True:
                    cursor, keys = self._redis_client.scan(
                        cursor=cursor,
                        match="rt:clicks:*",
                        count=100,
                    )

                    for key in keys:
                        # Skip minute-level keys
                        if ":min:" in key:
                            continue

                        try:
                            url_id = int(key.split(":")[-1])
                            count = int(self._redis_client.get(key) or 0)
                            redis_urls.append((url_id, count))
                        except (ValueError, IndexError):
                            continue

                    if cursor == 0:
                        break

                # Sort by count and add top URLs not already in list
                redis_urls.sort(key=lambda x: x[1], reverse=True)
                existing_ids = {p[0] for p in popular}

                for url_id, _ in redis_urls:
                    if url_id in existing_ids:
                        continue
                    if len(popular) >= self._top_n:
                        break

                    # Get URL details
                    url = db(db.short_urls.id == url_id).select(
                        db.short_urls.ALL,
                        db.domains.domain,
                        left=db.domains.on(db.short_urls.domain_id == db.domains.id),
                    ).first()

                    if url and url.short_urls and url.domains:
                        popular.append(
                            (url.short_urls.id, url.domains.domain, url.short_urls.slug)
                        )
                        existing_ids.add(url_id)

            except Exception as e:
                logger.warning(f"Failed to get popular URLs from Redis: {e}")

        return popular

    def _warm_urls(self, urls: list[tuple[int, str, str]]) -> int:
        """Warm specified URLs into cache.

        Args:
            urls: List of (url_id, domain, slug) tuples.

        Returns:
            Number of URLs successfully warmed.
        """
        if not urls:
            return 0

        db = self._db_getter()
        cache = get_cache_service()
        warmed = 0

        for url_id, domain, slug in urls:
            try:
                # Skip if already in cache
                if cache.get(domain, slug) is not None:
                    continue

                # Fetch from database
                url = db(db.short_urls.id == url_id).select(
                    db.short_urls.ALL,
                    db.domains.domain,
                    left=db.domains.on(db.short_urls.domain_id == db.domains.id),
                ).first()

                if not url or not url.short_urls:
                    continue

                # Create CachedURL object
                cached = CachedURL(
                    id=url.short_urls.id,
                    domain=url.domains.domain if url.domains else domain,
                    slug=url.short_urls.slug,
                    original_url=url.short_urls.original_url,
                    ios_url=url.short_urls.ios_url,
                    android_url=url.short_urls.android_url,
                    expires_at=int(url.short_urls.expires_at.timestamp())
                    if url.short_urls.expires_at
                    else None,
                    password_hash=url.short_urls.password,
                    is_active=True,
                )

                # Add to cache
                cache.set(cached)
                warmed += 1

            except Exception as e:
                logger.debug(f"Failed to warm URL {url_id}: {e}")
                continue

        return warmed


# Global scheduler instance
_warmer_scheduler: Optional[BackgroundScheduler] = None
_cache_warmer: Optional[CacheWarmer] = None


def start_cache_warmer(
    db_getter: callable,
    redis_client=None,
    interval_minutes: int = 15,
    top_n: int = CacheWarmer.DEFAULT_TOP_N,
) -> BackgroundScheduler:
    """Start the cache warmer scheduler.

    Args:
        db_getter: Callable returning PyDAL database instance.
        redis_client: Optional Redis client.
        interval_minutes: Minutes between warm-up runs.
        top_n: Number of top URLs to warm.

    Returns:
        BackgroundScheduler instance.
    """
    global _warmer_scheduler, _cache_warmer

    if _warmer_scheduler is not None:
        logger.warning("Cache warmer already running")
        return _warmer_scheduler

    _cache_warmer = CacheWarmer(db_getter, redis_client, top_n)
    _warmer_scheduler = BackgroundScheduler()

    # Schedule periodic warming
    _warmer_scheduler.add_job(
        _cache_warmer.warm,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="cache_warmer",
        name="Cache warmer",
        replace_existing=True,
    )

    _warmer_scheduler.start()

    # Run initial warm-up
    _cache_warmer.warm()

    logger.info(f"Cache warmer started (runs every {interval_minutes} minutes)")
    return _warmer_scheduler


def stop_cache_warmer() -> None:
    """Stop the cache warmer scheduler."""
    global _warmer_scheduler, _cache_warmer

    if _warmer_scheduler is not None:
        _warmer_scheduler.shutdown(wait=False)
        _warmer_scheduler = None
        _cache_warmer = None
        logger.info("Cache warmer stopped")


def warm_popular_urls() -> int:
    """Manually trigger cache warm-up.

    Returns:
        Number of URLs warmed.
    """
    if _cache_warmer is None:
        logger.error("Cache warmer not initialized")
        return 0

    return _cache_warmer.warm()
