"""Real-time analytics endpoints using Server-Sent Events (SSE).

Provides live click data streaming for dashboards.
"""

import json
import logging
import time
from datetime import datetime
from typing import Generator, Optional

from flask import Blueprint, Response, g, jsonify, request, stream_with_context

from ..middleware import token_required
from ..models import get_db

logger = logging.getLogger(__name__)

realtime_bp = Blueprint("realtime", __name__)


def _get_redis_client():
    """Get Redis client from app extensions."""
    from flask import current_app
    if hasattr(current_app, "extensions"):
        return current_app.extensions.get("redis")
    return None


def _format_sse_message(data: dict, event: Optional[str] = None) -> str:
    """Format data as SSE message.

    Args:
        data: Data to send.
        event: Optional event name.

    Returns:
        SSE formatted string.
    """
    msg = ""
    if event:
        msg += f"event: {event}\n"
    msg += f"data: {json.dumps(data)}\n\n"
    return msg


@realtime_bp.route("/stream/<int:url_id>", methods=["GET"])
@token_required
def stream_url_clicks(url_id: int):
    """Stream real-time clicks for a specific URL.

    Uses Server-Sent Events to push live click data to the client.

    Args:
        url_id: Short URL ID.

    Returns:
        SSE stream of click events.
    """
    db = get_db()
    user_id = g.current_user["id"]

    # Check URL exists and user has access
    url = db(db.short_urls.id == url_id).select().first()
    if not url:
        return jsonify({"error": "URL not found"}), 404

    # Check team membership
    membership = db(
        (db.team_members.team_id == url.team_id)
        & (db.team_members.user_id == user_id)
    ).select().first()

    if not membership:
        return jsonify({"error": "Access denied"}), 403

    def generate() -> Generator[str, None, None]:
        """Generate SSE events for URL clicks."""
        redis = _get_redis_client()
        last_count = 0

        # Send initial data
        yield _format_sse_message(
            {"type": "connected", "url_id": url_id, "timestamp": time.time()},
            event="connection",
        )

        while True:
            try:
                if redis:
                    # Get current click count from Redis
                    current_count = int(redis.get(f"rt:clicks:{url_id}") or 0)

                    if current_count > last_count:
                        # New clicks detected
                        new_clicks = current_count - last_count
                        last_count = current_count

                        # Get recent geo/device data
                        today = datetime.utcnow().strftime("%Y%m%d")
                        geo_data = redis.hgetall(f"rt:geo:{url_id}:{today}") or {}
                        device_data = redis.hgetall(f"rt:device:{url_id}:{today}") or {}

                        yield _format_sse_message(
                            {
                                "type": "clicks",
                                "url_id": url_id,
                                "total_clicks": current_count,
                                "new_clicks": new_clicks,
                                "geo": geo_data,
                                "devices": device_data,
                                "timestamp": time.time(),
                            },
                            event="update",
                        )

                    # Get unique visitors from HyperLogLog
                    today = datetime.utcnow().strftime("%Y%m%d")
                    unique_count = redis.pfcount(f"unique:{url_id}:{today}") or 0

                    yield _format_sse_message(
                        {
                            "type": "stats",
                            "url_id": url_id,
                            "total_clicks": current_count,
                            "unique_visitors": unique_count,
                            "timestamp": time.time(),
                        },
                        event="stats",
                    )
                else:
                    # Fallback to database query
                    url_record = db(db.short_urls.id == url_id).select(
                        db.short_urls.click_count
                    ).first()

                    if url_record:
                        yield _format_sse_message(
                            {
                                "type": "stats",
                                "url_id": url_id,
                                "total_clicks": url_record.click_count or 0,
                                "timestamp": time.time(),
                            },
                            event="stats",
                        )

                # Send heartbeat every 30 seconds
                yield _format_sse_message(
                    {"type": "heartbeat", "timestamp": time.time()},
                    event="heartbeat",
                )

                # Sleep for 2 seconds between updates
                time.sleep(2)

            except GeneratorExit:
                logger.debug(f"SSE client disconnected for URL {url_id}")
                break
            except Exception as e:
                logger.error(f"SSE stream error: {e}")
                yield _format_sse_message(
                    {"type": "error", "message": str(e)},
                    event="error",
                )
                break

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@realtime_bp.route("/stream/team/<int:team_id>", methods=["GET"])
@token_required
def stream_team_clicks(team_id: int):
    """Stream real-time clicks for all team URLs.

    Args:
        team_id: Team ID.

    Returns:
        SSE stream of click events.
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

    # Get team's URL IDs
    team_urls = db(db.short_urls.team_id == team_id).select(db.short_urls.id)
    url_ids = [u.id for u in team_urls]

    def generate() -> Generator[str, None, None]:
        """Generate SSE events for team clicks."""
        redis = _get_redis_client()
        last_counts = {uid: 0 for uid in url_ids}

        # Send initial data
        yield _format_sse_message(
            {
                "type": "connected",
                "team_id": team_id,
                "url_count": len(url_ids),
                "timestamp": time.time(),
            },
            event="connection",
        )

        while True:
            try:
                if redis and url_ids:
                    total_clicks = 0
                    total_new = 0
                    updates = []

                    for url_id in url_ids:
                        current = int(redis.get(f"rt:clicks:{url_id}") or 0)
                        total_clicks += current

                        if current > last_counts.get(url_id, 0):
                            new = current - last_counts.get(url_id, 0)
                            total_new += new
                            last_counts[url_id] = current
                            updates.append({
                                "url_id": url_id,
                                "clicks": current,
                                "new": new,
                            })

                    if updates:
                        yield _format_sse_message(
                            {
                                "type": "updates",
                                "team_id": team_id,
                                "total_clicks": total_clicks,
                                "new_clicks": total_new,
                                "url_updates": updates,
                                "timestamp": time.time(),
                            },
                            event="update",
                        )

                    yield _format_sse_message(
                        {
                            "type": "stats",
                            "team_id": team_id,
                            "total_clicks": total_clicks,
                            "url_count": len(url_ids),
                            "timestamp": time.time(),
                        },
                        event="stats",
                    )
                else:
                    # Fallback to database
                    total = db(db.short_urls.team_id == team_id).select(
                        db.short_urls.click_count.sum().with_alias("total")
                    ).first()

                    yield _format_sse_message(
                        {
                            "type": "stats",
                            "team_id": team_id,
                            "total_clicks": total.total or 0 if total else 0,
                            "timestamp": time.time(),
                        },
                        event="stats",
                    )

                # Heartbeat
                yield _format_sse_message(
                    {"type": "heartbeat", "timestamp": time.time()},
                    event="heartbeat",
                )

                time.sleep(2)

            except GeneratorExit:
                logger.debug(f"SSE client disconnected for team {team_id}")
                break
            except Exception as e:
                logger.error(f"SSE team stream error: {e}")
                yield _format_sse_message(
                    {"type": "error", "message": str(e)},
                    event="error",
                )
                break

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@realtime_bp.route("/snapshot/<int:url_id>", methods=["GET"])
@token_required
def get_realtime_snapshot(url_id: int):
    """Get current real-time stats snapshot (non-streaming).

    Args:
        url_id: Short URL ID.

    Returns:
        JSON with current real-time stats.
    """
    db = get_db()
    user_id = g.current_user["id"]

    # Check URL exists and user has access
    url = db(db.short_urls.id == url_id).select().first()
    if not url:
        return jsonify({"error": "URL not found"}), 404

    # Check team membership
    membership = db(
        (db.team_members.team_id == url.team_id)
        & (db.team_members.user_id == user_id)
    ).select().first()

    if not membership:
        return jsonify({"error": "Access denied"}), 403

    redis = _get_redis_client()
    today = datetime.utcnow().strftime("%Y%m%d")

    if redis:
        # Get real-time data from Redis
        total_clicks = int(redis.get(f"rt:clicks:{url_id}") or 0)
        unique_visitors = redis.pfcount(f"unique:{url_id}:{today}") or 0
        geo_data = redis.hgetall(f"rt:geo:{url_id}:{today}") or {}
        device_data = redis.hgetall(f"rt:device:{url_id}:{today}") or {}

        # Get minute-level data for last hour
        now = int(time.time())
        minute_data = []
        for i in range(60):
            minute_ts = ((now - i * 60) // 60) * 60
            key = f"rt:clicks:{url_id}:min:{minute_ts}"
            count = int(redis.get(key) or 0)
            minute_data.append({
                "timestamp": minute_ts,
                "clicks": count,
            })

        return jsonify({
            "url_id": url_id,
            "total_clicks": total_clicks,
            "unique_visitors_today": unique_visitors,
            "geo_breakdown": {k: int(v) for k, v in geo_data.items()},
            "device_breakdown": {k: int(v) for k, v in device_data.items()},
            "minute_timeline": list(reversed(minute_data)),
            "timestamp": time.time(),
        })
    else:
        # Fallback to database
        return jsonify({
            "url_id": url_id,
            "total_clicks": url.click_count or 0,
            "timestamp": time.time(),
            "realtime_disabled": True,
        })
