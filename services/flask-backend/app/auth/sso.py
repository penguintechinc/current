"""SSO/OAuth integration for enterprise users.

This module provides SAML and OAuth2 authentication for enterprise
customers with valid licenses.

Supported providers:
- SAML 2.0 (Okta, Azure AD, OneLogin, etc.)
- OAuth2/OIDC (Google, GitHub, Microsoft, etc.)

License requirement:
- Enterprise plan required for SSO features
- Validates against PenguinTech License Server
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional

from flask import Blueprint, current_app, g, jsonify, redirect, request, session

logger = logging.getLogger(__name__)

sso_bp = Blueprint("sso", __name__)


class SSOProvider(str, Enum):
    """Supported SSO providers."""
    SAML = "saml"
    GOOGLE = "google"
    GITHUB = "github"
    MICROSOFT = "microsoft"
    OKTA = "okta"
    CUSTOM_OIDC = "oidc"


@dataclass(slots=True)
class SSOConfig:
    """SSO provider configuration."""
    provider: SSOProvider
    client_id: str
    client_secret: str
    issuer_url: Optional[str] = None
    metadata_url: Optional[str] = None
    redirect_uri: Optional[str] = None
    scopes: list[str] | None = None

    def __post_init__(self):
        if self.scopes is None:
            self.scopes = ["openid", "email", "profile"]


def _check_enterprise_license() -> tuple[bool, str]:
    """Check if enterprise license is valid.

    Returns:
        Tuple of (is_valid, message).
    """
    # Check if release mode is enabled
    release_mode = os.environ.get("RELEASE_MODE", "false").lower() == "true"

    if not release_mode:
        # Development mode - all features available
        return True, "Development mode - SSO enabled"

    # Check license
    try:
        # Import shared licensing client
        import sys
        sys.path.insert(0, "/home/penguin/code/Current/shared/licensing")
        from licensing_client import LicenseClient

        client = LicenseClient()
        result = client.check_feature("sso")

        if result.get("allowed"):
            return True, "Enterprise license valid"
        else:
            return False, result.get("message", "SSO requires enterprise license")

    except ImportError:
        # Licensing client not available - check plan directly
        logger.warning("Licensing client not available, falling back to plan check")
        return _check_team_plan_for_sso()

    except Exception as e:
        logger.error(f"License check failed: {e}")
        return False, "License validation failed"


def _check_team_plan_for_sso() -> tuple[bool, str]:
    """Check if current team has enterprise plan.

    Returns:
        Tuple of (is_allowed, message).
    """
    from ..models import get_db

    try:
        db = get_db()
        user_id = g.current_user.get("id") if hasattr(g, "current_user") else None

        if not user_id:
            return False, "Authentication required"

        # Get user's teams with enterprise plan
        enterprise_teams = db(
            (db.team_members.user_id == user_id)
            & (db.teams.plan == "enterprise")
        ).select(
            db.teams.id,
            left=db.teams.on(db.team_members.team_id == db.teams.id),
        )

        if enterprise_teams:
            return True, "Enterprise plan active"
        else:
            return False, "SSO requires enterprise plan"

    except Exception as e:
        logger.error(f"Plan check failed: {e}")
        return False, "Plan validation failed"


def enterprise_required(f: Callable) -> Callable:
    """Decorator to require enterprise license for SSO endpoints.

    Args:
        f: Function to wrap.

    Returns:
        Wrapped function.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        is_valid, message = _check_enterprise_license()

        if not is_valid:
            return jsonify({
                "error": "Enterprise license required",
                "message": message,
                "upgrade_url": "https://www.penguintech.io/pricing",
            }), 403

        return f(*args, **kwargs)

    return decorated


@sso_bp.route("/providers", methods=["GET"])
def list_providers():
    """List available SSO providers.

    Returns available providers based on license status.

    Returns:
        JSON list of available providers.
    """
    is_licensed, _ = _check_enterprise_license()

    providers = [
        {
            "id": "google",
            "name": "Google",
            "type": "oauth2",
            "available": is_licensed,
        },
        {
            "id": "github",
            "name": "GitHub",
            "type": "oauth2",
            "available": is_licensed,
        },
        {
            "id": "microsoft",
            "name": "Microsoft",
            "type": "oauth2",
            "available": is_licensed,
        },
        {
            "id": "saml",
            "name": "SAML 2.0",
            "type": "saml",
            "available": is_licensed,
            "enterprise_only": True,
        },
        {
            "id": "oidc",
            "name": "Custom OIDC",
            "type": "oauth2",
            "available": is_licensed,
            "enterprise_only": True,
        },
    ]

    return jsonify({
        "providers": providers,
        "enterprise_licensed": is_licensed,
    })


@sso_bp.route("/config", methods=["GET"])
@enterprise_required
def get_sso_config():
    """Get SSO configuration for the current team.

    Returns:
        JSON with SSO configuration.
    """
    from ..models import get_db

    db = get_db()
    team_id = request.args.get("team_id", type=int)

    if not team_id:
        return jsonify({"error": "team_id required"}), 400

    # Get team's SSO config from settings
    team = db(db.teams.id == team_id).select().first()

    if not team:
        return jsonify({"error": "Team not found"}), 404

    sso_settings = team.settings.get("sso", {}) if team.settings else {}

    return jsonify({
        "team_id": team_id,
        "provider": sso_settings.get("provider"),
        "enabled": sso_settings.get("enabled", False),
        "metadata_url": sso_settings.get("metadata_url"),
        "issuer_url": sso_settings.get("issuer_url"),
    })


@sso_bp.route("/config", methods=["POST"])
@enterprise_required
def save_sso_config():
    """Save SSO configuration for a team.

    Request body:
        team_id: Team ID
        provider: SSO provider (saml, google, github, etc.)
        client_id: OAuth2 client ID (optional for SAML)
        client_secret: OAuth2 client secret (optional for SAML)
        metadata_url: SAML metadata URL (for SAML)
        issuer_url: OIDC issuer URL (for OIDC)

    Returns:
        JSON with saved configuration.
    """
    from ..models import get_db

    db = get_db()
    data = request.get_json() or {}

    team_id = data.get("team_id")
    if not team_id:
        return jsonify({"error": "team_id required"}), 400

    # Validate provider
    provider = data.get("provider")
    valid_providers = [p.value for p in SSOProvider]
    if provider and provider not in valid_providers:
        return jsonify({"error": f"Invalid provider. Use: {valid_providers}"}), 400

    # Get current team
    team = db(db.teams.id == team_id).select().first()
    if not team:
        return jsonify({"error": "Team not found"}), 404

    # Update settings
    settings = team.settings or {}
    settings["sso"] = {
        "provider": provider,
        "enabled": data.get("enabled", False),
        "client_id": data.get("client_id"),
        "metadata_url": data.get("metadata_url"),
        "issuer_url": data.get("issuer_url"),
    }

    # Don't store client_secret in DB, use env vars
    if data.get("client_secret"):
        logger.warning("SSO client_secret should be stored in environment variables")

    try:
        db(db.teams.id == team_id).update(settings=settings)
        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"Failed to save config: {str(e)}"}), 500

    return jsonify({
        "message": "SSO configuration saved",
        "team_id": team_id,
        "provider": provider,
    })


@sso_bp.route("/login/<provider>", methods=["GET"])
@enterprise_required
def initiate_sso_login(provider: str):
    """Initiate SSO login flow.

    Args:
        provider: SSO provider ID.

    Query params:
        team_id: Team ID for SSO config lookup

    Returns:
        Redirect to provider's login page.
    """
    team_id = request.args.get("team_id", type=int)

    if not team_id:
        return jsonify({"error": "team_id required"}), 400

    # This is a placeholder - actual implementation would:
    # 1. Load team's SSO config
    # 2. Generate state parameter
    # 3. Build authorization URL
    # 4. Redirect user to provider

    return jsonify({
        "message": "SSO login initiated",
        "provider": provider,
        "team_id": team_id,
        "status": "placeholder - full OAuth2/SAML flow not yet implemented",
        "next_steps": [
            "Install python-saml or authlib package",
            "Configure IdP metadata",
            "Implement callback handler",
        ],
    })


@sso_bp.route("/callback/<provider>", methods=["GET", "POST"])
def sso_callback(provider: str):
    """Handle SSO callback from provider.

    Args:
        provider: SSO provider ID.

    Returns:
        Redirect to app or error.
    """
    # This is a placeholder - actual implementation would:
    # 1. Validate state parameter
    # 2. Exchange code for tokens (OAuth2) or parse SAML response
    # 3. Extract user info
    # 4. Create/update user account
    # 5. Generate JWT tokens
    # 6. Redirect to frontend

    return jsonify({
        "message": "SSO callback received",
        "provider": provider,
        "status": "placeholder - callback processing not yet implemented",
    })
