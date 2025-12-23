"""Collections API endpoints."""

from flask import Blueprint, jsonify, request, g

from ..middleware import token_required
from ..models import get_db
from ..utils.permissions import team_role_required, can_manage_collection
from ..utils.slug_generator import generate_team_slug, is_collection_slug_available

collections_bp = Blueprint("collections", __name__)


@collections_bp.route("", methods=["GET"])
@token_required
def list_collections():
    """List collections for user's teams.

    Query params:
        team_id: Filter by team ID (required)
        parent_id: Filter by parent collection (for nested)

    Returns:
        JSON list of collections.
    """
    db = get_db()
    user_id = g.current_user["id"]

    team_id = request.args.get("team_id", type=int)
    if not team_id:
        return jsonify({"error": "team_id is required"}), 400

    # Check team membership
    membership = db(
        (db.team_members.team_id == team_id) &
        (db.team_members.user_id == user_id)
    ).select().first()

    if not membership:
        return jsonify({"error": "Access denied"}), 403

    # Build query
    query = (db.collections.team_id == team_id) & (db.collections.is_active == True)

    parent_id = request.args.get("parent_id", type=int)
    if parent_id is not None:
        query &= (db.collections.parent_id == parent_id)

    collections = db(query).select(orderby=db.collections.name)

    result = []
    for c in collections:
        coll_dict = c.as_dict()
        # Get URL count in collection
        coll_dict["url_count"] = db(db.short_urls.collection_id == c.id).count()
        # Get child count
        coll_dict["child_count"] = db(db.collections.parent_id == c.id).count()
        result.append(coll_dict)

    return jsonify({"collections": result})


@collections_bp.route("", methods=["POST"])
@token_required
def create_collection():
    """Create a new collection.

    Request body:
        team_id: Required - Team to create collection in
        name: Required - Collection name
        slug: Optional - URL-safe identifier
        description: Optional
        color: Optional - Hex color (default: #6366f1)
        icon: Optional - Emoji or icon class
        parent_id: Optional - Parent collection ID

    Returns:
        Created collection object.
    """
    db = get_db()
    user_id = g.current_user["id"]
    data = request.get_json() or {}

    # Validate required fields
    team_id = data.get("team_id")
    name = data.get("name", "").strip()

    if not team_id:
        return jsonify({"error": "team_id is required"}), 400
    if not name:
        return jsonify({"error": "name is required"}), 400

    # Check team membership with create permission
    membership = db(
        (db.team_members.team_id == team_id) &
        (db.team_members.user_id == user_id)
    ).select().first()

    if not membership:
        return jsonify({"error": "Access denied"}), 403

    if membership.role == "viewer":
        return jsonify({"error": "Viewers cannot create collections"}), 403

    # Generate or validate slug
    slug = data.get("slug", "").strip().lower()
    if slug:
        if not is_collection_slug_available(db, team_id, slug):
            return jsonify({"error": "Slug already in use in this team"}), 409
    else:
        base_slug = generate_team_slug(name, max_length=50)
        slug = base_slug
        counter = 1
        while not is_collection_slug_available(db, team_id, slug):
            slug = f"{base_slug}-{counter}"
            counter += 1
            if counter > 100:
                return jsonify({"error": "Could not generate unique slug"}), 500

    # Validate parent collection if provided
    parent_id = data.get("parent_id")
    if parent_id:
        parent = db(
            (db.collections.id == parent_id) &
            (db.collections.team_id == team_id)
        ).select().first()
        if not parent:
            return jsonify({"error": "Parent collection not found"}), 404

    # Validate color format
    color = data.get("color", "#6366f1")
    if color and not color.startswith("#"):
        color = f"#{color}"
    if len(color) != 7:
        color = "#6366f1"

    try:
        collection_id = db.collections.insert(
            team_id=team_id,
            name=name,
            slug=slug,
            description=data.get("description", ""),
            color=color,
            icon=data.get("icon"),
            parent_id=parent_id,
        )
        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Failed to create collection: {str(e)}"}), 500

    created = db(db.collections.id == collection_id).select().first()
    result = created.as_dict()
    result["url_count"] = 0
    result["child_count"] = 0

    return jsonify(result), 201


@collections_bp.route("/<int:collection_id>", methods=["GET"])
@token_required
def get_collection(collection_id: int):
    """Get collection details.

    Args:
        collection_id: Collection ID.

    Returns:
        Collection object with stats.
    """
    db = get_db()
    user_id = g.current_user["id"]

    collection = db(db.collections.id == collection_id).select().first()
    if not collection:
        return jsonify({"error": "Collection not found"}), 404

    # Check team membership
    membership = db(
        (db.team_members.team_id == collection.team_id) &
        (db.team_members.user_id == user_id)
    ).select().first()

    if not membership:
        return jsonify({"error": "Access denied"}), 403

    result = collection.as_dict()
    result["url_count"] = db(db.short_urls.collection_id == collection_id).count()
    result["child_count"] = db(db.collections.parent_id == collection_id).count()

    return jsonify(result)


@collections_bp.route("/<int:collection_id>", methods=["PUT"])
@token_required
def update_collection(collection_id: int):
    """Update collection details.

    Args:
        collection_id: Collection ID.

    Request body:
        name: Optional
        description: Optional
        color: Optional
        icon: Optional
        parent_id: Optional (set to null to move to root)

    Returns:
        Updated collection object.
    """
    db = get_db()
    user_id = g.current_user["id"]
    data = request.get_json() or {}

    collection = db(db.collections.id == collection_id).select().first()
    if not collection:
        return jsonify({"error": "Collection not found"}), 404

    # Check permissions
    if not can_manage_collection(user_id, collection_id):
        return jsonify({"error": "Access denied"}), 403

    # Allowed update fields
    allowed_fields = {"name", "description", "color", "icon", "parent_id", "is_active"}
    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    # Validate parent if changing
    if "parent_id" in update_data:
        parent_id = update_data["parent_id"]
        if parent_id:
            # Can't set self as parent
            if parent_id == collection_id:
                return jsonify({"error": "Cannot set self as parent"}), 400

            parent = db(
                (db.collections.id == parent_id) &
                (db.collections.team_id == collection.team_id)
            ).select().first()
            if not parent:
                return jsonify({"error": "Parent collection not found"}), 404

            # Check for circular reference
            current = parent
            while current and current.parent_id:
                if current.parent_id == collection_id:
                    return jsonify({"error": "Circular reference detected"}), 400
                current = db(db.collections.id == current.parent_id).select().first()

    if not update_data:
        return jsonify({"error": "No valid fields to update"}), 400

    try:
        db(db.collections.id == collection_id).update(**update_data)
        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Failed to update collection: {str(e)}"}), 500

    updated = db(db.collections.id == collection_id).select().first()
    result = updated.as_dict()
    result["url_count"] = db(db.short_urls.collection_id == collection_id).count()
    result["child_count"] = db(db.collections.parent_id == collection_id).count()

    return jsonify(result)


@collections_bp.route("/<int:collection_id>", methods=["DELETE"])
@token_required
def delete_collection(collection_id: int):
    """Delete a collection.

    URLs in this collection will have their collection_id set to null.
    Child collections will be moved to parent (or root if no parent).

    Args:
        collection_id: Collection ID.

    Returns:
        Success message.
    """
    db = get_db()
    user_id = g.current_user["id"]

    collection = db(db.collections.id == collection_id).select().first()
    if not collection:
        return jsonify({"error": "Collection not found"}), 404

    # Check permissions
    if not can_manage_collection(user_id, collection_id):
        return jsonify({"error": "Access denied"}), 403

    try:
        # Move child collections to parent
        db(db.collections.parent_id == collection_id).update(
            parent_id=collection.parent_id
        )

        # Remove collection from URLs (set to null)
        db(db.short_urls.collection_id == collection_id).update(
            collection_id=None
        )

        # Delete collection
        db(db.collections.id == collection_id).delete()
        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Failed to delete collection: {str(e)}"}), 500

    return jsonify({"message": "Collection deleted successfully"})


@collections_bp.route("/<int:collection_id>/urls", methods=["GET"])
@token_required
def list_collection_urls(collection_id: int):
    """List URLs in a collection.

    Args:
        collection_id: Collection ID.

    Query params:
        page: Page number (default 1)
        per_page: Items per page (default 20, max 100)

    Returns:
        JSON list of URLs.
    """
    db = get_db()
    user_id = g.current_user["id"]

    collection = db(db.collections.id == collection_id).select().first()
    if not collection:
        return jsonify({"error": "Collection not found"}), 404

    # Check team membership
    membership = db(
        (db.team_members.team_id == collection.team_id) &
        (db.team_members.user_id == user_id)
    ).select().first()

    if not membership:
        return jsonify({"error": "Access denied"}), 403

    # Pagination
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    offset = (page - 1) * per_page

    # Get URLs
    query = (db.short_urls.collection_id == collection_id) & (db.short_urls.archived == False)
    total = db(query).count()

    urls = db(query).select(
        db.short_urls.ALL,
        db.domains.domain,
        left=db.domains.on(db.short_urls.domain_id == db.domains.id),
        orderby=~db.short_urls.created_at,
        limitby=(offset, offset + per_page),
    )

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
