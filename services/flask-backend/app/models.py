"""
PyDAL Database Models for Flask-Security-Too.

Defines database tables compatible with Flask-Security-Too:
- auth_user: User accounts with Flask-Security fields
- auth_role: Role definitions
- auth_user_roles: User-role join table
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydal import DAL, Field
from pydal.validators import IS_EMAIL, IS_IN_SET, IS_NOT_EMPTY
from quart import Quart, g

from .config import Config

# Valid roles for the application
VALID_ROLES = ["admin", "maintainer", "viewer"]

# Role descriptions
ROLE_DESCRIPTIONS = {
    "admin": "Full access: user CRUD, settings, all features",
    "maintainer": "Read/write access to resources, no user management",
    "viewer": "Read-only access to resources",
}


def init_db(app: Quart) -> DAL:
    """
    Initialize database connection and define Flask-Security-Too compatible tables.

    Args:
        app: Quart application instance

    Returns:
        PyDAL database instance
    """
    db_uri = Config.get_db_uri()

    db = DAL(
        db_uri,
        pool_size=Config.DB_POOL_SIZE,
        migrate=False,  # Disable PyDAL migration system
        check_reserved=["all"],
        lazy_tables=True,
    )

    # Create tables if they don't exist
    _create_tables_if_needed(db)

    # Define tables for runtime use (without creating them again)
    db.define_table(
        "auth_user",
        Field("email", "string", length=255),
        Field("password", "string", length=255),
        Field("is_active", "boolean"),
        Field("fs_uniquifier", "string", length=64),
        Field("fs_token_uniquifier", "string", length=64),
        Field("full_name", "string", length=255),
        Field("confirmed_at", "datetime"),
        Field("last_login_at", "datetime"),
        Field("current_login_at", "datetime"),
        Field("last_login_ip", "string", length=45),
        Field("current_login_ip", "string", length=45),
        Field("login_count", "integer"),
        Field("created_at", "datetime"),
        Field("updated_at", "datetime"),
        migrate=False,  # Don't create tables
    )

    db.define_table(
        "auth_role",
        Field("name", "string", length=50),
        Field("description", "text"),
        Field("created_at", "datetime"),
        migrate=False,  # Don't create tables
    )

    db.define_table(
        "auth_user_roles",
        Field("user_id", "reference auth_user"),
        Field("role_id", "reference auth_role"),
        migrate=False,  # Don't create tables
    )

    # Ensure default roles exist
    _ensure_default_roles(db)

    # Initialize RBAC tables and scopes
    from .rbac import init_rbac_tables
    init_rbac_tables(db)

    # Store db instance in app
    app.config["db"] = db

    return db


def _create_tables_if_needed(db: DAL) -> None:
    """Create database tables if they don't already exist using raw SQL."""
    db_type = Config.DB_TYPE.lower()

    # Check if auth_user table exists
    try:
        db.executesql("SELECT 1 FROM auth_user LIMIT 1")
        # Table exists, skip creation
        return
    except Exception:
        # Table doesn't exist, create all tables
        db.commit()  # Clear any failed transaction

    try:
        if "postgres" in db_type:
            # PostgreSQL table definitions
            try:
                db.executesql("""
                    CREATE TABLE auth_user (
                        id SERIAL PRIMARY KEY,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        password VARCHAR(255) NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        fs_uniquifier VARCHAR(64) UNIQUE NOT NULL,
                        fs_token_uniquifier VARCHAR(64) UNIQUE,
                        full_name VARCHAR(255) DEFAULT '',
                        confirmed_at TIMESTAMP,
                        last_login_at TIMESTAMP,
                        current_login_at TIMESTAMP,
                        last_login_ip VARCHAR(45),
                        current_login_ip VARCHAR(45),
                        login_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                db.commit()
            except Exception:
                db.commit()

            try:
                db.executesql("""
                    CREATE TABLE auth_role (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(50) UNIQUE NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                db.commit()
            except Exception:
                db.commit()

            try:
                db.executesql("""
                    CREATE TABLE auth_user_roles (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES auth_user(id),
                        role_id INTEGER NOT NULL REFERENCES auth_role(id),
                        UNIQUE(user_id, role_id)
                    )
                """)
                db.commit()
            except Exception:
                db.commit()
        else:
            # SQLite / MySQL compatible definitions
            try:
                db.executesql("""
                    CREATE TABLE IF NOT EXISTS auth_user (
                        id INTEGER PRIMARY KEY AUTO_INCREMENT,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        password VARCHAR(255) NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        fs_uniquifier VARCHAR(64) UNIQUE NOT NULL,
                        fs_token_uniquifier VARCHAR(64) UNIQUE,
                        full_name VARCHAR(255) DEFAULT '',
                        confirmed_at DATETIME,
                        last_login_at DATETIME,
                        current_login_at DATETIME,
                        last_login_ip VARCHAR(45),
                        current_login_ip VARCHAR(45),
                        login_count INTEGER DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                db.commit()
            except Exception:
                db.commit()

            try:
                db.executesql("""
                    CREATE TABLE IF NOT EXISTS auth_role (
                        id INTEGER PRIMARY KEY AUTO_INCREMENT,
                        name VARCHAR(50) UNIQUE NOT NULL,
                        description TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                db.commit()
            except Exception:
                db.commit()

            try:
                db.executesql("""
                    CREATE TABLE IF NOT EXISTS auth_user_roles (
                        id INTEGER PRIMARY KEY AUTO_INCREMENT,
                        user_id INTEGER NOT NULL REFERENCES auth_user(id),
                        role_id INTEGER NOT NULL REFERENCES auth_role(id),
                        UNIQUE(user_id, role_id)
                    )
                """)
                db.commit()
            except Exception:
                db.commit()
    except Exception as e:
        # Table creation may fail due to existing tables or permission issues
        db.commit()


def _ensure_default_roles(db: DAL) -> None:
    """
    Ensure default roles exist in the database.

    Creates admin, maintainer, and viewer roles if they don't exist.
    Also creates team-level and resource-level roles.
    """
    # Global roles
    for role_name in VALID_ROLES:
        existing = db(db.auth_role.name == role_name).select().first()
        if not existing:
            db.auth_role.insert(
                name=role_name,
                description=ROLE_DESCRIPTIONS.get(role_name, ""),
            )

    # Team-level roles
    team_roles = {
        'team_admin': 'Full access within team',
        'team_maintainer': 'Read/write access within team',
        'team_viewer': 'Read-only access within team',
    }
    for role_name, description in team_roles.items():
        existing = db(db.auth_role.name == role_name).select().first()
        if not existing:
            db.auth_role.insert(name=role_name, description=description)

    # Resource-level roles
    resource_roles = {
        'owner': 'Full control over specific resource',
        'editor': 'Read/write on specific resource',
        'resource_viewer': 'Read-only on specific resource',
    }
    for role_name, description in resource_roles.items():
        existing = db(db.auth_role.name == role_name).select().first()
        if not existing:
            db.auth_role.insert(name=role_name, description=description)

    db.commit()


def get_db() -> DAL:
    """
    Get database connection for current request context.

    Returns:
        PyDAL database instance
    """
    from quart import current_app

    if "db" not in g:
        g.db = current_app.config.get("db")
    return g.db


# Legacy compatibility functions - these now work with auth_user table


def get_user_by_email(email: str) -> Optional[dict]:
    """Get user by email address (legacy compatibility)."""
    db = get_db()
    user = db(db.auth_user.email == email).select().first()
    if user:
        result = user.as_dict()
        # Add legacy field names for backward compatibility
        result["password_hash"] = result.get("password", "")
        result["is_active"] = result.get("active", True)
        result["role"] = _get_primary_role(db, user.id)
        return result
    return None


def get_user_by_id(user_id: int) -> Optional[dict]:
    """Get user by ID (legacy compatibility)."""
    db = get_db()
    user = db(db.auth_user.id == user_id).select().first()
    if user:
        result = user.as_dict()
        result["password_hash"] = result.get("password", "")
        result["is_active"] = result.get("active", True)
        result["role"] = _get_primary_role(db, user.id)
        return result
    return None


def _get_primary_role(db: DAL, user_id: int) -> str:
    """Get primary role for a user (first role assigned)."""
    role_row = (
        db(
            (db.auth_user_roles.user_id == user_id)
            & (db.auth_user_roles.role_id == db.auth_role.id)
        )
        .select(db.auth_role.name)
        .first()
    )
    return role_row.name if role_row else "viewer"


def create_user(
    email: str,
    password_hash: str,
    full_name: str = "",
    role: str = "viewer",
) -> dict:
    """
    Create a new user (legacy compatibility).

    Note: password_hash parameter is stored in 'password' field
    for Flask-Security compatibility.
    """
    import uuid

    db = get_db()

    # Insert user with Flask-Security required fields
    user_id = db.auth_user.insert(
        email=email,
        password=password_hash,  # Flask-Security uses 'password' not 'password_hash'
        full_name=full_name,
        is_active=True,
        fs_uniquifier=str(uuid.uuid4()),
        fs_token_uniquifier=str(uuid.uuid4()),
    )

    # Assign role (legacy table for Flask-Security compatibility)
    role_row = db(db.auth_role.name == role).select().first()
    if role_row:
        db.auth_user_roles.insert(user_id=user_id, role_id=role_row.id)

        # Also assign role at global level in new RBAC system
        # Define user_role_assignments table if not already defined
        if 'user_role_assignments' not in db.tables:
            db.define_table(
                'user_role_assignments',
                db.Field('user_id', 'reference auth_user'),
                db.Field('role_id', 'reference auth_role'),
                db.Field('scope_level', 'string', length=20),
                db.Field('scope_id', 'integer'),
                db.Field('created_at', 'datetime'),
                migrate=False,
            )

        # Assign global-level role
        db.user_role_assignments.insert(
            user_id=user_id,
            role_id=role_row.id,
            scope_level='global',
            scope_id=None,
        )

    db.commit()
    return get_user_by_id(user_id)


def update_user(user_id: int, **kwargs) -> Optional[dict]:
    """Update user by ID (legacy compatibility)."""
    db = get_db()

    # Map legacy field names to new schema
    field_mapping = {
        "password_hash": "password",
    }

    update_data = {}
    role_update = None

    for key, value in kwargs.items():
        # Handle field name mapping
        actual_key = field_mapping.get(key, key)

        # Handle role separately
        if key == "role":
            role_update = value
            continue

        # Only update allowed fields
        allowed_fields = {"email", "password", "full_name", "is_active"}
        if actual_key in allowed_fields:
            update_data[actual_key] = value

    if update_data:
        db(db.auth_user.id == user_id).update(**update_data)

    # Update role if provided
    if role_update:
        # Remove existing roles
        db(db.auth_user_roles.user_id == user_id).delete()
        # Add new role
        role_row = db(db.auth_role.name == role_update).select().first()
        if role_row:
            db.auth_user_roles.insert(user_id=user_id, role_id=role_row.id)

    db.commit()
    return get_user_by_id(user_id)


def delete_user(user_id: int) -> bool:
    """Delete user by ID (legacy compatibility)."""
    db = get_db()

    # Delete role assignments first
    db(db.auth_user_roles.user_id == user_id).delete()

    # Delete user
    deleted = db(db.auth_user.id == user_id).delete()
    db.commit()
    return deleted > 0


def list_users(page: int = 1, per_page: int = 20) -> tuple[list[dict], int]:
    """List users with pagination (legacy compatibility)."""
    db = get_db()
    offset = (page - 1) * per_page

    users = db(db.auth_user).select(
        orderby=db.auth_user.created_at,
        limitby=(offset, offset + per_page),
    )
    total = db(db.auth_user).count()

    result = []
    for user in users:
        user_dict = user.as_dict()
        user_dict["password_hash"] = user_dict.get("password", "")
        user_dict["is_active"] = user_dict.get("active", True)
        user_dict["role"] = _get_primary_role(db, user.id)
        result.append(user_dict)

    return result, total


# Refresh token functions (unchanged, but using new table naming convention)


def store_refresh_token(user_id: int, token_hash: str, expires_at: datetime) -> int:
    """Store a refresh token."""
    db = get_db()

    # Ensure refresh_tokens table exists
    if "refresh_tokens" not in db.tables:
        db.define_table(
            "refresh_tokens",
            Field("user_id", "reference auth_user", requires=IS_NOT_EMPTY()),
            Field("token_hash", "string", length=255, unique=True),
            Field("expires_at", "datetime"),
            Field("revoked", "boolean", default=False),
            Field("created_at", "datetime", default=datetime.utcnow),
        )
        db.commit()

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
    if "refresh_tokens" not in db.tables:
        return False
    updated = db(db.refresh_tokens.token_hash == token_hash).update(revoked=True)
    db.commit()
    return updated > 0


def is_refresh_token_valid(token_hash: str) -> bool:
    """Check if refresh token is valid (not revoked and not expired)."""
    db = get_db()
    if "refresh_tokens" not in db.tables:
        return False
    token = db(
        (db.refresh_tokens.token_hash == token_hash)
        & (db.refresh_tokens.revoked == False)  # noqa: E712
        & (db.refresh_tokens.expires_at > datetime.utcnow())
    ).select().first()
    return token is not None


def revoke_all_user_tokens(user_id: int) -> int:
    """Revoke all refresh tokens for a user."""
    db = get_db()
    if "refresh_tokens" not in db.tables:
        return 0
    updated = db(db.refresh_tokens.user_id == user_id).update(revoked=True)
    db.commit()
    return updated
