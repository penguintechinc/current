"""Utility modules for URL shortener."""

from .permissions import (
    team_role_required,
    can_manage_url,
    can_manage_collection,
    get_user_team_role,
    check_plan_limit,
)
from .slug_generator import (
    generate_slug,
    generate_team_slug,
    is_slug_available,
    is_team_slug_available,
    is_collection_slug_available,
)
from .dns_verification import (
    generate_verification_code,
    verify_domain_dns,
    verify_domain_cname,
    get_domain_verification_instructions,
)

__all__ = [
    # Permissions
    "team_role_required",
    "can_manage_url",
    "can_manage_collection",
    "get_user_team_role",
    "check_plan_limit",
    # Slug generation
    "generate_slug",
    "generate_team_slug",
    "is_slug_available",
    "is_team_slug_available",
    "is_collection_slug_available",
    # DNS verification
    "generate_verification_code",
    "verify_domain_dns",
    "verify_domain_cname",
    "get_domain_verification_instructions",
]
