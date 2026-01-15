"""
Role and Scope Management API Endpoints.

Provides endpoints for managing custom roles and viewing available scopes.
"""

from __future__ import annotations

from quart import Blueprint, jsonify, request, g
from werkzeug.exceptions import BadRequest, NotFound

from .auth import auth_required
from .rbac import require_scope, SCOPES, ROLE_SCOPES, TEAM_ROLE_SCOPES, RESOURCE_ROLE_SCOPES
from .models import get_db

roles_bp = Blueprint('roles', __name__)


@roles_bp.route('/scopes', methods=['GET'])
@auth_required
async def list_scopes():
    """
    List all available scopes in the system.

    Returns:
        {
            "data": [
                {"name": "users:read", "description": "Read user data"},
                ...
            ]
        }
    """
    scopes_list = [
        {'name': name, 'description': desc}
        for name, desc in SCOPES.items()
    ]
    return jsonify({'data': scopes_list}), 200


@roles_bp.route('/roles', methods=['GET'])
@auth_required
async def list_roles():
    """
    List all roles with their assigned scopes.

    Query params:
        level: Filter by scope level (global, team, resource)

    Returns:
        {
            "data": [
                {
                    "id": 1,
                    "name": "admin",
                    "description": "Full system access",
                    "scopes": ["users:read", "users:write", ...],
                    "is_custom": false
                },
                ...
            ]
        }
    """
    db = get_db()
    level_filter = request.args.get('level')  # global, team, resource

    # Get all roles
    roles = db(db.auth_role).select().as_list()

    result = []
    for role in roles:
        # Get scopes for this role
        role_scopes = db(
            (db.role_scopes.role_id == role['id']) &
            (db.role_scopes.scope_id == db.scopes.id)
        ).select(db.scopes.name).as_list()

        scope_names = [rs['name'] for rs in role_scopes]

        # Filter by level if specified
        if level_filter:
            if level_filter == 'global' and not role['name'] in ROLE_SCOPES:
                continue
            if level_filter == 'team' and not role['name'] in TEAM_ROLE_SCOPES:
                continue
            if level_filter == 'resource' and not role['name'] in RESOURCE_ROLE_SCOPES:
                continue

        result.append({
            'id': role['id'],
            'name': role['name'],
            'description': role['description'],
            'scopes': scope_names,
            'is_custom': role['name'] not in {**ROLE_SCOPES, **TEAM_ROLE_SCOPES, **RESOURCE_ROLE_SCOPES}.keys(),
        })

    return jsonify({'data': result}), 200


@roles_bp.route('/roles/custom', methods=['POST'])
@auth_required
@require_scope('users:admin', 'system:admin')
async def create_custom_role():
    """
    Create a custom role with selected scopes.

    Requires: users:admin or system:admin scope

    Body:
        {
            "name": "analytics_viewer",
            "description": "Can view analytics only",
            "scopes": ["analytics:read", "urls:read"],
            "level": "global"  // global, team, or resource
        }
    """
    data = await request.get_json()

    if not data or 'name' not in data or 'scopes' not in data:
        raise BadRequest('name and scopes are required')

    role_name = data['name']
    description = data.get('description', '')
    selected_scopes = data['scopes']
    level = data.get('level', 'global')

    # Validate level
    if level not in ['global', 'team', 'resource']:
        raise BadRequest('level must be global, team, or resource')

    # Validate scopes
    available_scopes = set(SCOPES.keys())
    if not set(selected_scopes).issubset(available_scopes):
        invalid_scopes = set(selected_scopes) - available_scopes
        raise BadRequest(f'Invalid scopes: {", ".join(invalid_scopes)}')

    db = get_db()
    user_id = g.current_user['id']

    # Check if role name already exists
    existing = db(db.auth_role.name == role_name).select().first()
    if existing:
        raise BadRequest(f'Role {role_name} already exists')

    # Create custom role
    role_id = db.auth_role.insert(
        name=role_name,
        description=description,
    )

    # Record as custom role
    db.custom_roles.insert(
        name=role_name,
        description=description,
        created_by=user_id,
        scope_level=level,
    )

    # Assign scopes to role
    for scope_name in selected_scopes:
        scope = db(db.scopes.name == scope_name).select().first()
        if scope:
            db.role_scopes.insert(
                role_id=role_id,
                scope_id=scope.id,
            )

    db.commit()

    # Return created role
    role = db(db.auth_role.id == role_id).select().first()
    return jsonify({
        'data': {
            'id': role.id,
            'name': role.name,
            'description': role.description,
            'scopes': selected_scopes,
            'level': level,
            'is_custom': True,
        }
    }), 201


@roles_bp.route('/roles/<int:role_id>', methods=['DELETE'])
@auth_required
@require_scope('users:admin', 'system:admin')
async def delete_custom_role(role_id: int):
    """
    Delete a custom role.

    Requires: users:admin or system:admin scope

    Note: Cannot delete built-in roles (admin, maintainer, viewer, etc.)
    """
    db = get_db()

    # Check if it's a custom role
    custom_role = db(
        (db.custom_roles.name == db.auth_role.name) &
        (db.auth_role.id == role_id)
    ).select(db.custom_roles.ALL).first()

    if not custom_role:
        raise BadRequest('Cannot delete built-in role')

    # Delete role (cascades to role_scopes and user_role_assignments)
    db(db.auth_role.id == role_id).delete()
    db(db.custom_roles.id == custom_role.id).delete()
    db.commit()

    return jsonify({'message': 'Custom role deleted'}), 200


@roles_bp.route('/users/<int:user_id>/roles', methods=['POST'])
@auth_required
@require_scope('users:admin')
async def assign_role_to_user(user_id: int):
    """
    Assign a role to a user at a specific scope level.

    Requires: users:admin scope

    Body:
        {
            "role_id": 1,
            "scope_level": "global",  // global, team, or resource
            "scope_id": null  // team_id or resource_id (required for team/resource level)
        }
    """
    data = await request.get_json()

    if not data or 'role_id' not in data or 'scope_level' not in data:
        raise BadRequest('role_id and scope_level are required')

    role_id = data['role_id']
    scope_level = data['scope_level']
    scope_id = data.get('scope_id')

    # Validate scope_level
    if scope_level not in ['global', 'team', 'resource']:
        raise BadRequest('scope_level must be global, team, or resource')

    # Validate scope_id for team/resource levels
    if scope_level in ['team', 'resource'] and not scope_id:
        raise BadRequest(f'scope_id is required for {scope_level} level')

    db = get_db()

    # Verify user exists
    user = db(db.auth_user.id == user_id).select().first()
    if not user:
        raise NotFound('User not found')

    # Verify role exists
    role = db(db.auth_role.id == role_id).select().first()
    if not role:
        raise NotFound('Role not found')

    # Remove existing role assignment at this scope level/id
    db(
        (db.user_role_assignments.user_id == user_id) &
        (db.user_role_assignments.scope_level == scope_level) &
        (db.user_role_assignments.scope_id == scope_id if scope_id else db.user_role_assignments.scope_id == None)
    ).delete()

    # Create new role assignment
    db.user_role_assignments.insert(
        user_id=user_id,
        role_id=role_id,
        scope_level=scope_level,
        scope_id=scope_id,
    )

    # Also update legacy auth_user_roles table for global roles
    if scope_level == 'global':
        # Remove existing global role
        db(db.auth_user_roles.user_id == user_id).delete()
        # Add new global role
        db.auth_user_roles.insert(user_id=user_id, role_id=role_id)

    db.commit()

    return jsonify({'message': 'Role assigned successfully'}), 200


@roles_bp.route('/users/<int:user_id>/roles', methods=['GET'])
@auth_required
@require_scope('users:read')
async def get_user_roles(user_id: int):
    """
    Get all role assignments for a user.

    Requires: users:read scope

    Returns:
        {
            "data": [
                {
                    "role_id": 1,
                    "role_name": "admin",
                    "scope_level": "global",
                    "scope_id": null
                },
                {
                    "role_id": 4,
                    "role_name": "team_admin",
                    "scope_level": "team",
                    "scope_id": 5,
                    "scope_name": "Engineering Team"
                },
                ...
            ]
        }
    """
    db = get_db()

    # Get user's role assignments
    assignments = db(
        (db.user_role_assignments.user_id == user_id) &
        (db.user_role_assignments.role_id == db.auth_role.id)
    ).select(
        db.user_role_assignments.ALL,
        db.auth_role.name,
    ).as_list()

    result = []
    for assignment in assignments:
        role_data = {
            'role_id': assignment['user_role_assignments']['role_id'],
            'role_name': assignment['auth_role']['name'],
            'scope_level': assignment['user_role_assignments']['scope_level'],
            'scope_id': assignment['user_role_assignments']['scope_id'],
        }

        # Add scope name if applicable
        if assignment['user_role_assignments']['scope_level'] == 'team':
            team = db(db.teams.id == assignment['user_role_assignments']['scope_id']).select().first()
            if team:
                role_data['scope_name'] = team.name

        result.append(role_data)

    return jsonify({'data': result}), 200
