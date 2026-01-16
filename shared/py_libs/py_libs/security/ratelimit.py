"""
Rate limiting utilities.

Provides rate limiting with:
- In-memory storage (for single instance)
- Redis storage (for distributed)
- Multiple strategies (fixed window, sliding window, token bucket)
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable, Dict, Optional, Tuple, Union

# Import Redis (optional)
try:
    import redis.asyncio as aioredis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


@dataclass(slots=True, frozen=True)
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    remaining: int
    reset_at: float  # Unix timestamp
    retry_after: Optional[float] = None  # Seconds until reset

    @property
    def reset_in(self) -> float:
        """Seconds until rate limit resets."""
        return max(0, self.reset_at - time.time())


@dataclass(slots=True)
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests: int = 100  # Number of requests allowed
    window: int = 60  # Time window in seconds
    burst: Optional[int] = None  # Allow burst up to this amount
    key_prefix: str = "ratelimit"

    @classmethod
    def per_second(cls, requests: int) -> RateLimitConfig:
        """Rate limit per second."""
        return cls(requests=requests, window=1)

    @classmethod
    def per_minute(cls, requests: int) -> RateLimitConfig:
        """Rate limit per minute."""
        return cls(requests=requests, window=60)

    @classmethod
    def per_hour(cls, requests: int) -> RateLimitConfig:
        """Rate limit per hour."""
        return cls(requests=requests, window=3600)

    @classmethod
    def per_day(cls, requests: int) -> RateLimitConfig:
        """Rate limit per day."""
        return cls(requests=requests, window=86400)


class RateLimitStorage(ABC):
    """Abstract base class for rate limit storage backends."""

    @abstractmethod
    async def increment(
        self,
        key: str,
        window: int,
    ) -> Tuple[int, float]:
        """
        Increment counter for key.

        Returns:
            Tuple of (current_count, window_reset_time)
        """
        ...

    @abstractmethod
    async def get_count(self, key: str) -> int:
        """Get current count for key."""
        ...

    @abstractmethod
    async def reset(self, key: str) -> None:
        """Reset counter for key."""
        ...


class InMemoryStorage(RateLimitStorage):
    """
    In-memory rate limit storage.

    Suitable for single-instance deployments.
    Not suitable for distributed systems.
    """

    def __init__(self) -> None:
        self._data: Dict[str, Tuple[int, float]] = {}
        self._lock = Lock()

    async def increment(self, key: str, window: int) -> Tuple[int, float]:
        """Increment counter for key."""
        current_time = time.time()

        with self._lock:
            if key in self._data:
                count, reset_at = self._data[key]
                if current_time >= reset_at:
                    # Window expired, reset
                    count = 1
                    reset_at = current_time + window
                else:
                    count += 1
            else:
                count = 1
                reset_at = current_time + window

            self._data[key] = (count, reset_at)
            return count, reset_at

    async def get_count(self, key: str) -> int:
        """Get current count for key."""
        with self._lock:
            if key not in self._data:
                return 0
            count, reset_at = self._data[key]
            if time.time() >= reset_at:
                return 0
            return count

    async def reset(self, key: str) -> None:
        """Reset counter for key."""
        with self._lock:
            self._data.pop(key, None)

    def cleanup(self) -> int:
        """Remove expired entries. Returns number of entries removed."""
        current_time = time.time()
        removed = 0

        with self._lock:
            expired_keys = [
                k for k, (_, reset_at) in self._data.items() if current_time >= reset_at
            ]
            for key in expired_keys:
                del self._data[key]
                removed += 1

        return removed


class RedisStorage(RateLimitStorage):
    """
    Redis-based rate limit storage.

    Suitable for distributed deployments.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        redis_client: Optional[Any] = None,
    ) -> None:
        if not REDIS_AVAILABLE:
            raise ImportError(
                "redis is required for Redis storage. "
                "Install with: pip install redis"
            )

        self._redis_url = redis_url
        self._client = redis_client

    async def _get_client(self) -> Any:
        """Get or create Redis client."""
        if self._client is None:
            self._client = aioredis.from_url(self._redis_url)
        return self._client

    async def increment(self, key: str, window: int) -> Tuple[int, float]:
        """Increment counter for key using Redis INCR with EXPIRE."""
        client = await self._get_client()
        current_time = time.time()

        # Use Lua script for atomic increment with expiry
        lua_script = """
        local current = redis.call('INCR', KEYS[1])
        if current == 1 then
            redis.call('EXPIRE', KEYS[1], ARGV[1])
        end
        local ttl = redis.call('TTL', KEYS[1])
        return {current, ttl}
        """

        result = await client.eval(lua_script, 1, key, window)
        count = int(result[0])
        ttl = int(result[1])
        reset_at = current_time + ttl

        return count, reset_at

    async def get_count(self, key: str) -> int:
        """Get current count for key."""
        client = await self._get_client()
        value = await client.get(key)
        return int(value) if value else 0

    async def reset(self, key: str) -> None:
        """Reset counter for key."""
        client = await self._get_client()
        await client.delete(key)

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()


class RateLimiter:
    """
    Rate limiter with configurable storage backend.

    Example:
        # In-memory rate limiter
        limiter = RateLimiter(
            config=RateLimitConfig.per_minute(100),
            storage=InMemoryStorage(),
        )

        # Check rate limit
        result = await limiter.check("user:123")
        if not result.allowed:
            return {"error": "Rate limit exceeded"}, 429
    """

    def __init__(
        self,
        config: Optional[RateLimitConfig] = None,
        storage: Optional[RateLimitStorage] = None,
    ) -> None:
        self.config = config or RateLimitConfig()
        self.storage = storage or InMemoryStorage()

    async def check(self, key: str) -> RateLimitResult:
        """
        Check if request is allowed under rate limit.

        Args:
            key: Rate limit key (e.g., IP address, user ID)

        Returns:
            RateLimitResult with allowed status and metadata
        """
        full_key = f"{self.config.key_prefix}:{key}"
        count, reset_at = await self.storage.increment(full_key, self.config.window)

        limit = self.config.burst or self.config.requests
        allowed = count <= limit
        remaining = max(0, limit - count)

        retry_after = None
        if not allowed:
            retry_after = reset_at - time.time()

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_at=reset_at,
            retry_after=retry_after,
        )

    async def reset(self, key: str) -> None:
        """Reset rate limit for a key."""
        full_key = f"{self.config.key_prefix}:{key}"
        await self.storage.reset(full_key)

    def get_headers(self, result: RateLimitResult) -> Dict[str, str]:
        """
        Get rate limit headers for response.

        Args:
            result: Rate limit check result

        Returns:
            Dictionary of rate limit headers
        """
        headers = {
            "X-RateLimit-Limit": str(self.config.requests),
            "X-RateLimit-Remaining": str(result.remaining),
            "X-RateLimit-Reset": str(int(result.reset_at)),
        }

        if result.retry_after is not None:
            headers["Retry-After"] = str(int(result.retry_after))

        return headers


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter for smoother rate limiting.

    Uses a sliding window algorithm that provides more consistent
    rate limiting compared to fixed window.
    """

    def __init__(
        self,
        config: Optional[RateLimitConfig] = None,
        storage: Optional[RateLimitStorage] = None,
    ) -> None:
        self.config = config or RateLimitConfig()
        self.storage = storage or InMemoryStorage()
        self._windows: Dict[str, list] = defaultdict(list)
        self._lock = Lock()

    async def check(self, key: str) -> RateLimitResult:
        """Check if request is allowed using sliding window."""
        current_time = time.time()
        window_start = current_time - self.config.window
        full_key = f"{self.config.key_prefix}:{key}"

        with self._lock:
            # Clean old requests
            self._windows[full_key] = [
                t for t in self._windows[full_key] if t > window_start
            ]

            count = len(self._windows[full_key])
            allowed = count < self.config.requests

            if allowed:
                self._windows[full_key].append(current_time)
                count += 1

        remaining = max(0, self.config.requests - count)
        reset_at = current_time + self.config.window

        retry_after = None
        if not allowed and self._windows[full_key]:
            # Time until oldest request expires
            oldest = min(self._windows[full_key])
            retry_after = oldest + self.config.window - current_time

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_at=reset_at,
            retry_after=retry_after,
        )


def rate_limit(
    config: Optional[RateLimitConfig] = None,
    key_func: Optional[Callable] = None,
    storage: Optional[RateLimitStorage] = None,
) -> Callable:
    """
    Decorator for rate limiting routes.

    Example:
        @app.route("/api/data")
        @rate_limit(config=RateLimitConfig.per_minute(100))
        async def get_data():
            return {"data": "value"}

    Args:
        config: Rate limit configuration
        key_func: Function to extract rate limit key from request
        storage: Storage backend
    """
    limiter = RateLimiter(config=config, storage=storage)

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get rate limit key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                # Default: try to get from request
                try:
                    from quart import request

                    key = request.remote_addr or "unknown"
                except ImportError:
                    key = "default"

            # Check rate limit
            result = await limiter.check(key)

            if not result.allowed:
                # Return 429 Too Many Requests
                headers = limiter.get_headers(result)
                return (
                    {"error": "Rate limit exceeded", "retry_after": result.retry_after},
                    429,
                    headers,
                )

            # Call the original function
            response = await func(*args, **kwargs)

            # Add rate limit headers to response
            headers = limiter.get_headers(result)
            if hasattr(response, "headers"):
                for name, value in headers.items():
                    response.headers[name] = value
            elif isinstance(response, tuple) and len(response) >= 3:
                resp_headers = dict(response[2])
                resp_headers.update(headers)
                response = (response[0], response[1], resp_headers)

            return response

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator
