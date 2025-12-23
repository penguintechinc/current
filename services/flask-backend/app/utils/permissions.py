"""Permission utilities for team-based access control."""

from functools import wraps
from typing import Optional

from flask import g, jsonify

from ..models import get_db, VALID_TEAM_ROLES


def get_user_team_role(user_id: int, team_id: int) -> Optional[str]:
    """Get user's role in a team.

    Args:
        user_id: User ID.
        team_id: Team ID.

    Returns:
        Role string or None if not a member.
    """
    db = get_db()
    membership = db(
        (db.team_members.team_id == team_id) &
        (db.team_members.user_id == user_id)
    ).select().first()

    return membership.role if membership else None


def team_role_required(*allowed_roles: str):
    """Decorator to require team membership with specific roles.

    The decorated function must have team_id or team_slug as first argument
    or in request args/json.

    Args:
        allowed_roles: Tuple of allowed role names.

    Usage:
        @team_role_required("owner", "admin")
        def manage_team(team_id):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            from flask import request

            db = get_db()
            user_id = g.current_user["id"]

            # Get team_id from various sources
            team_id = kwargs.get("team_id")
            team_slug = kwargs.get("team_slug")

            if not team_id and not team_slug:
                # Try request args
                team_id = request.args.get("team_id", type=int)
                team_slug = request.args.get("team_slug")

            if not team_id and not team_slug:
                # Try request JSON
                data = request.get_json(silent=True) or {}
                team_id = data.get("team_id")
                team_slug = data.get("team_slug")

            # Resolve team_slug to team_id
            if team_slug and not team_id:
                team = db(db.teams.slug == team_slug).select().first()
                if not team:
                    return jsonify({"error": "Team not found"}), 404
                team_id = team.id

            if not team_id:
                return jsonify({"error": "team_id or team_slug required"}), 400

            # Check membership
            role = get_user_team_role(user_id, team_id)
            if not role:
                return jsonify({"error": "Not a team member"}), 403

            if role not in allowed_roles:
                return jsonify({
                    "error": f"Requires one of: {', '.join(allowed_roles)}",
                    "your_role": role
                }), 403

            # Store team info in g
            team = db(db.teams.id == team_id).select().first()
            g.team = team.as_dict() if team else None
            g.team_role = role

            return f(*args, **kwargs)
        return decorated
    return decorator


def can_manage_url(user_id: int, url_id: int) -> bool:
    """Check if user can edit/delete a URL.

    Args:
        user_id: User ID.
        url_id: URL ID.

    Returns:
        True if user can manage the URL.
    """
    db = get_db()

    url = db(db.short_urls.id == url_id).select().first()
    if not url:
        return False

    # Owner of URL can always manage
    if url.created_by == user_id:
        return True

    # Team admin/owner can manage all team URLs
    role = get_user_team_role(user_id, url.team_id)
    return role in ("owner", "admin")


def can_manage_collection(user_id: int, collection_id: int) -> bool:
    """Check if user can edit/delete a collection.

    Args:
        user_id: User ID.
        collection_id: Collection ID.

    Returns:
        True if user can manage the collection.
    """
    db = get_db()

    collection = db(db.collections.id == collection_id).select().first()
    if not collection:
        return False

    # Team admin/owner can manage collections
    role = get_user_team_role(user_id, collection.team_id)
    return role in ("owner", "admin")


def check_plan_limit(team_id: int, resource: str) -> tuple[bool, str]:
    """Check if team has reached plan limits.

    Args:
        team_id: Team ID.
        resource: Resource type ("domains", "urls", "members").

    Returns:
        Tuple of (allowed, message).
    """
    db = get_db()
    team = db(db.teams.id == team_id).select().first()

    if not team:
        return False, "Team not found"

    if resource == "domains":
        current = db(db.team_domains.team_id == team_id).count()
        limit = team.max_domains
        if current >= limit:
            return False, f"Domain limit reached ({limit}). Upgrade your plan."
        return True, ""

    if resource == "urls":
        from datetime import datetime, timedelta
        # Count URLs created this month
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
        current = db(
            (db.short_urls.team_id == team_id) &
            (db.short_urls.created_at >= month_start)
        ).count()
        limit = team.max_urls_per_month
        if current >= limit:
            return False, f"Monthly URL limit reached ({limit}). Upgrade your plan."
        return True, ""

    if resource == "members":
        current = db(db.team_members.team_id == team_id).count()
        # Plan-based limits
        limits = {"free": 1, "pro": 5, "enterprise": 999}
        limit = limits.get(team.plan, 1)
        if current >= limit:
            return False, f"Team member limit reached ({limit}). Upgrade your plan."
        return True, ""

    return True, ""
