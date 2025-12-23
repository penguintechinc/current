"""Domains API endpoints with DNS verification."""

import os
from datetime import datetime
from flask import Blueprint, jsonify, request, g

from ..middleware import token_required
from ..models import get_db
from ..utils.permissions import team_role_required, check_plan_limit
from ..utils.dns_verification import (
    generate_verification_code,
    verify_domain_dns,
    verify_domain_cname,
    get_domain_verification_instructions,
)

domains_bp = Blueprint("domains", __name__)

# Our service hostname for CNAME/A record verification
SERVICE_HOSTNAME = os.environ.get("SERVICE_HOSTNAME", "redirect.shortener.io")


@domains_bp.route("", methods=["GET"])
@token_required
def list_domains():
    """List all domains available to the user.

    Query params:
        team_id: Filter by team ID (optional)

    Returns:
        JSON list of domains.
    """
    db = get_db()
    user_id = g.current_user["id"]

    team_id = request.args.get("team_id", type=int)

    if team_id:
        # Check team membership
        membership = db(
            (db.team_members.team_id == team_id) &
            (db.team_members.user_id == user_id)
        ).select().first()

        if not membership:
            return jsonify({"error": "Access denied"}), 403

        # Get team's domains
        team_domains = db(db.team_domains.team_id == team_id).select(
            db.team_domains.ALL,
            db.domains.ALL,
            left=db.domains.on(db.team_domains.domain_id == db.domains.id),
        )

        result = []
        for td in team_domains:
            if td.domains:
                domain_dict = td.domains.as_dict()
                domain_dict["is_default"] = td.team_domains.is_default
                domain_dict["is_verified"] = td.domains.verified_at is not None
                result.append(domain_dict)

        return jsonify({"domains": result})

    else:
        # Get all domains from user's teams
        user_teams = db(db.team_members.user_id == user_id).select(db.team_members.team_id)
        team_ids = [t.team_id for t in user_teams]

        if not team_ids:
            return jsonify({"domains": []})

        team_domains = db(db.team_domains.team_id.belongs(team_ids)).select(
            db.team_domains.ALL,
            db.domains.ALL,
            db.teams.name,
            db.teams.slug,
            left=[
                db.domains.on(db.team_domains.domain_id == db.domains.id),
                db.teams.on(db.team_domains.team_id == db.teams.id),
            ],
        )

        result = []
        for td in team_domains:
            if td.domains:
                domain_dict = td.domains.as_dict()
                domain_dict["is_default"] = td.team_domains.is_default
                domain_dict["is_verified"] = td.domains.verified_at is not None
                domain_dict["team_id"] = td.team_domains.team_id
                domain_dict["team_name"] = td.teams.name if td.teams else None
                domain_dict["team_slug"] = td.teams.slug if td.teams else None
                result.append(domain_dict)

        return jsonify({"domains": result})


@domains_bp.route("", methods=["POST"])
@token_required
def add_domain():
    """Add a new domain to a team.

    Request body:
        domain: Required - Domain name (e.g., "short.io")
        team_id: Required - Team to add domain to
        is_default: Optional - Set as team's default domain

    Returns:
        Domain object with verification instructions.
    """
    db = get_db()
    user_id = g.current_user["id"]
    data = request.get_json() or {}

    # Validate required fields
    domain_name = data.get("domain", "").strip().lower()
    team_id = data.get("team_id")

    if not domain_name:
        return jsonify({"error": "domain is required"}), 400
    if not team_id:
        return jsonify({"error": "team_id is required"}), 400

    # Check team membership with admin permission
    membership = db(
        (db.team_members.team_id == team_id) &
        (db.team_members.user_id == user_id)
    ).select().first()

    if not membership or membership.role not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403

    # Check plan limits
    allowed, message = check_plan_limit(team_id, "domains")
    if not allowed:
        return jsonify({"error": message}), 403

    # Check if domain already exists
    existing = db(db.domains.domain == domain_name).select().first()

    if existing:
        # Check if already assigned to a team
        existing_assignment = db(db.team_domains.domain_id == existing.id).select().first()
        if existing_assignment:
            return jsonify({"error": "Domain is already in use by another team"}), 409

        # Domain exists but not assigned - assign it to this team
        domain_id = existing.id
        verification_code = existing.verification_code
    else:
        # Create new domain
        verification_code = generate_verification_code(domain_name)

        try:
            domain_id = db.domains.insert(
                domain=domain_name,
                is_primary=False,
                is_active=True,
                ssl_enabled=True,
                verification_code=verification_code,
            )
            db.commit()
        except Exception as e:
            db.rollback()
            return jsonify({"error": f"Failed to create domain: {str(e)}"}), 500

    # Check if already assigned to this team
    existing_team_domain = db(
        (db.team_domains.team_id == team_id) &
        (db.team_domains.domain_id == domain_id)
    ).select().first()

    if existing_team_domain:
        return jsonify({"error": "Domain is already added to this team"}), 409

    # Assign domain to team
    is_default = data.get("is_default", False)

    # If setting as default, unset other defaults
    if is_default:
        db(db.team_domains.team_id == team_id).update(is_default=False)

    try:
        db.team_domains.insert(
            team_id=team_id,
            domain_id=domain_id,
            is_default=is_default,
        )
        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Failed to assign domain: {str(e)}"}), 500

    # Get domain info
    domain = db(db.domains.id == domain_id).select().first()
    result = domain.as_dict()
    result["is_default"] = is_default
    result["is_verified"] = domain.verified_at is not None

    # Include verification instructions
    result["verification"] = get_domain_verification_instructions(
        domain_name, verification_code
    )

    return jsonify(result), 201


@domains_bp.route("/<int:domain_id>", methods=["GET"])
@token_required
def get_domain(domain_id: int):
    """Get domain details.

    Args:
        domain_id: Domain ID.

    Returns:
        Domain object with verification status.
    """
    db = get_db()
    user_id = g.current_user["id"]

    domain = db(db.domains.id == domain_id).select().first()
    if not domain:
        return jsonify({"error": "Domain not found"}), 404

    # Check if user has access via any team
    team_domain = db(db.team_domains.domain_id == domain_id).select().first()
    if not team_domain:
        return jsonify({"error": "Domain not assigned to any team"}), 404

    membership = db(
        (db.team_members.team_id == team_domain.team_id) &
        (db.team_members.user_id == user_id)
    ).select().first()

    if not membership:
        return jsonify({"error": "Access denied"}), 403

    result = domain.as_dict()
    result["is_default"] = team_domain.is_default
    result["is_verified"] = domain.verified_at is not None
    result["team_id"] = team_domain.team_id

    # Include verification instructions if not verified
    if not domain.verified_at and domain.verification_code:
        result["verification"] = get_domain_verification_instructions(
            domain.domain, domain.verification_code
        )

    return jsonify(result)


@domains_bp.route("/<int:domain_id>", methods=["DELETE"])
@token_required
def remove_domain(domain_id: int):
    """Remove a domain from a team.

    Args:
        domain_id: Domain ID.

    Query params:
        team_id: Required - Team to remove domain from

    Returns:
        Success message.
    """
    db = get_db()
    user_id = g.current_user["id"]

    team_id = request.args.get("team_id", type=int)
    if not team_id:
        return jsonify({"error": "team_id query parameter is required"}), 400

    # Check admin permission
    membership = db(
        (db.team_members.team_id == team_id) &
        (db.team_members.user_id == user_id)
    ).select().first()

    if not membership or membership.role not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403

    # Check domain is assigned to team
    team_domain = db(
        (db.team_domains.team_id == team_id) &
        (db.team_domains.domain_id == domain_id)
    ).select().first()

    if not team_domain:
        return jsonify({"error": "Domain not found in this team"}), 404

    # Check if domain has URLs
    url_count = db(
        (db.short_urls.domain_id == domain_id) &
        (db.short_urls.team_id == team_id)
    ).count()

    if url_count > 0:
        return jsonify({
            "error": f"Cannot remove domain with {url_count} URLs. Delete or migrate URLs first."
        }), 400

    try:
        # Remove team-domain assignment
        db(db.team_domains.id == team_domain.id).delete()

        # Check if domain is still used by other teams
        other_assignments = db(db.team_domains.domain_id == domain_id).count()
        if other_assignments == 0:
            # No other teams using this domain, can delete it
            db(db.domains.id == domain_id).delete()

        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Failed to remove domain: {str(e)}"}), 500

    return jsonify({"message": "Domain removed successfully"})


@domains_bp.route("/<int:domain_id>/verify", methods=["POST"])
@token_required
def verify_domain(domain_id: int):
    """Verify domain ownership via DNS.

    Checks for TXT record or CNAME/A record pointing to our service.

    Args:
        domain_id: Domain ID.

    Request body:
        method: Optional - "txt" or "cname" (default: tries both)

    Returns:
        Verification result.
    """
    db = get_db()
    user_id = g.current_user["id"]
    data = request.get_json() or {}

    domain = db(db.domains.id == domain_id).select().first()
    if not domain:
        return jsonify({"error": "Domain not found"}), 404

    # Check user has access
    team_domain = db(db.team_domains.domain_id == domain_id).select().first()
    if not team_domain:
        return jsonify({"error": "Domain not assigned to any team"}), 404

    membership = db(
        (db.team_members.team_id == team_domain.team_id) &
        (db.team_members.user_id == user_id)
    ).select().first()

    if not membership or membership.role not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403

    # Already verified?
    if domain.verified_at:
        return jsonify({
            "verified": True,
            "message": "Domain already verified",
            "verified_at": domain.verified_at.isoformat(),
        })

    method = data.get("method", "auto")

    # Try verification methods
    result = {"verified": False, "attempts": []}

    if method in ("txt", "auto"):
        txt_result = verify_domain_dns(domain.domain, domain.verification_code)
        result["attempts"].append({"method": "txt", **txt_result})

        if txt_result["verified"]:
            result["verified"] = True
            result["method"] = "txt"

    if not result["verified"] and method in ("cname", "auto"):
        cname_result = verify_domain_cname(domain.domain, SERVICE_HOSTNAME)
        result["attempts"].append({"method": "cname", **cname_result})

        if cname_result["verified"]:
            result["verified"] = True
            result["method"] = "cname"

    # Update domain if verified
    if result["verified"]:
        try:
            db(db.domains.id == domain_id).update(
                verified_at=datetime.utcnow()
            )
            db.commit()
            result["message"] = "Domain verified successfully"
        except Exception as e:
            db.rollback()
            return jsonify({"error": f"Failed to update domain: {str(e)}"}), 500
    else:
        result["message"] = "Verification failed. Please check your DNS configuration."
        result["instructions"] = get_domain_verification_instructions(
            domain.domain, domain.verification_code
        )

    return jsonify(result)


@domains_bp.route("/<int:domain_id>/set-default", methods=["POST"])
@token_required
def set_default_domain(domain_id: int):
    """Set domain as team's default.

    Args:
        domain_id: Domain ID.

    Request body:
        team_id: Required - Team ID

    Returns:
        Success message.
    """
    db = get_db()
    user_id = g.current_user["id"]
    data = request.get_json() or {}

    team_id = data.get("team_id")
    if not team_id:
        return jsonify({"error": "team_id is required"}), 400

    # Check admin permission
    membership = db(
        (db.team_members.team_id == team_id) &
        (db.team_members.user_id == user_id)
    ).select().first()

    if not membership or membership.role not in ("owner", "admin"):
        return jsonify({"error": "Admin access required"}), 403

    # Check domain is assigned to team
    team_domain = db(
        (db.team_domains.team_id == team_id) &
        (db.team_domains.domain_id == domain_id)
    ).select().first()

    if not team_domain:
        return jsonify({"error": "Domain not found in this team"}), 404

    try:
        # Unset other defaults
        db(db.team_domains.team_id == team_id).update(is_default=False)

        # Set this as default
        db(db.team_domains.id == team_domain.id).update(is_default=True)
        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Failed to set default: {str(e)}"}), 500

    return jsonify({"message": "Default domain updated"})
