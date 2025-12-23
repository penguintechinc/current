"""Redirect endpoint for short URL resolution."""

import time
from flask import Blueprint, redirect, request, abort, jsonify

from ..dto import ClickEvent
from ..services.cache_service import get_cache_service
from ..services.redirect_service import (
    get_redirect_service,
    parse_user_agent,
    detect_device_type,
    is_bot,
    extract_referrer_domain,
)

redirect_bp = Blueprint("redirect", __name__)


@redirect_bp.route("/<slug>", methods=["GET"])
def handle_redirect(slug: str):
    """Handle short URL redirect.

    This is the performance-critical path. Uses 3-layer cache:
    L1 (in-memory) -> L2 (Redis) -> L3 (PostgreSQL)

    Args:
        slug: Short URL code.

    Returns:
        302 redirect to original URL or 404 if not found.
    """
    # Get domain from Host header
    host = request.host.split(":")[0]  # Remove port if present

    # Resolve URL using 3-layer cache
    service = get_redirect_service()
    cached_url = service.resolve_url(host, slug)

    if cached_url is None:
        abort(404)

    # Check if password protected
    if cached_url.is_password_protected():
        # TODO: Implement password verification page
        # For now, just redirect
        pass

    # Determine redirect URL based on device
    ua_string = request.headers.get("User-Agent", "")
    device_type = detect_device_type(ua_string)
    redirect_url = cached_url.get_redirect_url(device_type)

    # Track click asynchronously (non-blocking)
    _track_click_async(cached_url, ua_string, device_type)

    # Return redirect
    return redirect(redirect_url, code=302)


def _track_click_async(cached_url, ua_string: str, device_type: str) -> None:
    """Track click event asynchronously.

    Args:
        cached_url: The resolved CachedURL.
        ua_string: User agent string.
        device_type: Detected device type.
    """
    try:
        # Get request metadata
        ip = request.remote_addr or ""
        referrer = request.headers.get("Referer", "")

        # Hash IP for privacy
        ip_hash = ClickEvent.hash_ip(ip)

        # Parse user agent (cached)
        _, browser, browser_ver, os_name, os_ver = parse_user_agent(ua_string)

        # Check if bot
        bot = is_bot(ua_string)

        # Extract referrer domain
        referrer_domain = extract_referrer_domain(referrer)

        # Check if unique visitor today
        cache = get_cache_service()
        today = time.strftime("%Y-%m-%d")
        is_unique = cache.add_unique_visitor(cached_url.id, ip_hash, today)

        # Create click event
        event = ClickEvent(
            url_id=cached_url.id,
            timestamp=time.time(),
            ip_hash=ip_hash,
            country="",  # Will be populated by geo service
            region="",
            city="",
            device_type=device_type,
            browser=browser,
            browser_version=browser_ver,
            os=os_name,
            os_version=os_ver,
            referrer=referrer[:500] if referrer else "",
            referrer_domain=referrer_domain,
            is_unique=is_unique,
            is_bot=bot,
        )

        # Add to async buffer
        service = get_redirect_service()
        service.track_click(event)

    except Exception as e:
        # Never let click tracking break the redirect
        import logging
        logging.getLogger(__name__).warning(f"Click tracking error: {e}")


@redirect_bp.route("/<slug>/info", methods=["GET"])
def get_url_info(slug: str):
    """Get short URL information (for preview).

    Args:
        slug: Short URL code.

    Returns:
        JSON with URL info or 404.
    """
    host = request.host.split(":")[0]

    service = get_redirect_service()
    cached_url = service.resolve_url(host, slug)

    if cached_url is None:
        abort(404)

    # Don't expose password hash or internal fields
    return jsonify({
        "slug": cached_url.slug,
        "domain": cached_url.domain,
        "original_url": cached_url.original_url,
        "has_password": cached_url.is_password_protected(),
        "is_active": cached_url.is_active,
    })
