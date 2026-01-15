import asyncio
from aiohttp import web
import aiohttp_cors
import ssl
import json
import sys
import os

sys.path.append(os.path.dirname(__file__))
from apps.shorturl.models import db
from apps.shorturl.utils.auth import auth, requires_role
from apps.shorturl.utils.urlshortener import URLShortener
from apps.shorturl.utils.analytics import Analytics
from apps.shorturl.utils.certificates import CertificateManager
from apps.shorturl.utils.security import Security, rate_limit
from settings import ADMIN_HTTPS_PORT, CERT_PATH


class AdminPortal:

    def __init__(self):
        self.app = web.Application()
        self.setup_routes()
        self.setup_cors()
        self.analytics = Analytics()
        self.cert_manager = CertificateManager()

    def setup_cors(self):
        """Setup CORS for API endpoints"""
        cors = aiohttp_cors.setup(
            self.app,
            defaults={
                "*": aiohttp_cors.ResourceOptions(
                    allow_credentials=True,
                    expose_headers="*",
                    allow_headers="*",
                    allow_methods="*",
                )
            },
        )

        for route in list(self.app.router.routes()):
            cors.add(route)

    def setup_routes(self):
        """Setup admin portal routes"""
        # Static files
        self.app.router.add_static("/static", "apps/shorturl/static")

        # Auth routes
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/login", self.handle_login_page)
        self.app.router.add_post("/api/auth/login", self.handle_login)
        self.app.router.add_post("/api/auth/logout", self.handle_logout)
        self.app.router.add_post("/api/auth/register", self.handle_register)

        # Dashboard routes
        self.app.router.add_get("/dashboard", self.handle_dashboard)

        # URL management routes
        self.app.router.add_get("/api/urls", self.handle_get_urls)
        self.app.router.add_post("/api/urls", self.handle_create_url)
        self.app.router.add_put("/api/urls/{id}", self.handle_update_url)
        self.app.router.add_delete("/api/urls/{id}", self.handle_delete_url)
        self.app.router.add_get("/api/urls/search", self.handle_search_urls)

        # Category management routes
        self.app.router.add_get("/api/categories", self.handle_get_categories)
        self.app.router.add_post("/api/categories", self.handle_create_category)
        self.app.router.add_put("/api/categories/{id}", self.handle_update_category)
        self.app.router.add_delete("/api/categories/{id}", self.handle_delete_category)

        # Analytics routes
        self.app.router.add_get("/api/analytics/url/{id}", self.handle_url_analytics)
        self.app.router.add_get("/api/analytics/global", self.handle_global_analytics)
        self.app.router.add_get("/api/analytics/visitors", self.handle_top_visitors)

        # Certificate management routes
        self.app.router.add_get("/api/certificates", self.handle_get_certificate)
        self.app.router.add_post("/api/certificates/acme", self.handle_request_acme)
        self.app.router.add_post(
            "/api/certificates/renew", self.handle_renew_certificate
        )

        # Settings routes
        self.app.router.add_get("/api/settings", self.handle_get_settings)
        self.app.router.add_put("/api/settings", self.handle_update_settings)

        # Monitoring endpoints
        self.app.router.add_get("/healthz", self.handle_healthz)
        self.app.router.add_get("/metrics", self.handle_metrics)

    async def handle_index(self, request):
        """Handle index page"""
        return web.FileResponse("apps/shorturl/templates/index.html")

    async def handle_login_page(self, request):
        """Handle login page"""
        return web.FileResponse("apps/shorturl/templates/login.html")

    async def handle_login(self, request):
        """Handle login API"""
        data = await request.json()
        email = data.get("email")
        password = data.get("password")

        user = auth.login(email, password)
        if user:
            return web.json_response(
                {
                    "success": True,
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "role": user.role,
                    },
                }
            )
        else:
            return web.json_response(
                {"success": False, "error": "Invalid credentials"}, status=401
            )

    async def handle_logout(self, request):
        """Handle logout API"""
        auth.logout()
        return web.json_response({"success": True})

    async def handle_register(self, request):
        """Handle registration API"""
        data = await request.json()

        user = auth.register(
            email=data.get("email"),
            password=data.get("password"),
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            role=data.get("role", "viewer"),
        )

        if user:
            return web.json_response({"success": True})
        else:
            return web.json_response(
                {"success": False, "error": "User already exists"}, status=400
            )

    async def handle_dashboard(self, request):
        """Handle dashboard page"""
        return web.FileResponse("apps/shorturl/templates/dashboard.html")

    async def handle_get_urls(self, request):
        """Get all URLs"""
        category_id = request.query.get("category_id")

        if category_id:
            urls = db(
                (db.urls.is_active == True) & (db.urls.category_id == category_id)
            ).select()
        else:
            urls = db(db.urls.is_active == True).select()

        urls_data = []
        for url in urls:
            urls_data.append(
                {
                    "id": url.id,
                    "short_code": url.short_code,
                    "long_url": url.long_url,
                    "title": url.title,
                    "description": url.description,
                    "category_id": url.category_id,
                    "click_count": url.click_count,
                    "show_on_frontpage": url.show_on_frontpage,
                    "created_on": (
                        url.created_on.isoformat() if url.created_on else None
                    ),
                }
            )

        return web.json_response(urls_data)

    async def handle_create_url(self, request):
        """Create new short URL"""
        data = await request.json()

        # Get current user (simplified for now)
        user_id = 1  # Would get from session

        url, error = URLShortener.create_short_url(
            long_url=data.get("long_url"),
            user_id=user_id,
            custom_code=data.get("custom_code"),
            category_id=data.get("category_id"),
            title=data.get("title"),
            description=data.get("description"),
            show_on_frontpage=data.get("show_on_frontpage", False),
        )

        if url:
            return web.json_response(
                {
                    "success": True,
                    "url": {
                        "id": url.id,
                        "short_code": url.short_code,
                        "long_url": url.long_url,
                    },
                }
            )
        else:
            return web.json_response({"success": False, "error": error}, status=400)

    async def handle_update_url(self, request):
        """Update existing URL"""
        url_id = request.match_info.get("id")
        data = await request.json()

        # Get current user (simplified)
        user_id = 1

        url, error = URLShortener.update_short_url(
            url_id=url_id, user_id=user_id, **data
        )

        if url:
            return web.json_response({"success": True})
        else:
            return web.json_response({"success": False, "error": error}, status=400)

    async def handle_delete_url(self, request):
        """Delete URL"""
        url_id = request.match_info.get("id")
        user_id = 1  # Would get from session

        success, error = URLShortener.delete_short_url(url_id, user_id)

        if success:
            return web.json_response({"success": True})
        else:
            return web.json_response({"success": False, "error": error}, status=400)

    async def handle_search_urls(self, request):
        """Search URLs"""
        query = request.query.get("q")
        category_id = request.query.get("category_id")
        user_id = 1  # Would get from session

        urls = URLShortener.search_urls(query, user_id, category_id)

        urls_data = []
        for url in urls:
            urls_data.append(
                {
                    "id": url.id,
                    "short_code": url.short_code,
                    "long_url": url.long_url,
                    "title": url.title,
                    "click_count": url.click_count,
                }
            )

        return web.json_response(urls_data)

    async def handle_get_categories(self, request):
        """Get all categories"""
        categories = db(db.categories.is_active == True).select()

        categories_data = []
        for cat in categories:
            categories_data.append(
                {"id": cat.id, "name": cat.name, "description": cat.description}
            )

        return web.json_response(categories_data)

    async def handle_create_category(self, request):
        """Create new category"""
        data = await request.json()
        user_id = 1  # Would get from session

        cat_id = db.categories.insert(
            name=Security.sanitize_input(data.get("name")),
            description=Security.sanitize_input(data.get("description")),
            created_by=user_id,
        )
        db.commit()

        return web.json_response({"success": True, "id": cat_id})

    async def handle_update_category(self, request):
        """Update category"""
        cat_id = request.match_info.get("id")
        data = await request.json()

        db(db.categories.id == cat_id).update(
            name=Security.sanitize_input(data.get("name")),
            description=Security.sanitize_input(data.get("description")),
        )
        db.commit()

        return web.json_response({"success": True})

    async def handle_delete_category(self, request):
        """Delete category"""
        cat_id = request.match_info.get("id")

        db(db.categories.id == cat_id).update(is_active=False)
        db.commit()

        return web.json_response({"success": True})

    async def handle_url_analytics(self, request):
        """Get analytics for specific URL"""
        url_id = request.match_info.get("id")
        days = int(request.query.get("days", 30))

        analytics_data = self.analytics.get_url_analytics(url_id, days)

        return web.json_response(analytics_data)

    async def handle_global_analytics(self, request):
        """Get global analytics"""
        days = int(request.query.get("days", 30))

        analytics_data = self.analytics.get_global_analytics(days)

        return web.json_response(analytics_data)

    async def handle_top_visitors(self, request):
        """Get top repeat visitors"""
        days = int(request.query.get("days", 30))
        limit = int(request.query.get("limit", 10))

        visitors = self.analytics.get_top_repeat_visitors(days, limit)

        return web.json_response(visitors)

    async def handle_get_certificate(self, request):
        """Get certificate information"""
        cert_info = self.cert_manager.get_certificate_info()

        if cert_info:
            return web.json_response(cert_info)
        else:
            return web.json_response({"error": "No certificate found"}, status=404)

    async def handle_request_acme(self, request):
        """Request ACME certificate"""
        success, message = self.cert_manager.request_acme_certificate()

        if success:
            return web.json_response({"success": True, "message": message})
        else:
            return web.json_response({"success": False, "error": message}, status=400)

    async def handle_renew_certificate(self, request):
        """Renew certificate"""
        success = self.cert_manager.renew_certificate()

        if success:
            return web.json_response({"success": True})
        else:
            return web.json_response(
                {"success": False, "error": "Renewal failed"}, status=400
            )

    async def handle_get_settings(self, request):
        """Get application settings"""
        settings = db(db.settings).select()

        settings_data = {}
        for setting in settings:
            settings_data[setting.key] = setting.value

        return web.json_response(settings_data)

    async def handle_update_settings(self, request):
        """Update application settings"""
        data = await request.json()
        user_id = 1  # Would get from session

        for key, value in data.items():
            db(db.settings.key == key).update(value=str(value), updated_by=user_id)
        db.commit()

        return web.json_response({"success": True})

    async def handle_healthz(self, request):
        """Health check endpoint"""
        # Check database connection
        try:
            db.executesql("SELECT 1")
            return web.json_response({"status": "healthy"})
        except:
            return web.json_response({"status": "unhealthy"}, status=503)

    async def handle_metrics(self, request):
        """Prometheus metrics endpoint"""
        # Basic authentication check
        auth_header = request.headers.get("Authorization")
        # Would validate against viewer credentials

        metrics = []

        # Total URLs
        total_urls = db(db.urls.is_active == True).count()
        metrics.append(f"shorturl_total_urls {total_urls}")

        # Total clicks
        total_clicks = db(db.analytics).count()
        metrics.append(f"shorturl_total_clicks {total_clicks}")

        # Total users
        total_users = db(db.auth_user.is_active == True).count()
        metrics.append(f"shorturl_total_users {total_users}")

        # Active categories
        total_categories = db(db.categories.is_active == True).count()
        metrics.append(f"shorturl_total_categories {total_categories}")

        return web.Response(text="\\n".join(metrics), content_type="text/plain")

    def get_ssl_context(self):
        """Get SSL context for HTTPS"""
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(
            f"{CERT_PATH}/fullchain.pem", f"{CERT_PATH}/privkey.pem"
        )
        return ssl_context

    async def start(self):
        """Start the admin portal"""
        runner = web.AppRunner(self.app)
        await runner.setup()

        # HTTPS server on port 9443
        ssl_context = self.get_ssl_context()
        site = web.TCPSite(runner, "0.0.0.0", ADMIN_HTTPS_PORT, ssl_context=ssl_context)
        await site.start()
        print(f"Admin portal started on https://0.0.0.0:{ADMIN_HTTPS_PORT}")


async def main():
    """Main entry point for admin portal"""
    portal = AdminPortal()
    await portal.start()

    # Keep running
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
