"""URL CRUD endpoints for short URL management."""

import secrets
import string
from datetime import datetime
from typing import Optional

from flask import Blueprint, jsonify, request, g

from ..middleware import token_required
from ..models import get_db, PLAN_DOMAIN_LIMITS
from ..services.cache_service import get_cache_service

urls_bp = Blueprint("urls", __name__)


def generate_slug(length: int = 7) -> str:
    """Generate a random short URL slug.

    Args:
        length: Length of the slug (default 7).

    Returns:
        Random alphanumeric string.
    """
    # Use URL-safe characters (no ambiguous chars like 0/O, 1/l)
    alphabet = string.ascii_lowercase + string.ascii_uppercase + string.digits
    alphabet = alphabet.replace("0", "").replace("O", "").replace("l", "").replace("1", "")
    return "".join(secrets.choice(alphabet) for _ in range(length))


def is_slug_available(db, domain_id: int, slug: str) -> bool:
    """Check if a slug is available for a domain.

    Args:
        db: Database connection.
        domain_id: Domain ID.
        slug: Slug to check.

    Returns:
        True if slug is available.
    """
    existing = db(
        (db.short_urls.domain_id == domain_id) &
        (db.short_urls.slug == slug)
    ).count()
    return existing == 0


@urls_bp.route("", methods=["GET"])
@token_required
def list_urls():
    """List short URLs for the current user's teams.

    Query params:
        team_id: Filter by team ID
        collection_id: Filter by collection ID
        page: Page number (default 1)
        per_page: Items per page (default 20, max 100)
        search: Search in title, slug, original_url
        archived: Include archived URLs (default false)

    Returns:
        JSON list of URLs with pagination.
    """
    db = get_db()
    user_id = g.current_user["id"]

    # Get query params
    team_id = request.args.get("team_id", type=int)
    collection_id = request.args.get("collection_id", type=int)
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    search = request.args.get("search", "")
    include_archived = request.args.get("archived", "false").lower() == "true"

    # Get user's teams
    user_teams = db(db.team_members.user_id == user_id).select(db.team_members.team_id)
    team_ids = [t.team_id for t in user_teams]

    if not team_ids:
        return jsonify({"urls": [], "total": 0, "page": page, "per_page": per_page})

    # Build query
    query = db.short_urls.team_id.belongs(team_ids)

    if team_id:
        if team_id not in team_ids:
            return jsonify({"error": "Access denied to this team"}), 403
        query &= (db.short_urls.team_id == team_id)

    if collection_id:
        query &= (db.short_urls.collection_id == collection_id)

    if not include_archived:
        query &= (db.short_urls.archived == False)

    if search:
        search_query = (
            db.short_urls.title.contains(search) |
            db.short_urls.slug.contains(search) |
            db.short_urls.original_url.contains(search)
        )
        query &= search_query

    # Get total count
    total = db(query).count()

    # Get paginated results with domain info
    offset = (page - 1) * per_page
    urls = db(query).select(
        db.short_urls.ALL,
        db.domains.domain,
        left=db.domains.on(db.short_urls.domain_id == db.domains.id),
        orderby=~db.short_urls.created_at,
        limitby=(offset, offset + per_page),
    )

    # Format response
    result = []
    for row in urls:
        url_dict = row.short_urls.as_dict()
        url_dict["domain"] = row.domains.domain if row.domains else None
        url_dict["short_url"] = f"https://{row.domains.domain}/{row.short_urls.slug}" if row.domains else None
        result.append(url_dict)

    return jsonify({
        "urls": result,
        "total": total,
        "page": page,
        "per_page": per_page,
    })


@urls_bp.route("", methods=["POST"])
@token_required
def create_url():
    """Create a new short URL.

    Request body:
        original_url: Required - URL to shorten
        team_id: Required - Team to create URL in
        domain_id: Optional - Domain to use (defaults to team's default)
        collection_id: Optional - Collection to add URL to
        slug: Optional - Custom slug (auto-generated if not provided)
        title: Optional - Title for the URL
        description: Optional - Description
        tags: Optional - List of tags
        password: Optional - Password to protect the URL
        expires_at: Optional - Expiration datetime (ISO format)
        max_clicks: Optional - Maximum number of clicks
        ios_url: Optional - iOS-specific redirect
        android_url: Optional - Android-specific redirect

    Returns:
        Created URL object.
    """
    db = get_db()
    user_id = g.current_user["id"]
    data = request.get_json() or {}

    # Validate required fields
    original_url = data.get("original_url")
    team_id = data.get("team_id")

    if not original_url:
        return jsonify({"error": "original_url is required"}), 400
    if not team_id:
        return jsonify({"error": "team_id is required"}), 400

    # Check team membership
    membership = db(
        (db.team_members.team_id == team_id) &
        (db.team_members.user_id == user_id)
    ).select().first()

    if not membership:
        return jsonify({"error": "Access denied to this team"}), 403

    if membership.role == "viewer":
        return jsonify({"error": "Viewers cannot create URLs"}), 403

    # Get domain
    domain_id = data.get("domain_id")
    if not domain_id:
        # Get team's default domain
        team_domain = db(
            (db.team_domains.team_id == team_id) &
            (db.team_domains.is_default == True)
        ).select().first()
        if team_domain:
            domain_id = team_domain.domain_id
        else:
            # Get first team domain
            team_domain = db(db.team_domains.team_id == team_id).select().first()
            if team_domain:
                domain_id = team_domain.domain_id
            else:
                return jsonify({"error": "No domain configured for this team"}), 400

    # Validate domain belongs to team
    domain_check = db(
        (db.team_domains.team_id == team_id) &
        (db.team_domains.domain_id == domain_id)
    ).select().first()
    if not domain_check:
        return jsonify({"error": "Domain not available for this team"}), 400

    # Generate or validate slug
    slug = data.get("slug")
    if slug:
        if not is_slug_available(db, domain_id, slug):
            return jsonify({"error": "Slug already in use"}), 409
    else:
        # Generate unique slug
        for _ in range(10):
            slug = generate_slug()
            if is_slug_available(db, domain_id, slug):
                break
        else:
            return jsonify({"error": "Could not generate unique slug"}), 500

    # Parse expiration
    expires_at = None
    if data.get("expires_at"):
        try:
            expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": "Invalid expires_at format"}), 400

    # Hash password if provided
    password_hash = None
    if data.get("password"):
        import bcrypt
        password_hash = bcrypt.hashpw(
            data["password"].encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

    # Create URL
    try:
        url_id = db.short_urls.insert(
            domain_id=domain_id,
            team_id=team_id,
            collection_id=data.get("collection_id"),
            created_by=user_id,
            slug=slug,
            original_url=original_url,
            title=data.get("title"),
            description=data.get("description"),
            tags=data.get("tags", []),
            password=password_hash,
            expires_at=expires_at,
            max_clicks=data.get("max_clicks"),
            ios_url=data.get("ios_url"),
            android_url=data.get("android_url"),
            utm_source=data.get("utm_source"),
            utm_medium=data.get("utm_medium"),
            utm_campaign=data.get("utm_campaign"),
        )
        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Failed to create URL: {str(e)}"}), 500

    # Get created URL with domain
    created = db(db.short_urls.id == url_id).select().first()
    domain = db(db.domains.id == domain_id).select().first()

    result = created.as_dict()
    result["domain"] = domain.domain if domain else None
    result["short_url"] = f"https://{domain.domain}/{slug}" if domain else None

    return jsonify(result), 201


@urls_bp.route("/<int:url_id>", methods=["GET"])
@token_required
def get_url(url_id: int):
    """Get a single short URL.

    Args:
        url_id: URL database ID.

    Returns:
        URL object with domain info.
    """
    db = get_db()
    user_id = g.current_user["id"]

    # Get URL
    url = db(db.short_urls.id == url_id).select().first()
    if not url:
        return jsonify({"error": "URL not found"}), 404

    # Check access
    membership = db(
        (db.team_members.team_id == url.team_id) &
        (db.team_members.user_id == user_id)
    ).select().first()

    if not membership:
        return jsonify({"error": "Access denied"}), 403

    # Get domain
    domain = db(db.domains.id == url.domain_id).select().first()

    result = url.as_dict()
    result["domain"] = domain.domain if domain else None
    result["short_url"] = f"https://{domain.domain}/{url.slug}" if domain else None

    return jsonify(result)


@urls_bp.route("/<int:url_id>", methods=["PUT"])
@token_required
def update_url(url_id: int):
    """Update a short URL.

    Args:
        url_id: URL database ID.

    Request body:
        Any fields from create except domain_id and slug.

    Returns:
        Updated URL object.
    """
    db = get_db()
    user_id = g.current_user["id"]
    data = request.get_json() or {}

    # Get URL
    url = db(db.short_urls.id == url_id).select().first()
    if not url:
        return jsonify({"error": "URL not found"}), 404

    # Check access (must be creator, admin, or owner)
    membership = db(
        (db.team_members.team_id == url.team_id) &
        (db.team_members.user_id == user_id)
    ).select().first()

    if not membership:
        return jsonify({"error": "Access denied"}), 403

    if membership.role == "viewer":
        return jsonify({"error": "Viewers cannot update URLs"}), 403

    if membership.role == "member" and url.created_by != user_id:
        return jsonify({"error": "Members can only update their own URLs"}), 403

    # Allowed update fields
    allowed_fields = {
        "original_url", "title", "description", "tags", "collection_id",
        "expires_at", "max_clicks", "is_active", "archived",
        "ios_url", "android_url",
        "utm_source", "utm_medium", "utm_campaign",
        "og_title", "og_description", "og_image",
    }

    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    # Parse expiration
    if "expires_at" in update_data and update_data["expires_at"]:
        try:
            update_data["expires_at"] = datetime.fromisoformat(
                update_data["expires_at"].replace("Z", "+00:00")
            )
        except ValueError:
            return jsonify({"error": "Invalid expires_at format"}), 400

    # Handle password update
    if "password" in data:
        if data["password"]:
            import bcrypt
            update_data["password"] = bcrypt.hashpw(
                data["password"].encode("utf-8"),
                bcrypt.gensalt()
            ).decode("utf-8")
        else:
            update_data["password"] = None

    if not update_data:
        return jsonify({"error": "No valid fields to update"}), 400

    try:
        db(db.short_urls.id == url_id).update(**update_data)
        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Failed to update URL: {str(e)}"}), 500

    # Invalidate cache
    domain = db(db.domains.id == url.domain_id).select().first()
    if domain:
        cache = get_cache_service()
        cache.invalidate(domain.domain, url.slug)

    # Get updated URL
    updated = db(db.short_urls.id == url_id).select().first()
    result = updated.as_dict()
    result["domain"] = domain.domain if domain else None
    result["short_url"] = f"https://{domain.domain}/{updated.slug}" if domain else None

    return jsonify(result)


@urls_bp.route("/<int:url_id>", methods=["DELETE"])
@token_required
def delete_url(url_id: int):
    """Delete a short URL.

    Args:
        url_id: URL database ID.

    Returns:
        Success message.
    """
    db = get_db()
    user_id = g.current_user["id"]

    # Get URL
    url = db(db.short_urls.id == url_id).select().first()
    if not url:
        return jsonify({"error": "URL not found"}), 404

    # Check access (must be creator, admin, or owner)
    membership = db(
        (db.team_members.team_id == url.team_id) &
        (db.team_members.user_id == user_id)
    ).select().first()

    if not membership:
        return jsonify({"error": "Access denied"}), 403

    if membership.role in ["viewer", "member"] and url.created_by != user_id:
        return jsonify({"error": "Cannot delete URLs created by others"}), 403

    # Get domain for cache invalidation
    domain = db(db.domains.id == url.domain_id).select().first()

    try:
        # Delete associated records
        db(db.click_events.short_url_id == url_id).delete()
        db(db.daily_stats.short_url_id == url_id).delete()
        db(db.qr_codes.short_url_id == url_id).delete()

        # Delete URL
        db(db.short_urls.id == url_id).delete()
        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Failed to delete URL: {str(e)}"}), 500

    # Invalidate cache
    if domain:
        cache = get_cache_service()
        cache.invalidate(domain.domain, url.slug)

    return jsonify({"message": "URL deleted successfully"})


@urls_bp.route("/<int:url_id>/duplicate", methods=["POST"])
@token_required
def duplicate_url(url_id: int):
    """Duplicate a short URL with a new slug.

    Args:
        url_id: URL database ID to duplicate.

    Returns:
        New duplicated URL object.
    """
    db = get_db()
    user_id = g.current_user["id"]

    # Get original URL
    url = db(db.short_urls.id == url_id).select().first()
    if not url:
        return jsonify({"error": "URL not found"}), 404

    # Check access
    membership = db(
        (db.team_members.team_id == url.team_id) &
        (db.team_members.user_id == user_id)
    ).select().first()

    if not membership:
        return jsonify({"error": "Access denied"}), 403

    if membership.role == "viewer":
        return jsonify({"error": "Viewers cannot create URLs"}), 403

    # Generate new slug
    for _ in range(10):
        new_slug = generate_slug()
        if is_slug_available(db, url.domain_id, new_slug):
            break
    else:
        return jsonify({"error": "Could not generate unique slug"}), 500

    # Create duplicate
    try:
        new_url_id = db.short_urls.insert(
            domain_id=url.domain_id,
            team_id=url.team_id,
            collection_id=url.collection_id,
            created_by=user_id,
            slug=new_slug,
            original_url=url.original_url,
            title=f"{url.title} (copy)" if url.title else None,
            description=url.description,
            tags=url.tags,
            ios_url=url.ios_url,
            android_url=url.android_url,
            utm_source=url.utm_source,
            utm_medium=url.utm_medium,
            utm_campaign=url.utm_campaign,
        )
        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Failed to duplicate URL: {str(e)}"}), 500

    # Get created URL
    created = db(db.short_urls.id == new_url_id).select().first()
    domain = db(db.domains.id == url.domain_id).select().first()

    result = created.as_dict()
    result["domain"] = domain.domain if domain else None
    result["short_url"] = f"https://{domain.domain}/{new_slug}" if domain else None

    return jsonify(result), 201
