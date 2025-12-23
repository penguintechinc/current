"""Slug generation utilities."""

import secrets
import string
import re
from typing import Optional


# URL-safe characters (excluding ambiguous chars)
URL_ALPHABET = "".join(
    c for c in string.ascii_letters + string.digits
    if c not in "0O1lI"
)


def generate_slug(length: int = 7) -> str:
    """Generate a random short URL slug.

    Args:
        length: Length of the slug (default 7).

    Returns:
        Random alphanumeric string.
    """
    return "".join(secrets.choice(URL_ALPHABET) for _ in range(length))


def generate_team_slug(name: str, max_length: int = 50) -> str:
    """Generate a URL-safe team slug from name.

    Args:
        name: Team name.
        max_length: Maximum slug length.

    Returns:
        URL-safe slug.
    """
    # Convert to lowercase
    slug = name.lower()

    # Replace spaces and special chars with hyphens
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)

    # Remove leading/trailing hyphens
    slug = slug.strip("-")

    # Truncate
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")

    # Ensure not empty
    if not slug:
        slug = generate_slug(8).lower()

    return slug


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


def is_team_slug_available(db, slug: str, exclude_id: Optional[int] = None) -> bool:
    """Check if a team slug is available.

    Args:
        db: Database connection.
        slug: Slug to check.
        exclude_id: Team ID to exclude (for updates).

    Returns:
        True if slug is available.
    """
    query = db.teams.slug == slug
    if exclude_id:
        query &= db.teams.id != exclude_id
    return db(query).count() == 0


def is_collection_slug_available(
    db,
    team_id: int,
    slug: str,
    exclude_id: Optional[int] = None
) -> bool:
    """Check if a collection slug is available within a team.

    Args:
        db: Database connection.
        team_id: Team ID.
        slug: Slug to check.
        exclude_id: Collection ID to exclude (for updates).

    Returns:
        True if slug is available.
    """
    query = (db.collections.team_id == team_id) & (db.collections.slug == slug)
    if exclude_id:
        query &= db.collections.id != exclude_id
    return db(query).count() == 0
