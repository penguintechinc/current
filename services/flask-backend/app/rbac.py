"""
Role-Based Access Control (RBAC) with OAuth2-Style Scopes.

Implements 3-tier permission system:
- Global: Organization-wide roles
- Team: Per-team access
- Resource: Per-resource permissions

All permissions are scope-based (e.g., users:read, users:write, analytics:admin).
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Optional

from quart import request, g
from werkzeug.exceptions import Forbidden

# OAuth2-style scope definitions
SCOPES = {
    # User management scopes
    "users:read": "Read user data",
    "users:write": "Create and update users",
    "users:admin": "Delete users and manage roles",
    # Team management scopes
    "teams:read": "Read team data",
    "teams:write": "Create and update teams",
    "teams:admin": "Delete teams and manage members",
    # URL management scopes
    "urls:read": "Read URL data",
    "urls:write": "Create and update URLs",
    "urls:delete": "Delete URLs",
    "urls:admin": "Manage all URLs",
    # Analytics scopes
    "analytics:read": "Read analytics data",
    "analytics:admin": "Configure analytics settings",
    # Settings scopes
    "settings:read": "Read application settings",
    "settings:write": "Modify application settings",
    # System scopes
    "system:admin": "Full system administration",
}

# Default role to scope mappings (Global level)
ROLE_SCOPES = {
    "admin": [
        # Full access to everything
        "users:read",
        "users:write",
        "users:admin",
        "teams:read",
        "teams:write",
        "teams:admin",
        "urls:read",
        "urls:write",
        "urls:delete",
        "urls:admin",
        "analytics:read",
        "analytics:admin",
        "settings:read",
        "settings:write",
        "system:admin",
    ],
    "maintainer": [
        # Read/write access, no admin permissions
        "users:read",
        "teams:read",
        "urls:read",
        "urls:write",
        "urls:delete",
        "analytics:read",
        "settings:read",
    ],
    "viewer": [
        # Read-only access
        "users:read",
        "teams:read",
        "urls:read",
        "analytics:read",
        "settings:read",
    ],
}

# Team-level role scopes (scoped to specific team)
TEAM_ROLE_SCOPES = {
    "team_admin": [
        "users:read",
        "users:write",
        "teams:read",
        "teams:write",
        "urls:read",
        "urls:write",
        "urls:delete",
        "analytics:read",
    ],
    "team_maintainer": [
        "users:read",
        "teams:read",
        "urls:read",
        "urls:write",
        "analytics:read",
    ],
    "team_viewer": [
        "users:read",
        "teams:read",
        "urls:read",
        "analytics:read",
    ],
}

# Resource-level role scopes (scoped to specific resource)
RESOURCE_ROLE_SCOPES = {
    "owner": [
        "urls:read",
        "urls:write",
        "urls:delete",
        "analytics:read",
    ],
    "editor": [
        "urls:read",
        "urls:write",
        "analytics:read",
    ],
    "viewer": [
        "urls:read",
        "analytics:read",
    ],
}


def init_rbac_tables(db) -> None:
    """Initialize RBAC tables in the database."""
    db_type = db._uri.split(":")[0].lower()

    # Check if scopes table exists
    try:
        db.executesql("SELECT 1 FROM scopes LIMIT 1")
        return  # Tables already exist
    except Exception:
        db.commit()

    # Create tables based on DB type
    if "postgres" in db_type:
        _create_postgres_rbac_tables(db)
    else:
        _create_mysql_rbac_tables(db)

    # Initialize default scopes
    _initialize_scopes(db)


def _create_postgres_rbac_tables(db) -> None:
    """Create RBAC tables for PostgreSQL."""
    tables = [
        # Scopes table
        """
        CREATE TABLE IF NOT EXISTS scopes (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        # Teams table
        """
        CREATE TABLE IF NOT EXISTS teams (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            created_by INTEGER REFERENCES auth_user(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        # Team members junction table
        """
        CREATE TABLE IF NOT EXISTS team_members (
            id SERIAL PRIMARY KEY,
            team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(team_id, user_id)
        )
        """,
        # Role scopes mapping (which scopes each role has)
        """
        CREATE TABLE IF NOT EXISTS role_scopes (
            id SERIAL PRIMARY KEY,
            role_id INTEGER NOT NULL REFERENCES auth_role(id) ON DELETE CASCADE,
            scope_id INTEGER NOT NULL REFERENCES scopes(id) ON DELETE CASCADE,
            UNIQUE(role_id, scope_id)
        )
        """,
        # User role assignments with 3-tier scope
        """
        CREATE TABLE IF NOT EXISTS user_role_assignments (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
            role_id INTEGER NOT NULL REFERENCES auth_role(id) ON DELETE CASCADE,
            scope_level VARCHAR(20) NOT NULL CHECK (scope_level IN ('global', 'team', 'resource')),
            scope_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        # Custom roles table
        """
        CREATE TABLE IF NOT EXISTS custom_roles (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            description TEXT,
            created_by INTEGER REFERENCES auth_user(id),
            scope_level VARCHAR(20) NOT NULL CHECK (scope_level IN ('global', 'team', 'resource')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
    ]

    for sql in tables:
        try:
            db.executesql(sql)
            db.commit()
        except Exception:
            db.commit()


def _create_mysql_rbac_tables(db) -> None:
    """Create RBAC tables for MySQL/SQLite."""
    tables = [
        """
        CREATE TABLE IF NOT EXISTS scopes (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(100) UNIQUE NOT NULL,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            created_by INTEGER REFERENCES auth_user(id),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS team_members (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            team_id INTEGER NOT NULL REFERENCES teams(id),
            user_id INTEGER NOT NULL REFERENCES auth_user(id),
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(team_id, user_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS role_scopes (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            role_id INTEGER NOT NULL REFERENCES auth_role(id),
            scope_id INTEGER NOT NULL REFERENCES scopes(id),
            UNIQUE(role_id, scope_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS user_role_assignments (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            user_id INTEGER NOT NULL REFERENCES auth_user(id),
            role_id INTEGER NOT NULL REFERENCES auth_role(id),
            scope_level VARCHAR(20) NOT NULL,
            scope_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS custom_roles (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(100) UNIQUE NOT NULL,
            description TEXT,
            created_by INTEGER REFERENCES auth_user(id),
            scope_level VARCHAR(20) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """,
    ]

    for sql in tables:
        try:
            db.executesql(sql)
            db.commit()
        except Exception:
            db.commit()


def _initialize_scopes(db) -> None:
    """Initialize all scopes in the database."""
    # Define scopes table for runtime
    db.define_table(
        "scopes",
        db.Field("name", "string", length=100),
        db.Field("description", "text"),
        db.Field("created_at", "datetime"),
        migrate=False,
    )

    # Insert all scopes
    for scope_name, scope_desc in SCOPES.items():
        existing = db(db.scopes.name == scope_name).select().first()
        if not existing:
            db.scopes.insert(name=scope_name, description=scope_desc)
    db.commit()

    # Initialize role-scope mappings
    _initialize_role_scope_mappings(db)


def _initialize_role_scope_mappings(db) -> None:
    """Initialize default role-to-scope mappings."""
    # Define required tables for runtime
    _define_rbac_tables(db)

    # Map global roles to their scopes
    for role_name, scope_names in ROLE_SCOPES.items():
        role = db(db.auth_role.name == role_name).select().first()
        if not role:
            continue

        for scope_name in scope_names:
            scope = db(db.scopes.name == scope_name).select().first()
            if not scope:
                continue

            # Check if mapping exists
            existing = (
                db(
                    (db.role_scopes.role_id == role.id)
                    & (db.role_scopes.scope_id == scope.id)
                )
                .select()
                .first()
            )

            if not existing:
                db.role_scopes.insert(role_id=role.id, scope_id=scope.id)

    # Map team roles to their scopes
    for role_name, scope_names in TEAM_ROLE_SCOPES.items():
        role = db(db.auth_role.name == role_name).select().first()
        if not role:
            continue

        for scope_name in scope_names:
            scope = db(db.scopes.name == scope_name).select().first()
            if not scope:
                continue

            existing = (
                db(
                    (db.role_scopes.role_id == role.id)
                    & (db.role_scopes.scope_id == scope.id)
                )
                .select()
                .first()
            )

            if not existing:
                db.role_scopes.insert(role_id=role.id, scope_id=scope.id)

    # Map resource roles to their scopes
    for role_name, scope_names in RESOURCE_ROLE_SCOPES.items():
        role = db(db.auth_role.name == role_name).select().first()
        if not role:
            continue

        for scope_name in scope_names:
            scope = db(db.scopes.name == scope_name).select().first()
            if not scope:
                continue

            existing = (
                db(
                    (db.role_scopes.role_id == role.id)
                    & (db.role_scopes.scope_id == scope.id)
                )
                .select()
                .first()
            )

            if not existing:
                db.role_scopes.insert(role_id=role.id, scope_id=scope.id)

    db.commit()


def get_user_scopes(
    user_id: int, team_id: Optional[int] = None, resource_id: Optional[int] = None
) -> list[str]:
    """
    Get all scopes for a user at the specified level.

    Args:
        user_id: User ID
        team_id: Optional team ID to check team-level permissions
        resource_id: Optional resource ID to check resource-level permissions

    Returns:
        List of scope names (e.g., ['users:read', 'users:write'])
    """
    from .models import get_db

    db = get_db()

    # Define tables for runtime
    _define_rbac_tables(db)

    all_scopes = set()

    # 1. Get global-level scopes
    global_assignments = db(
        (db.user_role_assignments.user_id == user_id)
        & (db.user_role_assignments.scope_level == "global")
    ).select()

    for assignment in global_assignments:
        role_scopes = db(
            (db.role_scopes.role_id == assignment.role_id)
            & (db.role_scopes.scope_id == db.scopes.id)
        ).select(db.scopes.name)
        all_scopes.update(rs.name for rs in role_scopes)

    # 2. Get team-level scopes if team_id provided
    if team_id:
        team_assignments = db(
            (db.user_role_assignments.user_id == user_id)
            & (db.user_role_assignments.scope_level == "team")
            & (db.user_role_assignments.scope_id == team_id)
        ).select()

        for assignment in team_assignments:
            role_scopes = db(
                (db.role_scopes.role_id == assignment.role_id)
                & (db.role_scopes.scope_id == db.scopes.id)
            ).select(db.scopes.name)
            all_scopes.update(rs.name for rs in role_scopes)

    # 3. Get resource-level scopes if resource_id provided
    if resource_id:
        resource_assignments = db(
            (db.user_role_assignments.user_id == user_id)
            & (db.user_role_assignments.scope_level == "resource")
            & (db.user_role_assignments.scope_id == resource_id)
        ).select()

        for assignment in resource_assignments:
            role_scopes = db(
                (db.role_scopes.role_id == assignment.role_id)
                & (db.role_scopes.scope_id == db.scopes.id)
            ).select(db.scopes.name)
            all_scopes.update(rs.name for rs in role_scopes)

    return list(all_scopes)


def has_scope(
    user_id: int,
    required_scope: str,
    team_id: Optional[int] = None,
    resource_id: Optional[int] = None,
) -> bool:
    """
    Check if user has the required scope.

    Args:
        user_id: User ID
        required_scope: Scope to check (e.g., 'users:write')
        team_id: Optional team context
        resource_id: Optional resource context

    Returns:
        True if user has the scope
    """
    user_scopes = get_user_scopes(user_id, team_id, resource_id)
    return required_scope in user_scopes


def require_scope(
    *required_scopes: str,
    team_id_param: Optional[str] = None,
    resource_id_param: Optional[str] = None,
):
    """
    Decorator to require specific scopes for an endpoint.

    Args:
        *required_scopes: One or more required scopes (user needs at least one)
        team_id_param: Name of route parameter containing team_id (e.g., 'team_id')
        resource_id_param: Name of route parameter containing resource_id (e.g., 'url_id')

    Example:
        @app.route('/api/v1/users', methods=['POST'])
        @require_scope('users:write', 'users:admin')
        async def create_user():
            ...

        @app.route('/api/v1/teams/<int:team_id>/urls', methods=['POST'])
        @require_scope('urls:write', team_id_param='team_id')
        async def create_team_url(team_id):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get current user from request context
            if not hasattr(g, "current_user") or not g.current_user:
                raise Forbidden("Authentication required")

            user_id = g.current_user.get("id")
            if not user_id:
                raise Forbidden("Invalid user")

            # Extract team_id and resource_id from route parameters if specified
            team_id = kwargs.get(team_id_param) if team_id_param else None
            resource_id = kwargs.get(resource_id_param) if resource_id_param else None

            # Check if user has any of the required scopes
            user_scopes = get_user_scopes(user_id, team_id, resource_id)
            has_required_scope = any(scope in user_scopes for scope in required_scopes)

            if not has_required_scope:
                raise Forbidden(
                    f'Insufficient permissions. Required scopes: {", ".join(required_scopes)}'
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def _define_rbac_tables(db) -> None:
    """Define RBAC tables for runtime use."""
    if "scopes" not in db.tables:
        db.define_table(
            "scopes",
            db.Field("name", "string", length=100),
            db.Field("description", "text"),
            db.Field("created_at", "datetime"),
            migrate=False,
        )

    if "teams" not in db.tables:
        db.define_table(
            "teams",
            db.Field("name", "string", length=255),
            db.Field("description", "text"),
            db.Field("created_by", "reference auth_user"),
            db.Field("created_at", "datetime"),
            db.Field("updated_at", "datetime"),
            migrate=False,
        )

    if "team_members" not in db.tables:
        db.define_table(
            "team_members",
            db.Field("team_id", "reference teams"),
            db.Field("user_id", "reference auth_user"),
            db.Field("added_at", "datetime"),
            migrate=False,
        )

    if "role_scopes" not in db.tables:
        db.define_table(
            "role_scopes",
            db.Field("role_id", "reference auth_role"),
            db.Field("scope_id", "reference scopes"),
            migrate=False,
        )

    if "user_role_assignments" not in db.tables:
        db.define_table(
            "user_role_assignments",
            db.Field("user_id", "reference auth_user"),
            db.Field("role_id", "reference auth_role"),
            db.Field("scope_level", "string", length=20),
            db.Field("scope_id", "integer"),
            db.Field("created_at", "datetime"),
            migrate=False,
        )

    if "custom_roles" not in db.tables:
        db.define_table(
            "custom_roles",
            db.Field("name", "string", length=100),
            db.Field("description", "text"),
            db.Field("created_by", "reference auth_user"),
            db.Field("scope_level", "string", length=20),
            db.Field("created_at", "datetime"),
            migrate=False,
        )
