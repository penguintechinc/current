"""
Team Management API Endpoints.

Implements team CRUD operations with scope-based permissions.
"""

from __future__ import annotations

from quart import Blueprint, jsonify, request, g
from werkzeug.exceptions import BadRequest, NotFound, Forbidden

from .auth import token_required
from .rbac import require_scope, get_user_scopes
from .models import get_db

teams_bp = Blueprint('teams', __name__)


@teams_bp.route('/teams', methods=['GET'])
@token_required
@require_scope('teams:read')
async def list_teams():
    """
    List all teams user has access to.

    Requires: teams:read scope
    """
    db = get_db()
    user_id = g.current_user['id']

    # If user has global teams:read, show all teams
    global_scopes = get_user_scopes(user_id)
    if 'teams:read' in global_scopes or 'teams:admin' in global_scopes:
        teams = db(db.teams).select(orderby=db.teams.created_at).as_list()
    else:
        # Show only teams user is member of
        teams = db(
            (db.team_members.user_id == user_id) &
            (db.team_members.team_id == db.teams.id)
        ).select(db.teams.ALL).as_list()

    return jsonify({'data': teams}), 200


@teams_bp.route('/teams', methods=['POST'])
@token_required
@require_scope('teams:write', 'teams:admin')
async def create_team():
    """
    Create a new team.

    Requires: teams:write or teams:admin scope

    Body:
        {
            "name": "Team Name",
            "description": "Optional description"
        }
    """
    data = await request.get_json()

    if not data or 'name' not in data:
        raise BadRequest('Team name is required')

    db = get_db()
    user_id = g.current_user['id']

    team_id = db.teams.insert(
        name=data['name'],
        description=data.get('description', ''),
        created_by=user_id,
    )

    # Add creator as team admin
    db.team_members.insert(
        team_id=team_id,
        user_id=user_id,
    )

    # Assign team_admin role to creator
    team_admin_role = db(db.auth_role.name == 'team_admin').select().first()
    if team_admin_role:
        db.user_role_assignments.insert(
            user_id=user_id,
            role_id=team_admin_role.id,
            scope_level='team',
            scope_id=team_id,
        )

    db.commit()

    team = db(db.teams.id == team_id).select().first()
    return jsonify({'data': team.as_dict()}), 201


@teams_bp.route('/teams/<int:team_id>', methods=['GET'])
@token_required
@require_scope('teams:read', team_id_param='team_id')
async def get_team(team_id: int):
    """
    Get team details.

    Requires: teams:read scope (global or team-level)
    """
    db = get_db()
    team = db(db.teams.id == team_id).select().first()

    if not team:
        raise NotFound('Team not found')

    # Get team members
    members = db(
        (db.team_members.team_id == team_id) &
        (db.team_members.user_id == db.auth_user.id)
    ).select(
        db.auth_user.id,
        db.auth_user.email,
        db.auth_user.full_name,
        db.team_members.added_at,
    ).as_list()

    team_data = team.as_dict()
    team_data['members'] = members

    return jsonify({'data': team_data}), 200


@teams_bp.route('/teams/<int:team_id>', methods=['PUT'])
@token_required
@require_scope('teams:write', 'teams:admin', team_id_param='team_id')
async def update_team(team_id: int):
    """
    Update team details.

    Requires: teams:write or teams:admin scope (global or team-level)
    """
    db = get_db()
    team = db(db.teams.id == team_id).select().first()

    if not team:
        raise NotFound('Team not found')

    data = await request.get_json()

    update_fields = {}
    if 'name' in data:
        update_fields['name'] = data['name']
    if 'description' in data:
        update_fields['description'] = data['description']

    if update_fields:
        db(db.teams.id == team_id).update(**update_fields)
        db.commit()

    updated_team = db(db.teams.id == team_id).select().first()
    return jsonify({'data': updated_team.as_dict()}), 200


@teams_bp.route('/teams/<int:team_id>', methods=['DELETE'])
@token_required
@require_scope('teams:admin', team_id_param='team_id')
async def delete_team(team_id: int):
    """
    Delete a team.

    Requires: teams:admin scope (global or team-level)
    """
    db = get_db()
    team = db(db.teams.id == team_id).select().first()

    if not team:
        raise NotFound('Team not found')

    # Delete team (cascades to team_members and role_assignments)
    db(db.teams.id == team_id).delete()
    db.commit()

    return jsonify({'message': 'Team deleted'}), 200


@teams_bp.route('/teams/<int:team_id>/members', methods=['POST'])
@token_required
@require_scope('teams:write', 'teams:admin', team_id_param='team_id')
async def add_team_member(team_id: int):
    """
    Add a user to a team.

    Requires: teams:write or teams:admin scope (global or team-level)

    Body:
        {
            "user_id": 123,
            "role": "team_viewer"  // team_admin, team_maintainer, or team_viewer
        }
    """
    db = get_db()
    team = db(db.teams.id == team_id).select().first()

    if not team:
        raise NotFound('Team not found')

    data = await request.get_json()
    if not data or 'user_id' not in data:
        raise BadRequest('user_id is required')

    user_id = data['user_id']
    role_name = data.get('role', 'team_viewer')

    # Validate role
    valid_team_roles = ['team_admin', 'team_maintainer', 'team_viewer']
    if role_name not in valid_team_roles:
        raise BadRequest(f'Invalid role. Must be one of: {", ".join(valid_team_roles)}')

    # Check if user exists
    user = db(db.auth_user.id == user_id).select().first()
    if not user:
        raise NotFound('User not found')

    # Check if already a member
    existing = db(
        (db.team_members.team_id == team_id) &
        (db.team_members.user_id == user_id)
    ).select().first()

    if not existing:
        db.team_members.insert(
            team_id=team_id,
            user_id=user_id,
        )

    # Assign role at team level
    role = db(db.auth_role.name == role_name).select().first()
    if role:
        # Remove existing team-level role assignments for this user in this team
        db(
            (db.user_role_assignments.user_id == user_id) &
            (db.user_role_assignments.scope_level == 'team') &
            (db.user_role_assignments.scope_id == team_id)
        ).delete()

        # Add new role assignment
        db.user_role_assignments.insert(
            user_id=user_id,
            role_id=role.id,
            scope_level='team',
            scope_id=team_id,
        )

    db.commit()

    return jsonify({'message': 'User added to team'}), 201


@teams_bp.route('/teams/<int:team_id>/members/<int:user_id>', methods=['DELETE'])
@token_required
@require_scope('teams:write', 'teams:admin', team_id_param='team_id')
async def remove_team_member(team_id: int, user_id: int):
    """
    Remove a user from a team.

    Requires: teams:write or teams:admin scope (global or team-level)
    """
    db = get_db()

    # Remove team membership
    db(
        (db.team_members.team_id == team_id) &
        (db.team_members.user_id == user_id)
    ).delete()

    # Remove team-level role assignments
    db(
        (db.user_role_assignments.user_id == user_id) &
        (db.user_role_assignments.scope_level == 'team') &
        (db.user_role_assignments.scope_id == team_id)
    ).delete()

    db.commit()

    return jsonify({'message': 'User removed from team'}), 200
