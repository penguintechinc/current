import asyncio
import datetime
import os
import ssl
import sys
import time

import aiohttp
from aiohttp import web
from user_agents import parse

sys.path.append(os.path.dirname(__file__))
from apps.shorturl.models import db
from apps.shorturl.utils.analytics import Analytics
from apps.shorturl.utils.security import RateLimiter
from apps.shorturl.utils.urlshortener import URLShortener
from settings import CERT_PATH, DOMAIN, PROXY_HTTP_PORT, PROXY_HTTPS_PORT


class ProxyServer:

    def __init__(self):
        self.app = web.Application()
        self.setup_routes()
        self.analytics = Analytics()

    def setup_routes(self):
        """Setup proxy routes"""
        self.app.router.add_get("/{short_code}", self.handle_redirect)
        self.app.router.add_get("/", self.handle_frontpage)

    async def handle_redirect(self, request):
        """Handle URL redirection"""
        start_time = time.time()
        short_code = request.match_info.get("short_code")

        # Get client IP
        ip_address = request.headers.get(
            "X-Forwarded-For", request.headers.get("X-Real-IP", request.remote)
        )

        # Check rate limit
        if not RateLimiter.check_rate_limit(ip_address):
            return web.Response(text="Rate limit exceeded", status=429)

        # Get URL record
        url_record = URLShortener.get_url_by_short_code(short_code)

        if not url_record:
            return web.Response(text="Short URL not found", status=404)

        # Check if expired
        if url_record.expires_on and url_record.expires_on < datetime.datetime.utcnow():
            return web.Response(text="Short URL has expired", status=410)

        # Update click count
        db(db.urls.id == url_record.id).update(click_count=url_record.click_count + 1)

        # Log analytics
        user_agent_str = request.headers.get("User-Agent", "")
        user_agent = parse(user_agent_str)

        # Get GeoIP data (async)
        geo_data = await self.analytics.get_geoip_data(ip_address)

        # Record analytics
        db.analytics.insert(
            url_id=url_record.id,
            ip_address=ip_address,
            user_agent=user_agent_str,
            referer=request.headers.get("Referer", ""),
            country=geo_data.get("country") if geo_data else None,
            city=geo_data.get("city") if geo_data else None,
            latitude=geo_data.get("latitude") if geo_data else None,
            longitude=geo_data.get("longitude") if geo_data else None,
            device_type="mobile" if user_agent.is_mobile else "desktop",
            browser=user_agent.browser.family if user_agent.browser else None,
            os=user_agent.os.family if user_agent.os else None,
            response_time_ms=int((time.time() - start_time) * 1000),
        )
        db.commit()

        # Redirect with proper headers
        headers = {
            "X-Real-IP": ip_address,
            "X-Forwarded-For": ip_address,
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Location": url_record.long_url,
        }

        return web.Response(status=301, headers=headers)

    async def handle_frontpage(self, request):
        """Handle frontpage display"""
        # Get client IP for rate limiting
        ip_address = request.headers.get(
            "X-Forwarded-For", request.headers.get("X-Real-IP", request.remote)
        )

        # Check rate limit
        if not RateLimiter.check_rate_limit(ip_address):
            return web.Response(text="Rate limit exceeded", status=429)

        # Get frontpage URLs
        frontpage_urls = URLShortener.get_frontpage_urls()

        # Generate HTML
        html = self.generate_frontpage_html(frontpage_urls)

        return web.Response(text=html, content_type="text/html")

    def generate_frontpage_html(self, urls):
        """Generate frontpage HTML with tiles"""
        html = (
            """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>"""
            + DOMAIN
            + """ - Short URLs</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    padding: 2rem;
                }
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                }
                h1 {
                    color: white;
                    text-align: center;
                    margin-bottom: 3rem;
                    font-size: 3rem;
                    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
                    animation: fadeInDown 0.8s ease;
                }
                .tiles {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                    gap: 2rem;
                }
                .tile {
                    background: white;
                    border-radius: 15px;
                    padding: 2rem;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                    transition: transform 0.3s ease, box-shadow 0.3s ease;
                    animation: fadeInUp 0.6s ease;
                    text-decoration: none;
                    color: inherit;
                    display: block;
                }
                .tile:hover {
                    transform: translateY(-5px);
                    box-shadow: 0 15px 40px rgba(0,0,0,0.3);
                }
                .tile h3 {
                    color: #667eea;
                    margin-bottom: 0.5rem;
                    font-size: 1.5rem;
                }
                .tile p {
                    color: #666;
                    line-height: 1.6;
                    margin-bottom: 1rem;
                }
                .tile .url {
                    color: #999;
                    font-size: 0.9rem;
                    word-break: break-all;
                }
                .tile .stats {
                    margin-top: 1rem;
                    padding-top: 1rem;
                    border-top: 1px solid #eee;
                    color: #999;
                    font-size: 0.9rem;
                }
                @keyframes fadeInDown {
                    from { opacity: 0; transform: translateY(-20px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                @keyframes fadeInUp {
                    from { opacity: 0; transform: translateY(20px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                @media (max-width: 768px) {
                    h1 { font-size: 2rem; }
                    .tiles { grid-template-columns: 1fr; }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>"""
            + DOMAIN
            + """</h1>
                <div class="tiles">
        """
        )

        for url in urls:
            html += f"""
                    <a href="/{url.short_code}" class="tile">
                        <h3>{url.title or 'Untitled'}</h3>
                        <p>{url.description or 'No description available'}</p>
                        <div class="url">{url.long_url[:50]}...</div>
                        <div class="stats">👁 {url.click_count} clicks</div>
                    </a>
            """

        html += """
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def get_ssl_context(self):
        """Get SSL context for HTTPS"""
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(
            f"{CERT_PATH}/fullchain.pem", f"{CERT_PATH}/privkey.pem"
        )
        return ssl_context

    async def start(self):
        """Start the proxy server"""
        runner = web.AppRunner(self.app)
        await runner.setup()

        # HTTP server
        http_site = web.TCPSite(runner, "0.0.0.0", PROXY_HTTP_PORT)
        await http_site.start()
        print(f"HTTP Proxy server started on port {PROXY_HTTP_PORT}")

        # HTTPS server
        ssl_context = self.get_ssl_context()
        https_site = web.TCPSite(
            runner, "0.0.0.0", PROXY_HTTPS_PORT, ssl_context=ssl_context
        )
        await https_site.start()
        print(f"HTTPS Proxy server started on port {PROXY_HTTPS_PORT}")


async def main():
    """Main entry point for proxy server"""
    server = ProxyServer()
    await server.start()

    # Keep running
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
