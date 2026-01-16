"""Pytest configuration and fixtures for Quart backend tests."""

from __future__ import annotations

import os
import sys

import pytest
import pytest_asyncio

# Set testing environment
os.environ["FLASK_ENV"] = "testing"
os.environ["DB_TYPE"] = "sqlite"
os.environ["DB_NAME"] = ":memory:"

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest_asyncio.fixture
async def app():
    """Create test application."""
    from app import create_app
    from app.config import TestingConfig

    app = create_app(TestingConfig)
    yield app


@pytest_asyncio.fixture
async def client(app):
    """Create test client."""
    async with app.test_client() as client:
        yield client


@pytest.fixture
def auth_headers():
    """Helper to create auth headers with a token."""
    def _auth_headers(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}
    return _auth_headers
