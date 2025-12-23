"""Teams API endpoints."""

from datetime import datetime
from flask import Blueprint, jsonify, request, g

from ..middleware import token_required
from ..models import get_db, VALID_TEAM_ROLES, VALID_PLANS, PLAN_DOMAIN_LIMITS
from ..utils.permissions import team_role_required, check_plan_limit
from ..utils.slug_generator import generate_team_slug, is_team_slug_available

teams_bp = Blueprint("teams", __name__)


@teams_bp.route("", methods=["GET"])
@token_required
def list_teams():
    """List teams for the current user.

    Returns:
        JSON list of teams with user's role in each.
    """
    db = get_db()
    user_id = g.current_user["id"]

    # Get user's team memberships with team data
    memberships = db(db.team_members.user_id == user_id).select(
        db.team_members.ALL,
        db.teams.ALL,
        left=db.teams.on(db.team_members.team_id == db.teams.id),
        orderby=db.teams.name,
    )

    result = []
    for m in memberships:
        if m.teams:
            team_dict = m.teams.as_dict()
            team_dict["my_role"] = m.team_members.role
            team_dict["joined_at"] = m.team_members.joined_at.isoformat() if m.team_members.joined_at else None

            # Get member count
            team_dict["member_count"] = db(db.team_members.team_id == m.teams.id).count()

            # Get URL count
            team_dict["url_count"] = db(db.short_urls.team_id == m.teams.id).count()

            result.append(team_dict)

    return jsonify({"teams": result})


@teams_bp.route("", methods=["POST"])
@token_required
def create_team():
    """Create a new team.

    Request body:
        name: Required - Team name
        slug: Optional - URL-safe identifier (auto-generated if not provided)
        description: Optional - Team description

    Returns:
        Created team object.
    """
    db = get_db()
    user_id = g.current_user["id"]
    data = request.get_json() or {}

    # Validate name
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    if len(name) > 255:
        return jsonify({"error": "name must be 255 characters or less"}), 400

    # Generate or validate slug
    slug = data.get("slug", "").strip().lower()
    if slug:
        if not is_team_slug_available(db, slug):
            return jsonify({"error": "Slug already in use"}), 409
    else:
        base_slug = generate_team_slug(name)
        slug = base_slug
        counter = 1
        while not is_team_slug_available(db, slug):
            slug = f"{base_slug}-{counter}"
            counter += 1
            if counter > 100:
                return jsonify({"error": "Could not generate unique slug"}), 500

    # Create team
    try:
        team_id = db.teams.insert(
            name=name,
            slug=slug,
            description=data.get("description", ""),
            plan="free",
            owner_id=user_id,
            max_domains=PLAN_DOMAIN_LIMITS["free"],
            max_urls_per_month=100,
            settings={},
        )

        # Add creator as owner
        db.team_members.insert(
            team_id=team_id,
            user_id=user_id,
            role="owner",
            invited_by=user_id,
        )

        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Failed to create team: {str(e)}"}), 500

    # Get created team
    team = db(db.teams.id == team_id).select().first()
    result = team.as_dict()
    result["my_role"] = "owner"
    result["member_count"] = 1
    result["url_count"] = 0

    return jsonify(result), 201


@teams_bp.route("/<team_slug>", methods=["GET"])
@token_required
def get_team(team_slug: str):
    """Get team details.

    Args:
        team_slug: Team slug.

    Returns:
        Team object with stats.
    """
    db = get_db()
    user_id = g.current_user["id"]

    team = db(db.teams.slug == team_slug).select().first()
    if not team:
        return jsonify({"error": "Team not found"}), 404

    # Check membership
    membership = db(
        (db.team_members.team_id == team.id) &
        (db.team_members.user_id == user_id)
    ).select().first()

    if not membership:
        return jsonify({"error": "Access denied"}), 403

    result = team.as_dict()
    result["my_role"] = membership.role

    # Get stats
    result["member_count"] = db(db.team_members.team_id == team.id).count()
    result["url_count"] = db(db.short_urls.team_id == team.id).count()
    result["collection_count"] = db(db.collections.team_id == team.id).count()
    result["domain_count"] = db(db.team_domains.team_id == team.id).count()

    return jsonify(result)


@teams_bp.route("/<team_slug>", methods=["PUT"])
@token_required
@team_role_required("owner", "admin")
def update_team(team_slug: str):
    """Update team details.

    Args:
        team_slug: Team slug.

    Request body:
        name: Optional - New team name
        description: Optional - New description
        settings: Optional - Team settings JSON

    Returns:
        Updated team object.
    """
    db = get_db()
    data = request.get_json() or {}

    team = db(db.teams.slug == team_slug).select().first()
    if not team:
        return jsonify({"error": "Team not found"}), 404

    # Allowed update fields
    allowed_fields = {"name", "description", "settings"}
    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    if not update_data:
        return jsonify({"error": "No valid fields to update"}), 400

    try:
        db(db.teams.id == team.id).update(**update_data)
        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Failed to update team: {str(e)}"}), 500

    # Get updated team
    updated = db(db.teams.id == team.id).select().first()
    result = updated.as_dict()
    result["my_role"] = g.team_role

    return jsonify(result)


@teams_bp.route("/<team_slug>", methods=["DELETE"])
@token_required
@team_role_required("owner")
def delete_team(team_slug: str):
    """Delete a team. Only owner can delete.

    Args:
        team_slug: Team slug.

    Returns:
        Success message.
    """
    db = get_db()

    team = db(db.teams.slug == team_slug).select().first()
    if not team:
        return jsonify({"error": "Team not found"}), 404

    try:
        team_id = team.id

        # Delete all team data
        # First get all URL IDs for cascade delete
        url_ids = [u.id for u in db(db.short_urls.team_id == team_id).select(db.short_urls.id)]

        for url_id in url_ids:
            db(db.click_events.short_url_id == url_id).delete()
            db(db.daily_stats.short_url_id == url_id).delete()
            db(db.qr_codes.short_url_id == url_id).delete()

        db(db.short_urls.team_id == team_id).delete()
        db(db.collections.team_id == team_id).delete()
        db(db.team_domains.team_id == team_id).delete()
        db(db.team_members.team_id == team_id).delete()
        db(db.teams.id == team_id).delete()

        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Failed to delete team: {str(e)}"}), 500

    return jsonify({"message": "Team deleted successfully"})


# Team Members Endpoints

@teams_bp.route("/<team_slug>/members", methods=["GET"])
@token_required
@team_role_required("owner", "admin", "member", "viewer")
def list_members(team_slug: str):
    """List team members.

    Args:
        team_slug: Team slug.

    Returns:
        JSON list of team members.
    """
    db = get_db()

    team = db(db.teams.slug == team_slug).select().first()
    if not team:
        return jsonify({"error": "Team not found"}), 404

    members = db(db.team_members.team_id == team.id).select(
        db.team_members.ALL,
        db.users.id,
        db.users.email,
        db.users.full_name,
        left=db.users.on(db.team_members.user_id == db.users.id),
        orderby=db.team_members.joined_at,
    )

    result = []
    for m in members:
        result.append({
            "id": m.team_members.id,
            "user_id": m.users.id if m.users else None,
            "email": m.users.email if m.users else None,
            "full_name": m.users.full_name if m.users else None,
            "role": m.team_members.role,
            "joined_at": m.team_members.joined_at.isoformat() if m.team_members.joined_at else None,
        })

    return jsonify({"members": result})


@teams_bp.route("/<team_slug>/members", methods=["POST"])
@token_required
@team_role_required("owner", "admin")
def invite_member(team_slug: str):
    """Invite a member to the team.

    Args:
        team_slug: Team slug.

    Request body:
        email: Required - User email to invite
        role: Optional - Role (default: member)

    Returns:
        Created membership object.
    """
    db = get_db()
    user_id = g.current_user["id"]
    data = request.get_json() or {}

    team = db(db.teams.slug == team_slug).select().first()
    if not team:
        return jsonify({"error": "Team not found"}), 404

    # Check plan limits
    allowed, message = check_plan_limit(team.id, "members")
    if not allowed:
        return jsonify({"error": message}), 403

    # Validate email
    email = data.get("email", "").strip().lower()
    if not email:
        return jsonify({"error": "email is required"}), 400

    # Find user by email
    user = db(db.users.email == email).select().first()
    if not user:
        return jsonify({"error": "User not found with this email"}), 404

    # Check if already a member
    existing = db(
        (db.team_members.team_id == team.id) &
        (db.team_members.user_id == user.id)
    ).select().first()

    if existing:
        return jsonify({"error": "User is already a team member"}), 409

    # Validate role
    role = data.get("role", "member")
    if role not in VALID_TEAM_ROLES:
        return jsonify({"error": f"Invalid role. Must be one of: {', '.join(VALID_TEAM_ROLES)}"}), 400

    # Can't add another owner
    if role == "owner":
        return jsonify({"error": "Cannot add another owner. Transfer ownership instead."}), 400

    # Admin can't add admin (only owner can)
    if role == "admin" and g.team_role != "owner":
        return jsonify({"error": "Only owner can add admins"}), 403

    try:
        member_id = db.team_members.insert(
            team_id=team.id,
            user_id=user.id,
            role=role,
            invited_by=user_id,
        )
        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Failed to add member: {str(e)}"}), 500

    return jsonify({
        "id": member_id,
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": role,
        "joined_at": datetime.utcnow().isoformat(),
    }), 201


@teams_bp.route("/<team_slug>/members/<int:member_id>", methods=["PUT"])
@token_required
@team_role_required("owner", "admin")
def update_member_role(team_slug: str, member_id: int):
    """Update a member's role.

    Args:
        team_slug: Team slug.
        member_id: Team member ID.

    Request body:
        role: New role

    Returns:
        Updated member object.
    """
    db = get_db()
    data = request.get_json() or {}

    team = db(db.teams.slug == team_slug).select().first()
    if not team:
        return jsonify({"error": "Team not found"}), 404

    member = db(
        (db.team_members.id == member_id) &
        (db.team_members.team_id == team.id)
    ).select().first()

    if not member:
        return jsonify({"error": "Member not found"}), 404

    # Can't change owner's role
    if member.role == "owner":
        return jsonify({"error": "Cannot change owner's role. Transfer ownership instead."}), 400

    # Validate role
    role = data.get("role")
    if not role or role not in VALID_TEAM_ROLES:
        return jsonify({"error": f"Invalid role. Must be one of: {', '.join(VALID_TEAM_ROLES)}"}), 400

    if role == "owner":
        return jsonify({"error": "Use transfer ownership endpoint instead"}), 400

    # Admin can't promote to admin
    if role == "admin" and g.team_role != "owner":
        return jsonify({"error": "Only owner can promote to admin"}), 403

    try:
        db(db.team_members.id == member_id).update(role=role)
        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Failed to update role: {str(e)}"}), 500

    # Get user info
    user = db(db.users.id == member.user_id).select().first()

    return jsonify({
        "id": member_id,
        "user_id": member.user_id,
        "email": user.email if user else None,
        "full_name": user.full_name if user else None,
        "role": role,
    })


@teams_bp.route("/<team_slug>/members/<int:member_id>", methods=["DELETE"])
@token_required
@team_role_required("owner", "admin")
def remove_member(team_slug: str, member_id: int):
    """Remove a member from the team.

    Args:
        team_slug: Team slug.
        member_id: Team member ID.

    Returns:
        Success message.
    """
    db = get_db()

    team = db(db.teams.slug == team_slug).select().first()
    if not team:
        return jsonify({"error": "Team not found"}), 404

    member = db(
        (db.team_members.id == member_id) &
        (db.team_members.team_id == team.id)
    ).select().first()

    if not member:
        return jsonify({"error": "Member not found"}), 404

    # Can't remove owner
    if member.role == "owner":
        return jsonify({"error": "Cannot remove owner. Transfer ownership first."}), 400

    # Admin can't remove admin
    if member.role == "admin" and g.team_role != "owner":
        return jsonify({"error": "Only owner can remove admins"}), 403

    try:
        db(db.team_members.id == member_id).delete()
        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Failed to remove member: {str(e)}"}), 500

    return jsonify({"message": "Member removed successfully"})


@teams_bp.route("/<team_slug>/leave", methods=["POST"])
@token_required
def leave_team(team_slug: str):
    """Leave a team.

    Args:
        team_slug: Team slug.

    Returns:
        Success message.
    """
    db = get_db()
    user_id = g.current_user["id"]

    team = db(db.teams.slug == team_slug).select().first()
    if not team:
        return jsonify({"error": "Team not found"}), 404

    member = db(
        (db.team_members.team_id == team.id) &
        (db.team_members.user_id == user_id)
    ).select().first()

    if not member:
        return jsonify({"error": "Not a team member"}), 403

    # Owner can't leave (must transfer ownership first)
    if member.role == "owner":
        return jsonify({"error": "Owner cannot leave. Transfer ownership first."}), 400

    try:
        db(db.team_members.id == member.id).delete()
        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Failed to leave team: {str(e)}"}), 500

    return jsonify({"message": "Left team successfully"})
