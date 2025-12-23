"""PyDAL Database Models."""

from datetime import datetime
from typing import Optional

from flask import Flask, g
from pydal import DAL, Field
from pydal.validators import (
    IS_EMAIL,
    IS_IN_SET,
    IS_LENGTH,
    IS_MATCH,
    IS_NOT_EMPTY,
    IS_URL,
)

from .config import Config

# Valid roles for the application
VALID_ROLES = ["admin", "maintainer", "viewer"]

# Valid team roles
VALID_TEAM_ROLES = ["owner", "admin", "member", "viewer"]

# Valid plan tiers
VALID_PLANS = ["free", "pro", "enterprise"]

# Plan limits for domains
PLAN_DOMAIN_LIMITS = {
    "free": 1,
    "pro": 5,
    "enterprise": 999,  # Effectively unlimited
}


def init_db(app: Flask) -> DAL:
    """Initialize database connection and define tables."""
    db_uri = Config.get_db_uri()

    db = DAL(
        db_uri,
        pool_size=Config.DB_POOL_SIZE,
        migrate=True,
        check_reserved=["all"],
        lazy_tables=False,
    )

    # Define users table
    db.define_table(
        "users",
        Field("email", "string", length=255, unique=True, requires=[
            IS_NOT_EMPTY(error_message="Email is required"),
            IS_EMAIL(error_message="Invalid email format"),
        ]),
        Field("password_hash", "string", length=255, requires=IS_NOT_EMPTY()),
        Field("full_name", "string", length=255),
        Field("role", "string", length=50, default="viewer", requires=IS_IN_SET(
            VALID_ROLES,
            error_message=f"Role must be one of: {', '.join(VALID_ROLES)}"
        )),
        Field("is_active", "boolean", default=True),
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", default=datetime.utcnow, update=datetime.utcnow),
    )

    # Define refresh tokens table for token invalidation
    db.define_table(
        "refresh_tokens",
        Field("user_id", "reference users", requires=IS_NOT_EMPTY()),
        Field("token_hash", "string", length=255, unique=True),
        Field("expires_at", "datetime"),
        Field("revoked", "boolean", default=False),
        Field("created_at", "datetime", default=datetime.utcnow),
    )

    # =========================================================================
    # URL Shortener Tables
    # =========================================================================

    # Domains - Short domain registry (e.g., "short.io", "link.co")
    db.define_table(
        "domains",
        Field("domain", "string", length=255, unique=True, requires=[
            IS_NOT_EMPTY(error_message="Domain is required"),
            IS_MATCH(r"^[a-zA-Z0-9][a-zA-Z0-9\-\.]*\.[a-zA-Z]{2,}$",
                     error_message="Invalid domain format"),
        ]),
        Field("is_primary", "boolean", default=False),
        Field("is_active", "boolean", default=True),
        Field("ssl_enabled", "boolean", default=True),
        Field("verification_code", "string", length=64),
        Field("verified_at", "datetime"),
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", default=datetime.utcnow, update=datetime.utcnow),
    )

    # Teams - Workspaces/organizations for URL management
    db.define_table(
        "teams",
        Field("name", "string", length=255, requires=IS_NOT_EMPTY()),
        Field("slug", "string", length=100, unique=True, requires=[
            IS_NOT_EMPTY(),
            IS_MATCH(r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$|^[a-z0-9]$",
                     error_message="Slug must be lowercase alphanumeric with hyphens"),
        ]),
        Field("description", "text"),
        Field("plan", "string", length=50, default="free", requires=IS_IN_SET(
            VALID_PLANS, error_message=f"Plan must be one of: {', '.join(VALID_PLANS)}"
        )),
        Field("owner_id", "reference users", requires=IS_NOT_EMPTY()),
        Field("max_domains", "integer", default=1),
        Field("max_urls_per_month", "integer", default=100),
        Field("is_active", "boolean", default=True),
        Field("settings", "json"),
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", default=datetime.utcnow, update=datetime.utcnow),
    )

    # Team members - Many-to-many relationship with roles
    db.define_table(
        "team_members",
        Field("team_id", "reference teams", requires=IS_NOT_EMPTY()),
        Field("user_id", "reference users", requires=IS_NOT_EMPTY()),
        Field("role", "string", length=50, default="member", requires=IS_IN_SET(
            VALID_TEAM_ROLES,
            error_message=f"Role must be one of: {', '.join(VALID_TEAM_ROLES)}"
        )),
        Field("invited_by", "reference users"),
        Field("joined_at", "datetime", default=datetime.utcnow),
    )

    # Team domains - Domains assigned to teams
    db.define_table(
        "team_domains",
        Field("team_id", "reference teams", requires=IS_NOT_EMPTY()),
        Field("domain_id", "reference domains", requires=IS_NOT_EMPTY()),
        Field("is_default", "boolean", default=False),
        Field("created_at", "datetime", default=datetime.utcnow),
    )

    # Collections - Folders for organizing URLs within teams
    db.define_table(
        "collections",
        Field("team_id", "reference teams", requires=IS_NOT_EMPTY()),
        Field("name", "string", length=255, requires=IS_NOT_EMPTY()),
        Field("slug", "string", length=100, requires=[
            IS_NOT_EMPTY(),
            IS_MATCH(r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$|^[a-z0-9]$",
                     error_message="Slug must be lowercase alphanumeric with hyphens"),
        ]),
        Field("description", "text"),
        Field("color", "string", length=7, default="#6366f1"),  # Hex color
        Field("icon", "string", length=50),  # Emoji or icon class
        Field("parent_id", "reference collections"),  # For nested folders
        Field("is_active", "boolean", default=True),
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", default=datetime.utcnow, update=datetime.utcnow),
    )

    # Short URLs - Core URL entity
    db.define_table(
        "short_urls",
        Field("domain_id", "reference domains", requires=IS_NOT_EMPTY()),
        Field("team_id", "reference teams", requires=IS_NOT_EMPTY()),
        Field("collection_id", "reference collections"),  # Optional
        Field("created_by", "reference users", requires=IS_NOT_EMPTY()),
        Field("slug", "string", length=50, requires=[
            IS_NOT_EMPTY(),
            IS_LENGTH(50, 1, error_message="Slug must be 1-50 characters"),
        ]),
        Field("original_url", "text", requires=[
            IS_NOT_EMPTY(error_message="Original URL is required"),
            IS_URL(error_message="Invalid URL format"),
        ]),
        Field("title", "string", length=500),
        Field("description", "text"),
        Field("tags", "list:string"),
        Field("password", "string", length=255),  # Bcrypt hash if protected
        Field("expires_at", "datetime"),
        Field("max_clicks", "integer"),
        Field("click_count", "integer", default=0),
        Field("is_active", "boolean", default=True),
        Field("archived", "boolean", default=False),
        # Device-specific redirects
        Field("ios_url", "text"),
        Field("android_url", "text"),
        # UTM parameters
        Field("utm_source", "string", length=100),
        Field("utm_medium", "string", length=100),
        Field("utm_campaign", "string", length=100),
        # Open Graph overrides
        Field("og_title", "string", length=255),
        Field("og_description", "text"),
        Field("og_image", "string", length=500),
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", default=datetime.utcnow, update=datetime.utcnow),
    )

    # Click events - Raw click data for analytics
    db.define_table(
        "click_events",
        Field("short_url_id", "reference short_urls", requires=IS_NOT_EMPTY()),
        Field("clicked_at", "datetime", default=datetime.utcnow),
        Field("ip_hash", "string", length=64),  # SHA256 for privacy
        Field("country", "string", length=2),  # ISO 3166-1 alpha-2
        Field("region", "string", length=100),
        Field("city", "string", length=100),
        Field("device_type", "string", length=20),  # mobile, tablet, desktop
        Field("browser", "string", length=50),
        Field("browser_version", "string", length=20),
        Field("os", "string", length=50),
        Field("os_version", "string", length=20),
        Field("referrer", "string", length=500),
        Field("referrer_domain", "string", length=255),
        Field("is_unique", "boolean", default=True),
        Field("is_bot", "boolean", default=False),
    )

    # Daily stats - Aggregated statistics for dashboard performance
    db.define_table(
        "daily_stats",
        Field("short_url_id", "reference short_urls", requires=IS_NOT_EMPTY()),
        Field("date", "date", requires=IS_NOT_EMPTY()),
        Field("clicks", "integer", default=0),
        Field("unique_clicks", "integer", default=0),
        Field("by_country", "json"),  # {"US": 100, "UK": 50}
        Field("by_device", "json"),   # {"mobile": 80, "desktop": 70}
        Field("by_browser", "json"),  # {"Chrome": 100, "Firefox": 30}
        Field("by_referrer", "json"), # {"google.com": 50, "twitter.com": 20}
    )

    # QR codes - QR code configuration storage
    db.define_table(
        "qr_codes",
        Field("short_url_id", "reference short_urls", unique=True,
              requires=IS_NOT_EMPTY()),
        Field("foreground_color", "string", length=7, default="#000000"),
        Field("background_color", "string", length=7, default="#FFFFFF"),
        Field("logo_url", "string", length=500),
        Field("logo_size", "integer", default=30),  # Percentage 10-50
        Field("error_correction", "string", length=1, default="M",
              requires=IS_IN_SET(["L", "M", "Q", "H"])),
        Field("style", "string", length=20, default="square",
              requires=IS_IN_SET(["square", "rounded", "dots"])),
        Field("frame_style", "string", length=20),
        Field("frame_text", "string", length=50),
        Field("created_at", "datetime", default=datetime.utcnow),
        Field("updated_at", "datetime", default=datetime.utcnow, update=datetime.utcnow),
    )

    # Commit table definitions
    db.commit()

    # Store db instance in app
    app.config["db"] = db

    return db


def get_db() -> DAL:
    """Get database connection for current request context."""
    from flask import current_app

    if "db" not in g:
        g.db = current_app.config.get("db")
    return g.db


def get_user_by_email(email: str) -> Optional[dict]:
    """Get user by email address."""
    db = get_db()
    user = db(db.users.email == email).select().first()
    return user.as_dict() if user else None


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Get user by ID."""
    db = get_db()
    user = db(db.users.id == user_id).select().first()
    return user.as_dict() if user else None


def create_user(email: str, password_hash: str, full_name: str = "",
                role: str = "viewer") -> dict:
    """Create a new user."""
    db = get_db()
    user_id = db.users.insert(
        email=email,
        password_hash=password_hash,
        full_name=full_name,
        role=role,
        is_active=True,
    )
    db.commit()
    return get_user_by_id(user_id)


def update_user(user_id: int, **kwargs) -> Optional[dict]:
    """Update user by ID."""
    db = get_db()

    # Filter allowed fields
    allowed_fields = {"email", "password_hash", "full_name", "role", "is_active"}
    update_data = {k: v for k, v in kwargs.items() if k in allowed_fields}

    if not update_data:
        return get_user_by_id(user_id)

    db(db.users.id == user_id).update(**update_data)
    db.commit()
    return get_user_by_id(user_id)


def delete_user(user_id: int) -> bool:
    """Delete user by ID."""
    db = get_db()
    deleted = db(db.users.id == user_id).delete()
    db.commit()
    return deleted > 0


def list_users(page: int = 1, per_page: int = 20) -> tuple[list[dict], int]:
    """List users with pagination."""
    db = get_db()
    offset = (page - 1) * per_page

    users = db(db.users).select(
        orderby=db.users.created_at,
        limitby=(offset, offset + per_page),
    )
    total = db(db.users).count()

    return [u.as_dict() for u in users], total


def store_refresh_token(user_id: int, token_hash: str, expires_at: datetime) -> int:
    """Store a refresh token."""
    db = get_db()
    token_id = db.refresh_tokens.insert(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.commit()
    return token_id


def revoke_refresh_token(token_hash: str) -> bool:
    """Revoke a refresh token."""
    db = get_db()
    updated = db(db.refresh_tokens.token_hash == token_hash).update(revoked=True)
    db.commit()
    return updated > 0


def is_refresh_token_valid(token_hash: str) -> bool:
    """Check if refresh token is valid (not revoked and not expired)."""
    db = get_db()
    token = db(
        (db.refresh_tokens.token_hash == token_hash) &
        (db.refresh_tokens.revoked == False) &
        (db.refresh_tokens.expires_at > datetime.utcnow())
    ).select().first()
    return token is not None


def revoke_all_user_tokens(user_id: int) -> int:
    """Revoke all refresh tokens for a user."""
    db = get_db()
    updated = db(db.refresh_tokens.user_id == user_id).update(revoked=True)
    db.commit()
    return updated
