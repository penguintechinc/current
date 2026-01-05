"""Tests for authentication endpoints."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_login_missing_body(client):
    """Test login with no request body."""
    response = await client.post(
        "/api/v1/auth/login",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    data = await response.get_json()
    assert "error" in data


@pytest.mark.asyncio
async def test_login_invalid_email(client):
    """Test login with invalid email format."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "password"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login_user_not_found(client):
    """Test login with non-existent user."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "password123"},
    )
    assert response.status_code == 401
    data = await response.get_json()
    assert "error" in data


@pytest.mark.asyncio
async def test_register_missing_body(client):
    """Test register with no request body."""
    response = await client.post(
        "/api/v1/auth/register",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_register_password_too_short(client):
    """Test register with short password."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "short",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_me_unauthenticated(client):
    """Test /me endpoint without authentication."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_unauthenticated(client):
    """Test logout without authentication."""
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_missing_token(client):
    """Test refresh with missing token."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={},
    )
    assert response.status_code == 400
