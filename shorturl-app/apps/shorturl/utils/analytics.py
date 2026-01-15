import datetime
import os
import sys

import geoip2.database
import geoip2.errors
from geolite2 import geolite2

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
)
from apps.shorturl.models import db


class Analytics:

    def __init__(self):
        self.geoip_reader = geolite2.reader()

    async def get_geoip_data(self, ip_address):
        """Get GeoIP data for an IP address"""
        try:
            response = self.geoip_reader.get(ip_address)
            if response:
                return {
                    "country": response.get("country", {}).get("names", {}).get("en"),
                    "city": response.get("city", {}).get("names", {}).get("en"),
                    "latitude": response.get("location", {}).get("latitude"),
                    "longitude": response.get("location", {}).get("longitude"),
                }
        except Exception:
            pass
        return {}

    @staticmethod
    def get_url_analytics(url_id, days=30):
        """Get analytics for a specific URL"""
        start_date = datetime.datetime.utcnow() - datetime.timedelta(days=days)

        # Get click data
        clicks = db(
            (db.analytics.url_id == url_id) & (db.analytics.clicked_on >= start_date)
        ).select()

        # Process data
        analytics_data = {
            "total_clicks": len(clicks),
            "unique_visitors": len(set([c.ip_address for c in clicks])),
            "countries": {},
            "cities": {},
            "devices": {"mobile": 0, "desktop": 0},
            "browsers": {},
            "operating_systems": {},
            "daily_clicks": {},
            "top_referers": {},
            "average_response_time": 0,
        }

        total_response_time = 0

        for click in clicks:
            # Countries
            if click.country:
                analytics_data["countries"][click.country] = (
                    analytics_data["countries"].get(click.country, 0) + 1
                )

            # Cities
            if click.city:
                analytics_data["cities"][click.city] = (
                    analytics_data["cities"].get(click.city, 0) + 1
                )

            # Devices
            if click.device_type:
                analytics_data["devices"][click.device_type] += 1

            # Browsers
            if click.browser:
                analytics_data["browsers"][click.browser] = (
                    analytics_data["browsers"].get(click.browser, 0) + 1
                )

            # Operating systems
            if click.os:
                analytics_data["operating_systems"][click.os] = (
                    analytics_data["operating_systems"].get(click.os, 0) + 1
                )

            # Daily clicks
            date_key = click.clicked_on.date().isoformat()
            analytics_data["daily_clicks"][date_key] = (
                analytics_data["daily_clicks"].get(date_key, 0) + 1
            )

            # Referers
            if click.referer:
                analytics_data["top_referers"][click.referer] = (
                    analytics_data["top_referers"].get(click.referer, 0) + 1
                )

            # Response time
            if click.response_time_ms:
                total_response_time += click.response_time_ms

        # Calculate average response time
        if clicks:
            analytics_data["average_response_time"] = total_response_time / len(clicks)

        # Sort and limit top items
        analytics_data["countries"] = dict(
            sorted(
                analytics_data["countries"].items(), key=lambda x: x[1], reverse=True
            )[:10]
        )

        analytics_data["cities"] = dict(
            sorted(analytics_data["cities"].items(), key=lambda x: x[1], reverse=True)[
                :10
            ]
        )

        analytics_data["top_referers"] = dict(
            sorted(
                analytics_data["top_referers"].items(), key=lambda x: x[1], reverse=True
            )[:10]
        )

        return analytics_data

    @staticmethod
    def get_global_analytics(days=30):
        """Get global analytics for all URLs"""
        start_date = datetime.datetime.utcnow() - datetime.timedelta(days=days)

        # Get all clicks
        clicks = db(db.analytics.clicked_on >= start_date).select()

        # Get top URLs
        url_clicks = {}
        for click in clicks:
            url_clicks[click.url_id] = url_clicks.get(click.url_id, 0) + 1

        top_urls = sorted(url_clicks.items(), key=lambda x: x[1], reverse=True)[:10]

        # Get URL details
        top_urls_data = []
        for url_id, click_count in top_urls:
            url = db.urls[url_id]
            if url:
                top_urls_data.append(
                    {
                        "short_code": url.short_code,
                        "title": url.title or url.long_url[:50],
                        "clicks": click_count,
                    }
                )

        # Get unique visitors
        unique_ips = set([c.ip_address for c in clicks])

        # Get top countries
        countries = {}
        for click in clicks:
            if click.country:
                countries[click.country] = countries.get(click.country, 0) + 1

        top_countries = dict(
            sorted(countries.items(), key=lambda x: x[1], reverse=True)[:10]
        )

        return {
            "total_clicks": len(clicks),
            "unique_visitors": len(unique_ips),
            "top_urls": top_urls_data,
            "top_countries": top_countries,
            "total_urls": db(db.urls.is_active == True).count(),
            "total_users": db(db.auth_user.is_active == True).count(),
        }

    @staticmethod
    def get_top_repeat_visitors(days=30, limit=10):
        """Get top repeat visitors"""
        start_date = datetime.datetime.utcnow() - datetime.timedelta(days=days)

        # Get all clicks
        clicks = db(db.analytics.clicked_on >= start_date).select()

        # Count by IP
        ip_counts = {}
        for click in clicks:
            ip_counts[click.ip_address] = ip_counts.get(click.ip_address, 0) + 1

        # Sort and get top
        top_ips = sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:limit]

        # Get additional data for each IP
        result = []
        for ip, count in top_ips:
            # Get latest click for this IP
            latest_click = (
                db(db.analytics.ip_address == ip)
                .select(orderby=~db.analytics.clicked_on, limitby=(0, 1))
                .first()
            )

            if latest_click:
                result.append(
                    {
                        "ip_address": ip,
                        "click_count": count,
                        "country": latest_click.country,
                        "city": latest_click.city,
                        "last_seen": latest_click.clicked_on,
                    }
                )

        return result

    @staticmethod
    def cleanup_old_analytics(days=90):
        """Remove analytics data older than specified days"""
        cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=days)

        # Delete old records
        deleted = db(db.analytics.clicked_on < cutoff_date).delete()
        db.commit()

        return deleted
