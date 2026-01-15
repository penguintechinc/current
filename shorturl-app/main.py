#!/usr/bin/env python3

import asyncio
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from admin_portal import AdminPortal
from apps.shorturl.utils.analytics import Analytics
from apps.shorturl.utils.certificates import CertificateManager

# Import servers
from proxy_server import ProxyServer
from settings import DOMAIN

from apps.shorturl.models import db


def init_database():
    """Initialize database and create default admin user"""
    print("Initializing database...")

    # Check if admin exists
    if db(db.auth_user.role == "admin").count() == 0:
        from apps.shorturl.utils.auth import auth

        # Create default admin
        admin = auth.register(
            email="admin@localhost",
            password="admin123",
            first_name="Admin",
            last_name="User",
            role="admin",
        )

        if admin:
            print("Default admin user created:")
            print("Email: admin@localhost")
            print("Password: admin123")
            print("IMPORTANT: Change this password after first login!")

    print("Database initialized successfully")


def init_certificates():
    """Initialize certificates"""
    print("Checking certificates...")
    cert_manager = CertificateManager()

    # Check if certificate exists
    cert_info = cert_manager.get_certificate_info()

    if not cert_info:
        print(f"Generating self-signed certificate for {DOMAIN}...")
        cert_manager.generate_self_signed()
        print("Self-signed certificate generated successfully")
    else:
        print(f"Certificate found for {DOMAIN}")
        print(f"Type: {cert_info['type']}")
        print(f"Expires in {cert_info['days_until_expiry']} days")


def cleanup_analytics():
    """Periodic cleanup of old analytics data"""
    analytics = Analytics()
    while True:
        try:
            # Sleep for 24 hours
            time.sleep(86400)

            # Cleanup old data
            deleted = analytics.cleanup_old_analytics()
            if deleted > 0:
                print(f"Cleaned up {deleted} old analytics records")
        except Exception as e:
            print(f"Error in analytics cleanup: {e}")


async def start_proxy_server():
    """Start the proxy server"""
    print("Starting proxy server...")
    server = ProxyServer()
    await server.start()


async def start_admin_portal():
    """Start the admin portal"""
    print("Starting admin portal...")
    portal = AdminPortal()
    await portal.start()


async def main():
    """Main application entry point"""
    print("=" * 60)
    print("ShortURL Application v1.0.0")
    print("=" * 60)

    # Initialize database
    init_database()

    # Initialize certificates
    init_certificates()

    # Start analytics cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_analytics, daemon=True)
    cleanup_thread.start()

    # Create tasks for both servers
    tasks = [
        asyncio.create_task(start_proxy_server()),
        asyncio.create_task(start_admin_portal()),
    ]

    print("=" * 60)
    print(f"Services starting on domain: {DOMAIN}")
    print(f"Proxy: http://0.0.0.0:80 and https://0.0.0.0:443")
    print(f"Admin Portal: https://0.0.0.0:9443")
    print("=" * 60)

    # Wait for all tasks
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    try:
        # Use uvloop for better performance if available
        try:
            import uvloop

            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            print("Using uvloop for enhanced performance")
        except ImportError:
            print("Using standard asyncio event loop")

        # Run the main application
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)
