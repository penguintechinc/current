#!/usr/bin/env python3
"""
Flask Backend Load/Performance Tests.

Tests API performance under load using concurrent requests.
Requires a running server (set BASE_URL environment variable).

Usage:
    BASE_URL=http://localhost:5000 python test_load.py
    BASE_URL=http://localhost:5000 python test_load.py --requests 1000 --concurrency 50
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class LoadTestResult:
    """Load test result metrics."""

    endpoint: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_time: float
    response_times: list[float] = field(default_factory=list)

    @property
    def requests_per_second(self) -> float:
        """Calculate requests per second."""
        if self.total_time > 0:
            return self.total_requests / self.total_time
        return 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_requests > 0:
            return (self.successful_requests / self.total_requests) * 100
        return 0

    @property
    def avg_response_time(self) -> float:
        """Average response time in ms."""
        if self.response_times:
            return statistics.mean(self.response_times) * 1000
        return 0

    @property
    def p50_response_time(self) -> float:
        """50th percentile response time in ms."""
        if self.response_times:
            return statistics.median(self.response_times) * 1000
        return 0

    @property
    def p95_response_time(self) -> float:
        """95th percentile response time in ms."""
        if len(self.response_times) >= 20:
            sorted_times = sorted(self.response_times)
            idx = int(len(sorted_times) * 0.95)
            return sorted_times[idx] * 1000
        return self.avg_response_time

    @property
    def p99_response_time(self) -> float:
        """99th percentile response time in ms."""
        if len(self.response_times) >= 100:
            sorted_times = sorted(self.response_times)
            idx = int(len(sorted_times) * 0.99)
            return sorted_times[idx] * 1000
        return self.p95_response_time


class LoadTester:
    """API load tester."""

    def __init__(self, base_url: str, requests: int = 100, concurrency: int = 10):
        self.base_url = base_url.rstrip("/")
        self.total_requests = requests
        self.concurrency = concurrency
        self.results: list[LoadTestResult] = []

    async def make_request(
        self, client, method: str, path: str, json: dict | None = None
    ) -> tuple[bool, float]:
        """Make a single request and return (success, response_time)."""
        import httpx

        start = time.perf_counter()
        try:
            response = await client.request(method, path, json=json, timeout=30.0)
            elapsed = time.perf_counter() - start
            return response.status_code < 500, elapsed
        except Exception:
            elapsed = time.perf_counter() - start
            return False, elapsed

    async def run_load_test(
        self,
        name: str,
        method: str,
        path: str,
        json: dict | None = None,
    ) -> LoadTestResult:
        """Run load test for a specific endpoint."""
        import httpx

        print(f"\nTesting: {name}")
        print(f"  {method} {path}")
        print(f"  Requests: {self.total_requests}, Concurrency: {self.concurrency}")

        result = LoadTestResult(
            endpoint=f"{method} {path}",
            total_requests=self.total_requests,
            successful_requests=0,
            failed_requests=0,
            total_time=0,
        )

        semaphore = asyncio.Semaphore(self.concurrency)

        async def bounded_request(client):
            async with semaphore:
                return await self.make_request(client, method, path, json)

        async with httpx.AsyncClient(base_url=self.base_url) as client:
            start_time = time.perf_counter()

            tasks = [bounded_request(client) for _ in range(self.total_requests)]
            responses = await asyncio.gather(*tasks)

            result.total_time = time.perf_counter() - start_time

            for success, response_time in responses:
                if success:
                    result.successful_requests += 1
                else:
                    result.failed_requests += 1
                result.response_times.append(response_time)

        # Print results
        print(f"  Duration: {result.total_time:.2f}s")
        print(f"  RPS: {result.requests_per_second:.2f}")
        print(f"  Success Rate: {result.success_rate:.1f}%")
        print(f"  Avg Response: {result.avg_response_time:.2f}ms")
        print(f"  P50: {result.p50_response_time:.2f}ms")
        print(f"  P95: {result.p95_response_time:.2f}ms")
        print(f"  P99: {result.p99_response_time:.2f}ms")

        self.results.append(result)
        return result

    async def run_all(self) -> bool:
        """Run all load tests."""
        print("=" * 60)
        print("Flask Backend Load Tests")
        print("=" * 60)
        print(f"Base URL: {self.base_url}")
        print(f"Total Requests per Test: {self.total_requests}")
        print(f"Concurrency: {self.concurrency}")

        # Test health endpoints (should be fast)
        await self.run_load_test("Readiness Check", "GET", "/readyz")
        await self.run_load_test("Liveness Check", "GET", "/livez")
        await self.run_load_test("Status Endpoint", "GET", "/api/v1/status")

        # Test auth endpoints (validation paths)
        await self.run_load_test(
            "Login (Invalid)",
            "POST",
            "/api/v1/auth/login",
            json={"email": "test@test.com", "password": "wrongpassword"},
        )

        # Print summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"{'Endpoint':<40} {'RPS':>10} {'Avg(ms)':>10} {'P95(ms)':>10}")
        print("-" * 70)

        all_passed = True
        for result in self.results:
            print(
                f"{result.endpoint:<40} "
                f"{result.requests_per_second:>10.1f} "
                f"{result.avg_response_time:>10.2f} "
                f"{result.p95_response_time:>10.2f}"
            )
            # Fail if success rate is below 95%
            if result.success_rate < 95:
                all_passed = False
                print(f"  ⚠ Warning: Success rate {result.success_rate:.1f}% < 95%")

        print("-" * 70)

        # Performance thresholds
        print("\nPerformance Thresholds:")
        thresholds_met = True

        for result in self.results:
            # Health endpoints should respond in < 100ms avg
            if "/readyz" in result.endpoint or "/livez" in result.endpoint:
                if result.avg_response_time > 100:
                    print(
                        f"  ✗ {result.endpoint}: Avg {result.avg_response_time:.0f}ms > 100ms threshold"
                    )
                    thresholds_met = False
                else:
                    print(
                        f"  ✓ {result.endpoint}: Avg {result.avg_response_time:.0f}ms < 100ms"
                    )

            # API endpoints should respond in < 500ms avg
            elif "/api/" in result.endpoint:
                if result.avg_response_time > 500:
                    print(
                        f"  ✗ {result.endpoint}: Avg {result.avg_response_time:.0f}ms > 500ms threshold"
                    )
                    thresholds_met = False
                else:
                    print(
                        f"  ✓ {result.endpoint}: Avg {result.avg_response_time:.0f}ms < 500ms"
                    )

        return all_passed and thresholds_met


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Flask Backend Load Tests")
    parser.add_argument(
        "--requests", "-r", type=int, default=100, help="Total requests per test"
    )
    parser.add_argument(
        "--concurrency", "-c", type=int, default=10, help="Concurrent requests"
    )
    args = parser.parse_args()

    base_url = os.getenv("BASE_URL", "")
    if not base_url:
        print("ERROR: BASE_URL environment variable required")
        print("Usage: BASE_URL=http://localhost:5000 python test_load.py")
        sys.exit(1)

    # Check if httpx is installed
    try:
        import httpx
    except ImportError:
        print("ERROR: httpx package required for load testing")
        print("Install with: pip install httpx")
        sys.exit(1)

    tester = LoadTester(
        base_url=base_url,
        requests=args.requests,
        concurrency=args.concurrency,
    )

    success = await tester.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
