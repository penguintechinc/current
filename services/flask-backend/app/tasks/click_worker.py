"""Click event worker for async analytics processing.

This worker consumes click events from the in-memory deque buffer
and persists them to PostgreSQL via PyDAL.
"""

import logging
import threading
import time
from collections import deque
from datetime import datetime
from typing import Optional

from ..dto import ClickEvent

logger = logging.getLogger(__name__)


class ClickWorker:
    """Background worker to process click events from buffer.

    Implements batched writes to PostgreSQL for efficient persistence.
    Uses thread-safe operations to consume from the shared deque buffer.
    """

    __slots__ = (
        "_buffer",
        "_batch_size",
        "_flush_interval",
        "_running",
        "_thread",
        "_db_getter",
        "_redis_client",
    )

    DEFAULT_BATCH_SIZE = 100
    DEFAULT_FLUSH_INTERVAL = 0.5  # 500ms

    def __init__(
        self,
        buffer: deque,
        db_getter: callable,
        redis_client=None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        flush_interval: float = DEFAULT_FLUSH_INTERVAL,
    ):
        """Initialize click worker.

        Args:
            buffer: Shared deque buffer containing ClickEvent objects.
            db_getter: Callable that returns PyDAL database instance.
            redis_client: Optional Redis client for real-time counters.
            batch_size: Number of events to batch before writing.
            flush_interval: Seconds between flush attempts.
        """
        self._buffer = buffer
        self._db_getter = db_getter
        self._redis_client = redis_client
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the background worker thread."""
        if self._running:
            logger.warning("Click worker already running")
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name="click-worker",
            daemon=True,
        )
        self._thread.start()
        logger.info("Click worker started")

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the background worker thread.

        Args:
            timeout: Seconds to wait for thread to finish.
        """
        if not self._running:
            return

        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("Click worker did not stop cleanly")
        logger.info("Click worker stopped")

    def _run_loop(self) -> None:
        """Main worker loop - drain buffer and persist events."""
        while self._running:
            try:
                events = self._drain_buffer()
                if events:
                    self._persist_events(events)
                    self._update_realtime_counters(events)
            except Exception as e:
                logger.error(f"Click worker error: {e}", exc_info=True)

            time.sleep(self._flush_interval)

        # Final flush on shutdown
        try:
            events = self._drain_buffer()
            if events:
                self._persist_events(events)
        except Exception as e:
            logger.error(f"Click worker final flush error: {e}")

    def _drain_buffer(self) -> list[ClickEvent]:
        """Drain events from buffer up to batch size.

        Returns:
            List of ClickEvent objects.
        """
        events = []
        try:
            while len(events) < self._batch_size:
                # popleft is thread-safe for deque
                event = self._buffer.popleft()
                events.append(event)
        except IndexError:
            # Buffer empty
            pass
        return events

    def _persist_events(self, events: list[ClickEvent]) -> None:
        """Persist click events to database.

        Args:
            events: List of ClickEvent objects to persist.
        """
        if not events:
            return

        try:
            db = self._db_getter()

            for event in events:
                db.click_events.insert(
                    short_url_id=event.url_id,
                    clicked_at=datetime.fromtimestamp(event.timestamp),
                    ip_hash=event.ip_hash,
                    country=event.country,
                    city=event.city,
                    device_type=event.device_type,
                    browser=event.browser,
                    os=event.os,
                    referrer_domain=event.referrer_domain,
                    is_unique=event.is_unique,
                    is_bot=event.is_bot,
                )

            db.commit()
            logger.debug(f"Persisted {len(events)} click events")

        except Exception as e:
            logger.error(f"Failed to persist click events: {e}")
            try:
                db.rollback()
            except Exception:
                pass

    def _update_realtime_counters(self, events: list[ClickEvent]) -> None:
        """Update real-time counters in Redis.

        Args:
            events: List of ClickEvent objects.
        """
        if not self._redis_client:
            return

        try:
            pipe = self._redis_client.pipeline()

            for event in events:
                # Increment total clicks
                pipe.incr(f"rt:clicks:{event.url_id}")

                # Minute-level granularity for real-time charts
                minute_ts = int(event.timestamp // 60) * 60
                pipe.incr(f"rt:clicks:{event.url_id}:min:{minute_ts}")
                pipe.expire(f"rt:clicks:{event.url_id}:min:{minute_ts}", 86400)

                # HyperLogLog for unique visitors (daily)
                date_key = datetime.fromtimestamp(event.timestamp).strftime("%Y%m%d")
                pipe.pfadd(f"unique:{event.url_id}:{date_key}", event.ip_hash)
                pipe.expire(f"unique:{event.url_id}:{date_key}", 604800)  # 7 days

                # Country counters
                if event.country:
                    pipe.hincrby(
                        f"rt:geo:{event.url_id}:{date_key}",
                        event.country,
                        1,
                    )
                    pipe.expire(f"rt:geo:{event.url_id}:{date_key}", 604800)

                # Device counters
                if event.device_type:
                    pipe.hincrby(
                        f"rt:device:{event.url_id}:{date_key}",
                        event.device_type,
                        1,
                    )
                    pipe.expire(f"rt:device:{event.url_id}:{date_key}", 604800)

            pipe.execute()

        except Exception as e:
            logger.warning(f"Failed to update Redis counters: {e}")


# Global worker instance
_click_worker: Optional[ClickWorker] = None


def start_click_worker(
    buffer: deque,
    db_getter: callable,
    redis_client=None,
) -> ClickWorker:
    """Start the global click worker.

    Args:
        buffer: Shared deque buffer for click events.
        db_getter: Callable returning PyDAL database instance.
        redis_client: Optional Redis client.

    Returns:
        ClickWorker instance.
    """
    global _click_worker

    if _click_worker is not None:
        logger.warning("Click worker already exists, stopping previous instance")
        _click_worker.stop()

    _click_worker = ClickWorker(
        buffer=buffer,
        db_getter=db_getter,
        redis_client=redis_client,
    )
    _click_worker.start()
    return _click_worker


def stop_click_worker() -> None:
    """Stop the global click worker."""
    global _click_worker

    if _click_worker is not None:
        _click_worker.stop()
        _click_worker = None
