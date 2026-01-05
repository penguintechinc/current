"""Tests for health check endpoints."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_readiness_check(client):
    """Test readiness endpoint returns 200."""
    response = await client.get("/readyz")
    assert response.status_code == 200
    data = await response.get_json()
    assert data["status"] == "ready"


@pytest.mark.asyncio
async def test_liveness_check(client):
    """Test liveness endpoint returns 200."""
    response = await client.get("/livez")
    assert response.status_code == 200
    data = await response.get_json()
    assert data["status"] == "alive"


@pytest.mark.asyncio
async def test_status_endpoint(client):
    """Test public status endpoint."""
    response = await client.get("/api/v1/status")
    assert response.status_code == 200
    data = await response.get_json()
    assert data["status"] == "running"
    assert data["service"] == "quart-backend"
