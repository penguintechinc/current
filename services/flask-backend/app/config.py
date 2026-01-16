"""
Quart Backend Configuration.

Configuration for Flask-Security-Too, PyDAL, and related services.
"""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Any


class Config:
    """Base configuration."""

    # Application
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    # Flask-Security-Too Configuration
    # See: https://flask-security-too.readthedocs.io/en/stable/configuration.html
    SECURITY_PASSWORD_SALT = os.getenv(
        "SECURITY_PASSWORD_SALT", "security-password-salt-change-me"
    )
    SECURITY_PASSWORD_HASH = "bcrypt"
    SECURITY_PASSWORD_SCHEMES = ["bcrypt", "argon2", "pbkdf2_sha256"]
    SECURITY_DEPRECATED_PASSWORD_SCHEMES = ["pbkdf2_sha256"]

    # Registration
    SECURITY_REGISTERABLE = True
    SECURITY_SEND_REGISTER_EMAIL = False
    SECURITY_POST_REGISTER_VIEW = None  # API-based, no redirects

    # Login/Logout
    SECURITY_POST_LOGIN_VIEW = None
    SECURITY_POST_LOGOUT_VIEW = None
    SECURITY_UNAUTHORIZED_VIEW = None

    # Trackable (track login IP, count, timestamps)
    SECURITY_TRACKABLE = True

    # Token authentication
    SECURITY_TOKEN_AUTHENTICATION_HEADER = "Authorization"
    SECURITY_TOKEN_AUTHENTICATION_KEY = "auth_token"
    SECURITY_TOKEN_MAX_AGE = int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "30")) * 60

    # CSRF (disabled for API-only backend)
    WTF_CSRF_ENABLED = False
    SECURITY_CSRF_PROTECT_MECHANISMS = []
    SECURITY_CSRF_IGNORE_UNAUTH_ENDPOINTS = True

    # Password validation
    SECURITY_PASSWORD_LENGTH_MIN = 8
    SECURITY_PASSWORD_COMPLEXITY_CHECKER = None  # We use py_libs validation

    # User identity attributes
    SECURITY_USER_IDENTITY_ATTRIBUTES = [{"email": {"mapper": str.casefold}}]

    # JWT Configuration (backward compatibility + Flask-Security)
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "30"))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(os.getenv("JWT_REFRESH_TOKEN_DAYS", "7"))
    )

    # Database - PyDAL compatible
    DB_TYPE = os.getenv("DB_TYPE", "postgres")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "app_db")
    DB_USER = os.getenv("DB_USER", "app_user")
    DB_PASS = os.getenv("DB_PASS", "app_pass")
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))

    # CORS
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

    # ASGI Server (Hypercorn)
    ASGI_HOST = os.getenv("ASGI_HOST", "0.0.0.0")
    ASGI_PORT = int(os.getenv("ASGI_PORT", "5000"))
    ASGI_WORKERS = int(os.getenv("ASGI_WORKERS", "4"))

    # Rate Limiting
    RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    RATE_LIMIT_DEFAULT = int(os.getenv("RATE_LIMIT_DEFAULT", "100"))  # per minute
    RATE_LIMIT_LOGIN = int(os.getenv("RATE_LIMIT_LOGIN", "10"))  # per minute
    RATE_LIMIT_REGISTER = int(os.getenv("RATE_LIMIT_REGISTER", "5"))  # per minute

    # Redis (for rate limiting, caching)
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_ENABLED = os.getenv("REDIS_ENABLED", "false").lower() == "true"

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Monitoring
    PROMETHEUS_ENABLED = os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true"
    PROMETHEUS_PORT = int(os.getenv("PROMETHEUS_PORT", "9090"))

    @classmethod
    def get_db_uri(cls) -> str:
        """Build PyDAL-compatible database URI."""
        db_type = cls.DB_TYPE

        # Map common aliases to PyDAL format
        type_map = {
            "postgresql": "postgres",
            "mysql": "mysql",
            "sqlite": "sqlite",
            "mssql": "mssql",
            "mariadb": "mysql",  # MariaDB uses MySQL driver
        }
        db_type = type_map.get(db_type, db_type)

        if db_type == "sqlite":
            if cls.DB_NAME == ":memory:":
                return "sqlite:memory"
            return f"sqlite://{cls.DB_NAME}.db"

        return (
            f"{db_type}://{cls.DB_USER}:{cls.DB_PASS}@"
            f"{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"
        )

    @classmethod
    def get_security_config(cls) -> dict[str, Any]:
        """Get Flask-Security-Too configuration as dictionary."""
        return {
            "SECURITY_PASSWORD_SALT": cls.SECURITY_PASSWORD_SALT,
            "SECURITY_PASSWORD_HASH": cls.SECURITY_PASSWORD_HASH,
            "SECURITY_REGISTERABLE": cls.SECURITY_REGISTERABLE,
            "SECURITY_SEND_REGISTER_EMAIL": cls.SECURITY_SEND_REGISTER_EMAIL,
            "SECURITY_TRACKABLE": cls.SECURITY_TRACKABLE,
            "SECURITY_TOKEN_AUTHENTICATION_HEADER": (
                cls.SECURITY_TOKEN_AUTHENTICATION_HEADER
            ),
            "SECURITY_TOKEN_MAX_AGE": cls.SECURITY_TOKEN_MAX_AGE,
            "WTF_CSRF_ENABLED": cls.WTF_CSRF_ENABLED,
            "SECURITY_CSRF_PROTECT_MECHANISMS": cls.SECURITY_CSRF_PROTECT_MECHANISMS,
            "SECURITY_PASSWORD_LENGTH_MIN": cls.SECURITY_PASSWORD_LENGTH_MIN,
            "SECURITY_USER_IDENTITY_ATTRIBUTES": cls.SECURITY_USER_IDENTITY_ATTRIBUTES,
        }


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True
    LOG_LEVEL = "DEBUG"

    # Less strict rate limiting in development
    RATE_LIMIT_ENABLED = False


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False
    LOG_LEVEL = "INFO"

    # Strict security in production
    SECURITY_PASSWORD_SALT = os.getenv("SECURITY_PASSWORD_SALT")  # Required
    SECRET_KEY = os.getenv("SECRET_KEY")  # Required

    @classmethod
    def validate(cls) -> None:
        """Validate production configuration."""
        if (
            not cls.SECRET_KEY
            or cls.SECRET_KEY == "dev-secret-key-change-in-production"
        ):
            raise ValueError("SECRET_KEY must be set in production")
        if not cls.SECURITY_PASSWORD_SALT or "change" in cls.SECURITY_PASSWORD_SALT:
            raise ValueError("SECURITY_PASSWORD_SALT must be set in production")


class TestingConfig(Config):
    """Testing configuration."""

    TESTING = True
    DEBUG = True
    DB_TYPE = "sqlite"
    DB_NAME = ":memory:"

    # Disable rate limiting in tests
    RATE_LIMIT_ENABLED = False

    # Disable Prometheus in tests to avoid duplicate metric registration
    PROMETHEUS_ENABLED = False

    # Use bcrypt for tests (plaintext not allowed by Flask-Security-Too)
    SECURITY_PASSWORD_HASH = "bcrypt"

    # CORS - use specific origin in testing (wildcard + credentials is invalid)
    CORS_ORIGINS = "http://localhost:3000"


def get_config() -> type[Config]:
    """Get configuration based on environment."""
    env = os.getenv("FLASK_ENV", "development").lower()
    config_map = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "testing": TestingConfig,
    }
    return config_map.get(env, DevelopmentConfig)
