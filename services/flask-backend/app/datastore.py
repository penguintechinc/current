"""
PyDAL User Datastore for Flask-Security-Too.

Implements the UserDatastore interface for Flask-Security-Too
using PyDAL as the database abstraction layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Iterator, List, Optional, Set

from flask_security import RoleMixin, UserDatastore, UserMixin
from pydal import DAL
from pydal.objects import Row, Table


class PyDALRole(RoleMixin):
    """
    Role wrapper implementing Flask-Security RoleMixin.

    Wraps a PyDAL Row to provide the interface expected by Flask-Security-Too.
    """

    __slots__ = ("_row", "_db")

    def __init__(self, row: Row, db: DAL) -> None:
        self._row = row
        self._db = db

    @property
    def id(self) -> int:
        """Role ID."""
        return self._row.id

    @property
    def name(self) -> str:
        """Role name."""
        return self._row.name

    @property
    def description(self) -> Optional[str]:
        """Role description."""
        return self._row.get("description")

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, PyDALRole):
            return self.name == other.name
        if isinstance(other, str):
            return self.name == other
        return False

    def __hash__(self) -> int:
        return hash(self.name)

    def __str__(self) -> str:
        return self.name


class PyDALUser(UserMixin):
    """
    User wrapper implementing Flask-Security UserMixin.

    Wraps a PyDAL Row to provide the interface expected by Flask-Security-Too.
    """

    __slots__ = ("_row", "_db", "_roles_cache")

    def __init__(self, row: Row, db: DAL) -> None:
        self._row = row
        self._db = db
        self._roles_cache: Optional[List[PyDALRole]] = None

    @property
    def id(self) -> int:
        """User ID."""
        return self._row.id

    @property
    def email(self) -> str:
        """User email address."""
        return self._row.email

    @property
    def password(self) -> str:
        """Password hash (Flask-Security expects 'password' not 'password_hash')."""
        return self._row.password

    @password.setter
    def password(self, value: str) -> None:
        """Set password hash."""
        self._db(self._db.auth_user.id == self.id).update(password=value)
        self._db.commit()
        self._row.password = value

    @property
    def active(self) -> bool:
        """Whether user is active (Flask-Security expects 'active' property)."""
        return self._row.is_active

    @active.setter
    def active(self, value: bool) -> None:
        """Set active status."""
        self._db(self._db.auth_user.id == self.id).update(is_active=value)
        self._db.commit()
        self._row.is_active = value

    @property
    def fs_uniquifier(self) -> str:
        """Flask-Security uniquifier (required for token generation)."""
        return self._row.fs_uniquifier

    @property
    def fs_token_uniquifier(self) -> Optional[str]:
        """Token uniquifier for token invalidation."""
        return self._row.get("fs_token_uniquifier")

    @property
    def full_name(self) -> str:
        """User full name."""
        return self._row.get("full_name", "")

    @property
    def confirmed_at(self) -> Optional[datetime]:
        """Email confirmation timestamp."""
        return self._row.get("confirmed_at")

    @property
    def last_login_at(self) -> Optional[datetime]:
        """Last login timestamp."""
        return self._row.get("last_login_at")

    @property
    def current_login_at(self) -> Optional[datetime]:
        """Current login timestamp."""
        return self._row.get("current_login_at")

    @property
    def login_count(self) -> int:
        """Total login count."""
        return self._row.get("login_count", 0)

    @property
    def created_at(self) -> Optional[datetime]:
        """Account creation timestamp."""
        return self._row.get("created_at")

    @property
    def updated_at(self) -> Optional[datetime]:
        """Last update timestamp."""
        return self._row.get("updated_at")

    @property
    def roles(self) -> List[PyDALRole]:
        """User roles (loaded from join table)."""
        if self._roles_cache is None:
            self._roles_cache = self._load_roles()
        return self._roles_cache

    def _load_roles(self) -> List[PyDALRole]:
        """Load roles from database."""
        db = self._db
        role_rows = db(
            (db.auth_user_roles.user_id == self.id)
            & (db.auth_user_roles.role_id == db.auth_role.id)
        ).select(db.auth_role.ALL)
        return [PyDALRole(row, db) for row in role_rows]

    def has_role(self, role: Any) -> bool:
        """Check if user has a specific role."""
        if isinstance(role, str):
            return any(r.name == role for r in self.roles)
        if isinstance(role, PyDALRole):
            return role in self.roles
        return False

    def add_role(self, role: PyDALRole) -> bool:
        """Add a role to this user."""
        if not self.has_role(role):
            self._db.auth_user_roles.insert(user_id=self.id, role_id=role.id)
            self._db.commit()
            self._roles_cache = None  # Invalidate cache
            return True
        return False

    def remove_role(self, role: PyDALRole) -> bool:
        """Remove a role from this user."""
        if self.has_role(role):
            self._db(
                (self._db.auth_user_roles.user_id == self.id)
                & (self._db.auth_user_roles.role_id == role.id)
            ).delete()
            self._db.commit()
            self._roles_cache = None  # Invalidate cache
            return True
        return False

    def get_auth_token(self) -> Optional[str]:
        """Get authentication token (handled by Flask-Security)."""
        return None  # Flask-Security handles this

    def as_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.roles[0].name if self.roles else "viewer",
            "roles": [r.name for r in self.roles],
            "is_active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": (
                self.last_login_at.isoformat() if self.last_login_at else None
            ),
        }

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, PyDALUser):
            return self.id == other.id
        return False

    def __hash__(self) -> int:
        return hash(self.id)


class PyDALUserDatastore(UserDatastore):
    """
    PyDAL-based user datastore for Flask-Security-Too.

    Implements the UserDatastore interface using PyDAL tables.
    """

    def __init__(
        self,
        db: DAL,
        user_table: Table,
        role_table: Table,
        user_roles_table: Table,
    ) -> None:
        """
        Initialize the datastore.

        Args:
            db: PyDAL database instance
            user_table: auth_user table
            role_table: auth_role table
            user_roles_table: auth_user_roles join table
        """
        self.db = db
        self.user_model = user_table
        self.role_model = role_table
        self.user_roles_model = user_roles_table

    def find_user(self, **kwargs: Any) -> Optional[PyDALUser]:
        """
        Find a user by attributes.

        Common lookups: id, email, fs_uniquifier
        """
        db = self.db
        query = None

        for key, value in kwargs.items():
            if value is None:
                continue
            field = getattr(db.auth_user, key, None)
            if field is not None:
                condition = field == value
                query = condition if query is None else query & condition

        if query is None:
            return None

        row = db(query).select().first()
        return PyDALUser(row, db) if row else None

    def find_role(self, role: str) -> Optional[PyDALRole]:
        """Find a role by name."""
        db = self.db
        row = db(db.auth_role.name == role).select().first()
        return PyDALRole(row, db) if row else None

    def create_user(self, **kwargs: Any) -> PyDALUser:
        """
        Create a new user.

        Required kwargs: email, password
        Optional kwargs: full_name, active, roles
        """
        db = self.db

        # Generate unique identifiers if not provided
        if "fs_uniquifier" not in kwargs:
            kwargs["fs_uniquifier"] = str(uuid.uuid4())
        if "fs_token_uniquifier" not in kwargs:
            kwargs["fs_token_uniquifier"] = str(uuid.uuid4())

        # Extract roles before inserting
        roles = kwargs.pop("roles", [])

        # Set defaults
        kwargs.setdefault("active", True)
        kwargs.setdefault("login_count", 0)
        kwargs.setdefault("created_at", datetime.utcnow())

        # Insert user
        user_id = db.auth_user.insert(**kwargs)
        db.commit()

        # Add roles
        user = self.find_user(id=user_id)
        if user:
            for role in roles:
                if isinstance(role, str):
                    role_obj = self.find_role(role)
                else:
                    role_obj = role
                if role_obj:
                    user.add_role(role_obj)

        return user

    def create_role(self, **kwargs: Any) -> PyDALRole:
        """Create a new role."""
        db = self.db
        role_id = db.auth_role.insert(**kwargs)
        db.commit()
        return self.find_role(kwargs["name"])

    def delete_user(self, user: PyDALUser) -> None:
        """Delete a user and their role assignments."""
        db = self.db

        # Delete role assignments
        db(db.auth_user_roles.user_id == user.id).delete()

        # Delete user
        db(db.auth_user.id == user.id).delete()
        db.commit()

    def add_role_to_user(self, user: PyDALUser, role: Any) -> bool:
        """Add a role to a user."""
        if isinstance(role, str):
            role_obj = self.find_role(role)
        else:
            role_obj = role

        if role_obj is None:
            return False

        return user.add_role(role_obj)

    def remove_role_from_user(self, user: PyDALUser, role: Any) -> bool:
        """Remove a role from a user."""
        if isinstance(role, str):
            role_obj = self.find_role(role)
        else:
            role_obj = role

        if role_obj is None:
            return False

        return user.remove_role(role_obj)

    def toggle_active(self, user: PyDALUser) -> bool:
        """Toggle user active status."""
        user.active = not user.active
        return user.active

    def deactivate_user(self, user: PyDALUser) -> bool:
        """Deactivate a user."""
        user.active = False
        return True

    def activate_user(self, user: PyDALUser) -> bool:
        """Activate a user."""
        user.active = True
        return True

    def set_uniquifier(self, user: PyDALUser, uniquifier: Optional[str] = None) -> None:
        """Set user's fs_uniquifier."""
        if uniquifier is None:
            uniquifier = str(uuid.uuid4())

        db = self.db
        db(db.auth_user.id == user.id).update(fs_uniquifier=uniquifier)
        db.commit()

    def set_token_uniquifier(
        self, user: PyDALUser, uniquifier: Optional[str] = None
    ) -> None:
        """Set user's fs_token_uniquifier (invalidates all auth tokens)."""
        if uniquifier is None:
            uniquifier = str(uuid.uuid4())

        db = self.db
        db(db.auth_user.id == user.id).update(fs_token_uniquifier=uniquifier)
        db.commit()

    def commit(self) -> None:
        """Commit any pending changes."""
        self.db.commit()

    def put(self, model: Any) -> Any:
        """Put/update a model (no-op for PyDAL, commit handles this)."""
        self.db.commit()
        return model
