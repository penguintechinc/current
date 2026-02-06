#!/usr/bin/env python3
"""
Quart Backend Entry Point.

Runs the Quart application using Hypercorn ASGI server.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

from hypercorn.asyncio import serve
from hypercorn.config import Config as HypercornConfig

from app import create_app
from app.auth import hash_password
from app.config import Config


def wait_for_database(max_retries: int = 30, retry_delay: int = 2) -> bool:
    """
    Wait for database to be available.

    Args:
        max_retries: Maximum number of connection attempts
        retry_delay: Delay between retries in seconds

    Returns:
        True if database is available, False otherwise
    """
    from pydal import DAL

    db_uri = Config.get_db_uri()
    print(f"Waiting for database connection: {Config.DB_HOST}:{Config.DB_PORT}")

    for attempt in range(1, max_retries + 1):
        try:
            db = DAL(db_uri, pool_size=1, migrate=False)
            db.executesql("SELECT 1")
            db.close()
            print(f"Database connection successful after {attempt} attempt(s)")
            return True
        except Exception as e:
            print(f"Database connection attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)

    return False


def create_default_admin(app) -> None:
    """
    Create default admin user if no users exist.

    Args:
        app: Quart application instance
    """
    from app.models import create_user, get_user_by_email

    # Get database from app config
    db = app.config.get("db")
    if db is None:
        print("WARNING: Database not initialized, skipping default admin creation")
        return

    user_count = db(db.auth_user).count()

    if user_count == 0:
        admin_email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@localhost.local")
        admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")

        # Check if admin already exists (shouldn't, but safety check)
        existing = db(db.auth_user.email == admin_email).select().first()
        if not existing:
            import uuid

            print(f"Creating default admin user: {admin_email}")

            # Create user directly with db to avoid context issues
            user_id = db.auth_user.insert(
                email=admin_email,
                password=hash_password(admin_password),
                full_name="System Administrator",
                is_active=True,
                fs_uniquifier=str(uuid.uuid4()),
                fs_token_uniquifier=str(uuid.uuid4()),
            )

            # Assign admin role
            admin_role = db(db.auth_role.name == "admin").select().first()
            if admin_role:
                db.auth_user_roles.insert(user_id=user_id, role_id=admin_role.id)

            db.commit()

            print("Default admin user created successfully")
            print("WARNING: Change the default password immediately!")
        else:
            print("Admin user already exists")
    else:
        print(
            f"Database has {user_count} existing user(s), "
            "skipping default admin creation"
        )


async def main() -> None:
    """Main async entry point."""
    # Wait for database (sync operation)
    if not wait_for_database():
        print("ERROR: Could not connect to database after maximum retries")
        sys.exit(1)

    # Create Quart app
    app = create_app()

    # Create default admin user (needs to happen before serving)
    # Run in executor since it uses sync PyDAL
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, create_default_admin, app)

    # Configure Hypercorn
    hypercorn_config = HypercornConfig()
    hypercorn_config.bind = [f"{Config.ASGI_HOST}:{Config.ASGI_PORT}"]
    hypercorn_config.workers = Config.ASGI_WORKERS

    # Access log configuration
    hypercorn_config.accesslog = "-"  # Log to stdout
    hypercorn_config.errorlog = "-"   # Log errors to stdout

    # Graceful shutdown timeout
    hypercorn_config.graceful_timeout = 10

    # Keep-alive settings
    hypercorn_config.keep_alive_timeout = 5

    print(f"Starting Quart backend with Hypercorn on {Config.ASGI_HOST}:{Config.ASGI_PORT}")
    print(f"Workers: {Config.ASGI_WORKERS}")

    # Start serving
    await serve(app, hypercorn_config)


def run_dev() -> None:
    """Run in development mode with auto-reload."""
    from quart import Quart

    # Wait for database
    if not wait_for_database():
        print("ERROR: Could not connect to database after maximum retries")
        sys.exit(1)

    app = create_app()

    # Create default admin
    # In dev mode, we need to do this differently
    async def setup_and_run():
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, create_default_admin, app)

    asyncio.run(setup_and_run())

    host = Config.ASGI_HOST
    port = Config.ASGI_PORT

    print(f"Starting Quart backend in development mode on {host}:{port}")
    app.run(host=host, port=port, debug=True)


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    if debug:
        run_dev()
    else:
        asyncio.run(main())
