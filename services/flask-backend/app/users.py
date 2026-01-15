"""
User Management Endpoints (Admin Only).

Provides CRUD operations for user management with Pydantic validation.
All endpoints require admin role.
"""

from __future__ import annotations

from pydantic import ValidationError
from quart import Blueprint, jsonify, request

from .async_db import run_sync
from .auth import (admin_required, auth_required, get_current_user,
                   hash_password)
from .models import (VALID_ROLES, create_user, delete_user, get_user_by_email,
                     get_user_by_id, list_users, update_user)
from .schemas import (CreateUserRequest, PaginatedUsersResponse,
                      PaginationMeta, RolesResponse, UpdateUserRequest,
                      UserCreatedResponse, UserDeletedResponse,
                      UserDetailResponse, UserListItem, UserUpdatedResponse)

users_bp = Blueprint("users", __name__)


@users_bp.route("", methods=["GET"])
@auth_required
@admin_required
async def get_users():
    """
    List all users with pagination (Admin only).

    Query parameters:
        page: Page number (default: 1)
        per_page: Items per page (default: 20, max: 100)

    Returns:
        users: List of users
        pagination: Pagination metadata
    """
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    # Validate and limit bounds
    page = max(1, page)
    per_page = min(max(per_page, 1), 100)

    # Get users from database
    users, total = await run_sync(list_users, page=page, per_page=per_page)

    # Convert to response models (removes password hashes)
    user_items = []
    for user in users:
        user_items.append(
            UserListItem(
                id=user["id"],
                email=user["email"],
                full_name=user.get("full_name", ""),
                role=user.get("role", "viewer"),
                is_active=user.get("is_active", True),
                created_at=user.get("created_at"),
                updated_at=user.get("updated_at"),
                last_login_at=user.get("last_login_at"),
            )
        )

    response = PaginatedUsersResponse(
        users=user_items,
        pagination=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            pages=(total + per_page - 1) // per_page if per_page > 0 else 0,
        ),
    )

    return jsonify(response.model_dump(mode="json")), 200


@users_bp.route("/<int:user_id>", methods=["GET"])
@auth_required
@admin_required
async def get_user(user_id: int):
    """
    Get single user by ID (Admin only).

    Path parameters:
        user_id: User ID

    Returns:
        User details
    """
    user = await run_sync(get_user_by_id, user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    response = UserDetailResponse(
        id=user["id"],
        email=user["email"],
        full_name=user.get("full_name", ""),
        role=user.get("role", "viewer"),
        is_active=user.get("is_active", True),
        created_at=user.get("created_at"),
        updated_at=user.get("updated_at"),
        last_login_at=user.get("last_login_at"),
        login_count=user.get("login_count"),
        confirmed_at=user.get("confirmed_at"),
    )

    return jsonify(response.model_dump(mode="json")), 200


@users_bp.route("", methods=["POST"])
@auth_required
@admin_required
async def create_new_user():
    """
    Create new user (Admin only).

    Request body (JSON):
        email: User email
        password: Password (min 8 characters)
        full_name: Optional full name
        role: User role (admin, maintainer, viewer)

    Returns:
        message: Success message
        user: Created user data
    """
    data = await request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    # Validate with Pydantic (includes password strength validation)
    try:
        create_req = CreateUserRequest(**data)
    except ValidationError as e:
        error_msg = e.errors()[0].get("msg", "Validation error")
        return jsonify({"error": error_msg}), 400

    # Check if user exists
    existing = await run_sync(get_user_by_email, create_req.email)
    if existing:
        return jsonify({"error": "Email already registered"}), 409

    # Hash password
    password_hash = hash_password(create_req.password)

    # Create user
    user = await run_sync(
        create_user,
        email=create_req.email,
        password_hash=password_hash,
        full_name=create_req.full_name,
        role=create_req.role,
    )

    # Build response
    user_item = UserListItem(
        id=user["id"],
        email=user["email"],
        full_name=user.get("full_name", ""),
        role=user.get("role", "viewer"),
        is_active=user.get("is_active", True),
        created_at=user.get("created_at"),
    )

    response = UserCreatedResponse(
        message="User created successfully",
        user=user_item,
    )

    return jsonify(response.model_dump(mode="json")), 201


@users_bp.route("/<int:user_id>", methods=["PUT"])
@auth_required
@admin_required
async def update_existing_user(user_id: int):
    """
    Update user by ID (Admin only).

    Path parameters:
        user_id: User ID

    Request body (JSON):
        email: Optional new email
        password: Optional new password
        full_name: Optional new full name
        role: Optional new role
        is_active: Optional active status

    Returns:
        message: Success message
        user: Updated user data
    """
    user = await run_sync(get_user_by_id, user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    data = await request.get_json()

    if not data:
        return jsonify({"error": "Request body required"}), 400

    # Validate with Pydantic
    try:
        update_req = UpdateUserRequest(**data)
    except ValidationError as e:
        error_msg = e.errors()[0].get("msg", "Validation error")
        return jsonify({"error": error_msg}), 400

    update_data = {}

    # Email update
    if update_req.email is not None and update_req.email != user["email"]:
        existing = await run_sync(get_user_by_email, update_req.email)
        if existing:
            return jsonify({"error": "Email already in use"}), 409
        update_data["email"] = update_req.email

    # Full name update
    if update_req.full_name is not None:
        update_data["full_name"] = update_req.full_name

    # Role update
    if update_req.role is not None:
        update_data["role"] = update_req.role

    # Active status update
    if update_req.is_active is not None:
        update_data["is_active"] = update_req.is_active

    # Password update
    if update_req.password is not None:
        update_data["password_hash"] = hash_password(update_req.password)

    if not update_data:
        return jsonify({"error": "No valid fields to update"}), 400

    updated_user = await run_sync(update_user, user_id, **update_data)

    # Build response
    user_item = UserListItem(
        id=updated_user["id"],
        email=updated_user["email"],
        full_name=updated_user.get("full_name", ""),
        role=updated_user.get("role", "viewer"),
        is_active=updated_user.get("is_active", True),
        created_at=updated_user.get("created_at"),
        updated_at=updated_user.get("updated_at"),
    )

    response = UserUpdatedResponse(
        message="User updated successfully",
        user=user_item,
    )

    return jsonify(response.model_dump(mode="json")), 200


@users_bp.route("/<int:user_id>", methods=["DELETE"])
@auth_required
@admin_required
async def delete_existing_user(user_id: int):
    """
    Delete user by ID (Admin only).

    Path parameters:
        user_id: User ID

    Returns:
        message: Success message
    """
    current_user = get_current_user()

    # Prevent self-deletion
    if current_user["id"] == user_id:
        return jsonify({"error": "Cannot delete your own account"}), 400

    user = await run_sync(get_user_by_id, user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    success = await run_sync(delete_user, user_id)

    if not success:
        return jsonify({"error": "Failed to delete user"}), 500

    response = UserDeletedResponse(message="User deleted successfully")

    return jsonify(response.model_dump()), 200


@users_bp.route("/roles", methods=["GET"])
@auth_required
@admin_required
async def get_roles():
    """
    Get list of valid roles (Admin only).

    Returns:
        roles: List of valid role names
        descriptions: Role descriptions
    """
    from .models import ROLE_DESCRIPTIONS

    response = RolesResponse(
        roles=VALID_ROLES,
        descriptions=ROLE_DESCRIPTIONS,
    )

    return jsonify(response.model_dump()), 200
