"""Analytics API endpoints for URL shortener.

Provides endpoints for:
- URL summary statistics
- Click timeline data
- Geographic breakdown
- Device/browser breakdown
- Referrer analysis
- Team-wide statistics
"""

import json
from datetime import date, datetime, timedelta
from typing import Optional

from flask import Blueprint, g, jsonify, request

from ..middleware import token_required
from ..models import get_db
from ..utils.permissions import can_manage_url

analytics_bp = Blueprint("analytics", __name__)


def _parse_date_range(
    start: Optional[str],
    end: Optional[str],
    default_days: int = 7,
) -> tuple[date, date]:
    """Parse date range from request parameters.

    Args:
        start: Start date string (YYYY-MM-DD).
        end: End date string (YYYY-MM-DD).
        default_days: Default range if not specified.

    Returns:
        Tuple of (start_date, end_date).
    """
    today = date.today()

    if end:
        try:
            end_date = datetime.strptime(end, "%Y-%m-%d").date()
        except ValueError:
            end_date = today
    else:
        end_date = today

    if start:
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d").date()
        except ValueError:
            start_date = end_date - timedelta(days=default_days)
    else:
        start_date = end_date - timedelta(days=default_days)

    return start_date, end_date


@analytics_bp.route("/urls/<int:url_id>/stats", methods=["GET"])
@token_required
def get_url_stats(url_id: int):
    """Get summary statistics for a URL.

    Args:
        url_id: Short URL ID.

    Query params:
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)

    Returns:
        JSON with total clicks, unique visitors, etc.
    """
    db = get_db()
    user_id = g.current_user["id"]

    # Check access
    url = db(db.short_urls.id == url_id).select().first()
    if not url:
        return jsonify({"error": "URL not found"}), 404

    if not can_manage_url(user_id, url):
        return jsonify({"error": "Access denied"}), 403

    # Parse date range
    start_date, end_date = _parse_date_range(
        request.args.get("start"),
        request.args.get("end"),
    )

    # Get aggregated stats
    stats = db(
        (db.daily_stats.short_url_id == url_id)
        & (db.daily_stats.date >= start_date)
        & (db.daily_stats.date <= end_date)
    ).select()

    total_clicks = 0
    total_unique = 0

    for stat in stats:
        total_clicks += stat.clicks or 0
        total_unique += stat.unique_clicks or 0

    # Get all-time stats from URL record
    all_time_clicks = url.click_count or 0

    # Get average daily clicks
    days_in_range = (end_date - start_date).days + 1
    avg_daily = total_clicks / days_in_range if days_in_range > 0 else 0

    return jsonify({
        "url_id": url_id,
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "total_clicks": total_clicks,
        "unique_visitors": total_unique,
        "all_time_clicks": all_time_clicks,
        "average_daily_clicks": round(avg_daily, 2),
    })


@analytics_bp.route("/urls/<int:url_id>/clicks", methods=["GET"])
@token_required
def get_click_timeline(url_id: int):
    """Get click timeline data for charts.

    Args:
        url_id: Short URL ID.

    Query params:
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)
        granularity: "day" or "hour" (default: day)

    Returns:
        JSON array of {date, clicks, unique} objects.
    """
    db = get_db()
    user_id = g.current_user["id"]

    # Check access
    url = db(db.short_urls.id == url_id).select().first()
    if not url:
        return jsonify({"error": "URL not found"}), 404

    if not can_manage_url(user_id, url):
        return jsonify({"error": "Access denied"}), 403

    # Parse date range
    start_date, end_date = _parse_date_range(
        request.args.get("start"),
        request.args.get("end"),
    )

    granularity = request.args.get("granularity", "day")

    if granularity == "hour":
        # Get hourly data from click_events (limited to 48 hours)
        max_hours = 48
        start_dt = datetime.combine(end_date, datetime.min.time()) - timedelta(
            hours=max_hours
        )

        clicks = db(
            (db.click_events.short_url_id == url_id)
            & (db.click_events.clicked_at >= start_dt)
        ).select(orderby=db.click_events.clicked_at)

        # Group by hour
        hourly = {}
        for click in clicks:
            hour_key = click.clicked_at.strftime("%Y-%m-%d %H:00")
            if hour_key not in hourly:
                hourly[hour_key] = {"clicks": 0, "unique_ips": set()}
            hourly[hour_key]["clicks"] += 1
            if click.ip_hash:
                hourly[hour_key]["unique_ips"].add(click.ip_hash)

        timeline = [
            {
                "datetime": k,
                "clicks": v["clicks"],
                "unique": len(v["unique_ips"]),
            }
            for k, v in sorted(hourly.items())
        ]

    else:
        # Get daily data from daily_stats
        stats = db(
            (db.daily_stats.short_url_id == url_id)
            & (db.daily_stats.date >= start_date)
            & (db.daily_stats.date <= end_date)
        ).select(orderby=db.daily_stats.date)

        # Fill in missing days with zeros
        timeline = []
        current = start_date
        stats_dict = {s.date: s for s in stats}

        while current <= end_date:
            if current in stats_dict:
                s = stats_dict[current]
                timeline.append({
                    "date": current.isoformat(),
                    "clicks": s.clicks or 0,
                    "unique": s.unique_clicks or 0,
                })
            else:
                timeline.append({
                    "date": current.isoformat(),
                    "clicks": 0,
                    "unique": 0,
                })
            current += timedelta(days=1)

    return jsonify({"timeline": timeline})


@analytics_bp.route("/urls/<int:url_id>/geo", methods=["GET"])
@token_required
def get_geo_breakdown(url_id: int):
    """Get geographic breakdown of clicks.

    Args:
        url_id: Short URL ID.

    Query params:
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)

    Returns:
        JSON with country breakdown.
    """
    db = get_db()
    user_id = g.current_user["id"]

    # Check access
    url = db(db.short_urls.id == url_id).select().first()
    if not url:
        return jsonify({"error": "URL not found"}), 404

    if not can_manage_url(user_id, url):
        return jsonify({"error": "Access denied"}), 403

    # Parse date range
    start_date, end_date = _parse_date_range(
        request.args.get("start"),
        request.args.get("end"),
    )

    # Get aggregated stats
    stats = db(
        (db.daily_stats.short_url_id == url_id)
        & (db.daily_stats.date >= start_date)
        & (db.daily_stats.date <= end_date)
    ).select()

    # Merge country data
    countries = {}
    for stat in stats:
        if stat.by_country:
            try:
                country_data = (
                    json.loads(stat.by_country)
                    if isinstance(stat.by_country, str)
                    else stat.by_country
                )
                for country, count in country_data.items():
                    countries[country] = countries.get(country, 0) + count
            except (json.JSONDecodeError, TypeError):
                pass

    # Sort by count
    sorted_countries = sorted(
        countries.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    return jsonify({
        "countries": [
            {"code": code, "clicks": count}
            for code, count in sorted_countries
        ],
        "total_countries": len(countries),
    })


@analytics_bp.route("/urls/<int:url_id>/devices", methods=["GET"])
@token_required
def get_device_breakdown(url_id: int):
    """Get device/browser/OS breakdown of clicks.

    Args:
        url_id: Short URL ID.

    Query params:
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)

    Returns:
        JSON with device, browser, and OS breakdown.
    """
    db = get_db()
    user_id = g.current_user["id"]

    # Check access
    url = db(db.short_urls.id == url_id).select().first()
    if not url:
        return jsonify({"error": "URL not found"}), 404

    if not can_manage_url(user_id, url):
        return jsonify({"error": "Access denied"}), 403

    # Parse date range
    start_date, end_date = _parse_date_range(
        request.args.get("start"),
        request.args.get("end"),
    )

    # Get aggregated stats
    stats = db(
        (db.daily_stats.short_url_id == url_id)
        & (db.daily_stats.date >= start_date)
        & (db.daily_stats.date <= end_date)
    ).select()

    # Merge device and browser data
    devices = {}
    browsers = {}

    for stat in stats:
        # Device breakdown
        if stat.by_device:
            try:
                device_data = (
                    json.loads(stat.by_device)
                    if isinstance(stat.by_device, str)
                    else stat.by_device
                )
                for device, count in device_data.items():
                    devices[device] = devices.get(device, 0) + count
            except (json.JSONDecodeError, TypeError):
                pass

        # Browser breakdown
        if stat.by_browser:
            try:
                browser_data = (
                    json.loads(stat.by_browser)
                    if isinstance(stat.by_browser, str)
                    else stat.by_browser
                )
                for browser, count in browser_data.items():
                    browsers[browser] = browsers.get(browser, 0) + count
            except (json.JSONDecodeError, TypeError):
                pass

    return jsonify({
        "devices": [
            {"type": d, "clicks": c}
            for d, c in sorted(devices.items(), key=lambda x: x[1], reverse=True)
        ],
        "browsers": [
            {"name": b, "clicks": c}
            for b, c in sorted(browsers.items(), key=lambda x: x[1], reverse=True)
        ],
    })


@analytics_bp.route("/urls/<int:url_id>/referrers", methods=["GET"])
@token_required
def get_referrer_breakdown(url_id: int):
    """Get referrer domain breakdown of clicks.

    Args:
        url_id: Short URL ID.

    Query params:
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)

    Returns:
        JSON with top referrers.
    """
    db = get_db()
    user_id = g.current_user["id"]

    # Check access
    url = db(db.short_urls.id == url_id).select().first()
    if not url:
        return jsonify({"error": "URL not found"}), 404

    if not can_manage_url(user_id, url):
        return jsonify({"error": "Access denied"}), 403

    # Parse date range
    start_date, end_date = _parse_date_range(
        request.args.get("start"),
        request.args.get("end"),
    )

    # Get aggregated stats
    stats = db(
        (db.daily_stats.short_url_id == url_id)
        & (db.daily_stats.date >= start_date)
        & (db.daily_stats.date <= end_date)
    ).select()

    # Merge referrer data
    referrers = {}
    for stat in stats:
        if stat.by_referrer:
            try:
                referrer_data = (
                    json.loads(stat.by_referrer)
                    if isinstance(stat.by_referrer, str)
                    else stat.by_referrer
                )
                for referrer, count in referrer_data.items():
                    referrers[referrer] = referrers.get(referrer, 0) + count
            except (json.JSONDecodeError, TypeError):
                pass

    # Sort by count
    sorted_referrers = sorted(
        referrers.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    return jsonify({
        "referrers": [
            {"domain": domain, "clicks": count}
            for domain, count in sorted_referrers[:50]  # Top 50
        ],
    })


@analytics_bp.route("/teams/<int:team_id>/stats", methods=["GET"])
@token_required
def get_team_stats(team_id: int):
    """Get team-wide analytics summary.

    Args:
        team_id: Team ID.

    Query params:
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)

    Returns:
        JSON with team-wide statistics.
    """
    db = get_db()
    user_id = g.current_user["id"]

    # Check team membership
    membership = db(
        (db.team_members.team_id == team_id)
        & (db.team_members.user_id == user_id)
    ).select().first()

    if not membership:
        return jsonify({"error": "Access denied"}), 403

    # Parse date range
    start_date, end_date = _parse_date_range(
        request.args.get("start"),
        request.args.get("end"),
    )

    # Get team's URLs
    team_urls = db(db.short_urls.team_id == team_id).select(db.short_urls.id)
    url_ids = [u.id for u in team_urls]

    if not url_ids:
        return jsonify({
            "team_id": team_id,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "total_urls": 0,
            "total_clicks": 0,
            "unique_visitors": 0,
            "top_urls": [],
        })

    # Get aggregated stats for all team URLs
    stats = db(
        (db.daily_stats.short_url_id.belongs(url_ids))
        & (db.daily_stats.date >= start_date)
        & (db.daily_stats.date <= end_date)
    ).select()

    # Calculate totals
    total_clicks = 0
    total_unique = 0
    url_clicks = {}

    for stat in stats:
        total_clicks += stat.clicks or 0
        total_unique += stat.unique_clicks or 0
        url_clicks[stat.short_url_id] = (
            url_clicks.get(stat.short_url_id, 0) + (stat.clicks or 0)
        )

    # Get top URLs
    top_url_ids = sorted(url_clicks.items(), key=lambda x: x[1], reverse=True)[:10]
    top_urls = []

    for url_id, clicks in top_url_ids:
        url = db(db.short_urls.id == url_id).select(
            db.short_urls.slug,
            db.short_urls.original_url,
            db.domains.domain,
            left=db.domains.on(db.short_urls.domain_id == db.domains.id),
        ).first()

        if url:
            top_urls.append({
                "id": url_id,
                "slug": url.short_urls.slug if url.short_urls else None,
                "domain": url.domains.domain if url.domains else None,
                "original_url": url.short_urls.original_url if url.short_urls else None,
                "clicks": clicks,
            })

    return jsonify({
        "team_id": team_id,
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "total_urls": len(url_ids),
        "total_clicks": total_clicks,
        "unique_visitors": total_unique,
        "top_urls": top_urls,
    })
