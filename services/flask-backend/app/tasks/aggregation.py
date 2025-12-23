"""Daily stats aggregation worker.

Aggregates click events into daily_stats table for efficient dashboard queries.
Uses APScheduler for scheduled execution.
"""

import json
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class StatsAggregator:
    """Aggregates click events into daily statistics.

    Pre-computes statistics for dashboard performance:
    - Total clicks per URL per day
    - Unique visitors (from HyperLogLog or distinct IP hashes)
    - Breakdown by country, device, browser, referrer
    """

    __slots__ = ("_db_getter", "_redis_client")

    def __init__(self, db_getter: callable, redis_client=None):
        """Initialize stats aggregator.

        Args:
            db_getter: Callable returning PyDAL database instance.
            redis_client: Optional Redis client for HyperLogLog unique counts.
        """
        self._db_getter = db_getter
        self._redis_client = redis_client

    def aggregate_day(self, target_date: date) -> int:
        """Aggregate click events for a specific day.

        Args:
            target_date: The date to aggregate.

        Returns:
            Number of URLs processed.
        """
        db = self._db_getter()
        processed = 0

        try:
            # Get all URLs with clicks on target date
            start_dt = datetime.combine(target_date, datetime.min.time())
            end_dt = datetime.combine(target_date + timedelta(days=1), datetime.min.time())

            # Find URLs with clicks on this day
            clicks_query = db(
                (db.click_events.clicked_at >= start_dt)
                & (db.click_events.clicked_at < end_dt)
            )

            # Get distinct URL IDs
            url_ids = set()
            for row in clicks_query.select(db.click_events.short_url_id, distinct=True):
                url_ids.add(row.short_url_id)

            logger.info(f"Aggregating stats for {len(url_ids)} URLs on {target_date}")

            for url_id in url_ids:
                self._aggregate_url_day(db, url_id, target_date, start_dt, end_dt)
                processed += 1

            db.commit()
            logger.info(f"Aggregated {processed} URLs for {target_date}")

        except Exception as e:
            logger.error(f"Aggregation failed for {target_date}: {e}", exc_info=True)
            try:
                db.rollback()
            except Exception:
                pass

        return processed

    def _aggregate_url_day(
        self,
        db,
        url_id: int,
        target_date: date,
        start_dt: datetime,
        end_dt: datetime,
    ) -> None:
        """Aggregate stats for a single URL on a single day.

        Args:
            db: PyDAL database instance.
            url_id: Short URL ID.
            target_date: Date to aggregate.
            start_dt: Start datetime.
            end_dt: End datetime.
        """
        # Query click events for this URL on this day
        clicks = db(
            (db.click_events.short_url_id == url_id)
            & (db.click_events.clicked_at >= start_dt)
            & (db.click_events.clicked_at < end_dt)
        ).select()

        if not clicks:
            return

        # Calculate aggregates
        total_clicks = len(clicks)
        unique_ips = set()
        by_country = {}
        by_device = {}
        by_browser = {}
        by_referrer = {}

        for click in clicks:
            # Unique visitors by IP hash
            if click.ip_hash:
                unique_ips.add(click.ip_hash)

            # Country breakdown
            country = click.country or "XX"
            by_country[country] = by_country.get(country, 0) + 1

            # Device breakdown
            device = click.device_type or "unknown"
            by_device[device] = by_device.get(device, 0) + 1

            # Browser breakdown
            browser = click.browser or "unknown"
            by_browser[browser] = by_browser.get(browser, 0) + 1

            # Referrer breakdown
            referrer = click.referrer_domain or "direct"
            by_referrer[referrer] = by_referrer.get(referrer, 0) + 1

        # Try to get more accurate unique count from Redis HyperLogLog
        unique_clicks = len(unique_ips)
        if self._redis_client:
            try:
                date_key = target_date.strftime("%Y%m%d")
                hll_count = self._redis_client.pfcount(f"unique:{url_id}:{date_key}")
                if hll_count > 0:
                    unique_clicks = hll_count
            except Exception as e:
                logger.debug(f"HyperLogLog count failed: {e}")

        # Check if stats already exist for this URL/date
        existing = db(
            (db.daily_stats.short_url_id == url_id)
            & (db.daily_stats.date == target_date)
        ).select().first()

        stats_data = {
            "clicks": total_clicks,
            "unique_clicks": unique_clicks,
            "by_country": json.dumps(by_country),
            "by_device": json.dumps(by_device),
            "by_browser": json.dumps(by_browser),
            "by_referrer": json.dumps(by_referrer),
        }

        if existing:
            db(db.daily_stats.id == existing.id).update(**stats_data)
        else:
            db.daily_stats.insert(
                short_url_id=url_id,
                date=target_date,
                **stats_data,
            )

    def aggregate_yesterday(self) -> int:
        """Aggregate stats for yesterday (scheduled job).

        Returns:
            Number of URLs processed.
        """
        yesterday = date.today() - timedelta(days=1)
        return self.aggregate_day(yesterday)

    def backfill(self, days: int = 7) -> int:
        """Backfill stats for the past N days.

        Args:
            days: Number of days to backfill.

        Returns:
            Total number of URLs processed.
        """
        total = 0
        today = date.today()

        for i in range(1, days + 1):
            target = today - timedelta(days=i)
            total += self.aggregate_day(target)

        return total


# Global scheduler instance
_scheduler: Optional[BackgroundScheduler] = None
_aggregator: Optional[StatsAggregator] = None


def start_aggregation_scheduler(
    db_getter: callable,
    redis_client=None,
    hour: int = 2,
    minute: int = 0,
) -> BackgroundScheduler:
    """Start the aggregation scheduler.

    Runs daily at specified time (default 2:00 AM) to aggregate
    the previous day's click events.

    Args:
        db_getter: Callable returning PyDAL database instance.
        redis_client: Optional Redis client.
        hour: Hour to run aggregation (0-23).
        minute: Minute to run aggregation (0-59).

    Returns:
        BackgroundScheduler instance.
    """
    global _scheduler, _aggregator

    if _scheduler is not None:
        logger.warning("Aggregation scheduler already running")
        return _scheduler

    _aggregator = StatsAggregator(db_getter, redis_client)
    _scheduler = BackgroundScheduler()

    # Schedule daily aggregation
    _scheduler.add_job(
        _aggregator.aggregate_yesterday,
        trigger=CronTrigger(hour=hour, minute=minute),
        id="daily_aggregation",
        name="Daily stats aggregation",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(f"Aggregation scheduler started (runs daily at {hour:02d}:{minute:02d})")

    return _scheduler


def stop_aggregation_scheduler() -> None:
    """Stop the aggregation scheduler."""
    global _scheduler, _aggregator

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        _aggregator = None
        logger.info("Aggregation scheduler stopped")


def get_aggregator() -> Optional[StatsAggregator]:
    """Get the global stats aggregator.

    Returns:
        StatsAggregator instance or None if not initialized.
    """
    return _aggregator


def run_aggregation_now(target_date: Optional[date] = None) -> int:
    """Run aggregation immediately (for testing/manual trigger).

    Args:
        target_date: Date to aggregate (defaults to yesterday).

    Returns:
        Number of URLs processed.
    """
    if _aggregator is None:
        logger.error("Aggregator not initialized")
        return 0

    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    return _aggregator.aggregate_day(target_date)
