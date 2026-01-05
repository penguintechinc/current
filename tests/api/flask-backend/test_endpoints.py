#!/usr/bin/env python3
"""
Flask Backend API Endpoint Tests.

Tests all API endpoints using the Quart test client.
Can also run against a live server if BASE_URL is set.

Usage:
    python test_endpoints.py              # Use test client
    BASE_URL=http://localhost:5000 python test_endpoints.py  # Live server
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from typing import Any

# Set testing environment BEFORE importing app
os.environ["FLASK_ENV"] = "testing"
os.environ["DB_TYPE"] = "sqlite"
os.environ["DB_NAME"] = ":memory:"

# Add service to path
SERVICE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "services", "flask-backend"
)
sys.path.insert(0, SERVICE_DIR)


@dataclass
class TestResult:
    """Test result container."""

    name: str
    passed: bool
    message: str = ""
    response_code: int = 0


class APITester:
    """API endpoint tester."""

    def __init__(self):
        self.results: list[TestResult] = []
        self.base_url = os.getenv("BASE_URL", "")
        self.client = None
        self.app = None
        self.access_token = None
        self.refresh_token = None

    async def setup(self):
        """Initialize test client or HTTP client."""
        if self.base_url:
            # Use httpx for live server testing
            import httpx

            self.client = httpx.AsyncClient(base_url=self.base_url)
        else:
            # Use Quart test client
            from app import create_app
            from app.config import TestingConfig

            self.app = create_app(TestingConfig)
            self.client = self.app.test_client()

    async def teardown(self):
        """Cleanup."""
        if self.base_url and self.client:
            await self.client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        json: dict | None = None,
        headers: dict | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Make HTTP request."""
        headers = headers or {}

        if self.base_url:
            # httpx client
            response = await self.client.request(
                method, path, json=json, headers=headers
            )
            try:
                data = response.json()
            except Exception:
                data = {"raw": response.text}
            return response.status_code, data
        else:
            # Quart test client
            async with self.client as client:
                if method.upper() == "GET":
                    response = await client.get(path, headers=headers)
                elif method.upper() == "POST":
                    response = await client.post(path, json=json, headers=headers)
                elif method.upper() == "PUT":
                    response = await client.put(path, json=json, headers=headers)
                elif method.upper() == "DELETE":
                    response = await client.delete(path, headers=headers)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                try:
                    data = await response.get_json()
                except Exception:
                    data = {"raw": await response.get_data(as_text=True)}
                return response.status_code, data

    def record(self, name: str, passed: bool, message: str = "", code: int = 0):
        """Record test result."""
        self.results.append(TestResult(name, passed, message, code))
        status = "✓" if passed else "✗"
        print(f"  {status} {name}: {message}")

    # Health Endpoint Tests

    async def test_readiness(self):
        """Test /readyz endpoint."""
        code, data = await self.request("GET", "/readyz")
        self.record(
            "GET /readyz",
            code == 200 and data.get("status") == "ready",
            f"status={code}",
            code,
        )

    async def test_liveness(self):
        """Test /livez endpoint."""
        code, data = await self.request("GET", "/livez")
        self.record(
            "GET /livez",
            code == 200 and data.get("status") == "alive",
            f"status={code}",
            code,
        )

    async def test_status(self):
        """Test /api/v1/status endpoint."""
        code, data = await self.request("GET", "/api/v1/status")
        self.record(
            "GET /api/v1/status",
            code == 200 and "status" in data,
            f"status={code}",
            code,
        )

    # Auth Endpoint Tests

    async def test_login_missing_body(self):
        """Test login with missing body."""
        code, data = await self.request("POST", "/api/v1/auth/login")
        self.record(
            "POST /api/v1/auth/login (no body)",
            code == 400 and "error" in data,
            f"status={code}",
            code,
        )

    async def test_login_invalid_email(self):
        """Test login with invalid email."""
        code, data = await self.request(
            "POST",
            "/api/v1/auth/login",
            json={"email": "invalid", "password": "test"},
        )
        self.record(
            "POST /api/v1/auth/login (invalid email)",
            code == 400 and "error" in data,
            f"status={code}",
            code,
        )

    async def test_login_user_not_found(self):
        """Test login with non-existent user."""
        code, data = await self.request(
            "POST",
            "/api/v1/auth/login",
            json={"email": "nonexistent@test.com", "password": "testpassword123"},
        )
        self.record(
            "POST /api/v1/auth/login (user not found)",
            code == 401 and "error" in data,
            f"status={code}",
            code,
        )

    async def test_register_missing_body(self):
        """Test register with missing body."""
        code, data = await self.request("POST", "/api/v1/auth/register")
        self.record(
            "POST /api/v1/auth/register (no body)",
            code == 400 and "error" in data,
            f"status={code}",
            code,
        )

    async def test_register_password_too_short(self):
        """Test register with short password."""
        code, data = await self.request(
            "POST",
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "short"},
        )
        self.record(
            "POST /api/v1/auth/register (short password)",
            code == 400 and "error" in data,
            f"status={code}",
            code,
        )

    async def test_me_unauthenticated(self):
        """Test /me without authentication."""
        code, data = await self.request("GET", "/api/v1/auth/me")
        self.record(
            "GET /api/v1/auth/me (no auth)",
            code == 401 and "error" in data,
            f"status={code}",
            code,
        )

    async def test_logout_unauthenticated(self):
        """Test logout without authentication."""
        code, data = await self.request("POST", "/api/v1/auth/logout")
        self.record(
            "POST /api/v1/auth/logout (no auth)",
            code == 401 and "error" in data,
            f"status={code}",
            code,
        )

    async def test_refresh_missing_token(self):
        """Test refresh with missing token."""
        code, data = await self.request(
            "POST", "/api/v1/auth/refresh", json={"refresh_token": ""}
        )
        self.record(
            "POST /api/v1/auth/refresh (empty token)",
            code == 400 and "error" in data,
            f"status={code}",
            code,
        )

    # User Endpoint Tests

    async def test_users_list_unauthenticated(self):
        """Test users list without authentication."""
        code, data = await self.request("GET", "/api/v1/users")
        self.record(
            "GET /api/v1/users (no auth)",
            code == 401 and "error" in data,
            f"status={code}",
            code,
        )

    async def test_user_create_unauthenticated(self):
        """Test user creation without authentication."""
        code, data = await self.request(
            "POST",
            "/api/v1/users",
            json={
                "email": "newuser@test.com",
                "password": "testpassword123",
                "full_name": "Test User",
            },
        )
        self.record(
            "POST /api/v1/users (no auth)",
            code == 401 and "error" in data,
            f"status={code}",
            code,
        )

    # Error Handling Tests

    async def test_404_not_found(self):
        """Test 404 response for non-existent route."""
        code, data = await self.request("GET", "/api/v1/nonexistent")
        self.record(
            "GET /api/v1/nonexistent (404)",
            code == 404,
            f"status={code}",
            code,
        )

    async def test_method_not_allowed(self):
        """Test 405 response for wrong method."""
        code, data = await self.request("DELETE", "/readyz")
        # Some frameworks return 404 for unmatched methods, others 405
        self.record(
            "DELETE /readyz (method not allowed)",
            code in (404, 405),
            f"status={code}",
            code,
        )

    async def run_all(self):
        """Run all tests."""
        print("\nFlask Backend API Endpoint Tests")
        print("=" * 50)

        if self.base_url:
            print(f"Testing live server: {self.base_url}")
        else:
            print("Using Quart test client")
        print("")

        await self.setup()

        try:
            # Health endpoints
            print("\nHealth Endpoints:")
            await self.test_readiness()
            await self.test_liveness()
            await self.test_status()

            # Auth endpoints
            print("\nAuth Endpoints:")
            await self.test_login_missing_body()
            await self.test_login_invalid_email()
            await self.test_login_user_not_found()
            await self.test_register_missing_body()
            await self.test_register_password_too_short()
            await self.test_me_unauthenticated()
            await self.test_logout_unauthenticated()
            await self.test_refresh_missing_token()

            # User endpoints
            print("\nUser Endpoints:")
            await self.test_users_list_unauthenticated()
            await self.test_user_create_unauthenticated()

            # Error handling
            print("\nError Handling:")
            await self.test_404_not_found()
            await self.test_method_not_allowed()

        finally:
            await self.teardown()

        # Summary
        print("\n" + "=" * 50)
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        print(f"Results: {passed} passed, {failed} failed")

        return failed == 0


async def main():
    """Main entry point."""
    tester = APITester()
    success = await tester.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
