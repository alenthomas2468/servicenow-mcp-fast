"""
User management tools for the ServiceNow MCP server.

This module provides tools for managing users and groups in ServiceNow.
"""

import json
import logging
from typing import List, Optional

import requests
from pydantic import Field

from servicenow_mcp.application import mcp, get_auth_manager, get_config
from servicenow_mcp.utils import http_client
from servicenow_mcp.utils.helpers import (
    build_request_data,
    resolve_record_id,
    format_success_response,
    format_error_response,
    format_list_response,
    extract_display_value,
    is_sys_id,
    validate_pagination,
)

logger = logging.getLogger(__name__)

# Table name constants
USER_TABLE = "sys_user"
USER_ROLE_TABLE = "sys_user_role"
USER_HAS_ROLE_TABLE = "sys_user_has_role"
USER_GROUP_TABLE = "sys_user_group"
USER_GROUP_MEMBER_TABLE = "sys_user_grmember"


# --- Helper Functions ---

def get_role_id(role_name: str) -> Optional[str]:
    """Get the sys_id of a role by its name."""
    config = get_config()
    auth_manager = get_auth_manager()
    
    api_url = f"{config.api_url}/table/{USER_ROLE_TABLE}"
    query_params = {
        "sysparm_query": f"name={role_name}",
        "sysparm_limit": "1",
    }

    try:
        response = http_client.get(
            api_url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", [])
        return result[0].get("sys_id") if result else None

    except requests.RequestException as e:
        logger.error(f"Failed to get role ID: {e}")
        return None


def check_user_has_role(user_id: str, role_id: str) -> bool:
    """Check if a user has a specific role."""
    config = get_config()
    auth_manager = get_auth_manager()
    
    api_url = f"{config.api_url}/table/{USER_HAS_ROLE_TABLE}"
    query_params = {
        "sysparm_query": f"user={user_id}^role={role_id}",
        "sysparm_limit": "1",
    }

    try:
        response = http_client.get(
            api_url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", [])
        return len(result) > 0

    except requests.RequestException as e:
        logger.error(f"Failed to check if user has role: {e}")
        return False


def assign_roles_to_user_impl(user_id: str, roles: List[str]) -> bool:
    """Assign roles to a user in ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()
    
    api_url = f"{config.api_url}/table/{USER_HAS_ROLE_TABLE}"

    success = True
    for role in roles:
        role_id = get_role_id(role)
        if not role_id:
            logger.warning(f"Role '{role}' not found, skipping assignment")
            continue

        if check_user_has_role(user_id, role_id):
            logger.info(f"User already has role '{role}', skipping assignment")
            continue

        data = {"user": user_id, "role": role_id}

        try:
            response = http_client.post(
                api_url,
                json=data,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to assign role '{role}' to user: {e}")
            success = False

    return success

# --- MCP Tools ---

@mcp.tool()
def create_user(
    user_name: str = Field(..., description="Username for the user"),
    first_name: str = Field(..., description="First name of the user"),
    last_name: str = Field(..., description="Last name of the user"),
    email: str = Field(..., description="Email address of the user"),
    title: Optional[str] = Field(None, description="Job title of the user"),
    department: Optional[str] = Field(None, description="Department the user belongs to"),
    manager: Optional[str] = Field(None, description="Manager of the user (sys_id or username)"),
    roles: Optional[List[str]] = Field(None, description="Roles to assign to the user"),
    phone: Optional[str] = Field(None, description="Phone number of the user"),
    mobile_phone: Optional[str] = Field(None, description="Mobile phone number of the user"),
    location: Optional[str] = Field(None, description="Location of the user"),
    password: Optional[str] = Field(None, description="Password for the user account"),
    active: bool = Field(True, description="Whether the user account is active"),
) -> str:
    """
    Create a new user in ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    api_url = f"{config.api_url}/table/{USER_TABLE}"

    # Build request data using helper
    data = build_request_data(
        required_fields={
            "user_name": user_name,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "active": active,
        },
        optional_fields={
            "title": title,
            "department": department,
            "manager": manager,
            "phone": phone,
            "mobile_phone": mobile_phone,
            "location": location,
            "user_password": password,  # Note: field name is user_password in ServiceNow
        }
    )

    try:
        response = http_client.post(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        # Handle role assignments if provided
        if roles and result.get("sys_id"):
            assign_roles_to_user_impl(result.get("sys_id"), roles)

        return format_success_response(
            "User created successfully",
            user_id=result.get("sys_id"),
            user_name=result.get("user_name"),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to create user: {e}")
        return format_error_response("create user", e)


@mcp.tool()
def update_user(
    user_id: str = Field(..., description="User ID or sys_id to update"),
    user_name: Optional[str] = Field(None, description="Username for the user"),
    first_name: Optional[str] = Field(None, description="First name of the user"),
    last_name: Optional[str] = Field(None, description="Last name of the user"),
    email: Optional[str] = Field(None, description="Email address of the user"),
    title: Optional[str] = Field(None, description="Job title of the user"),
    department: Optional[str] = Field(None, description="Department the user belongs to"),
    manager: Optional[str] = Field(None, description="Manager of the user (sys_id or username)"),
    roles: Optional[List[str]] = Field(None, description="Roles to assign to the user"),
    phone: Optional[str] = Field(None, description="Phone number of the user"),
    mobile_phone: Optional[str] = Field(None, description="Mobile phone number of the user"),
    location: Optional[str] = Field(None, description="Location of the user"),
    password: Optional[str] = Field(None, description="Password for the user account"),
    active: Optional[bool] = Field(None, description="Whether the user account is active"),
) -> str:
    """
    Update an existing user in ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    api_url = f"{config.api_url}/table/{USER_TABLE}/{user_id}"

    # Build request data using helper
    data = build_request_data(
        required_fields={},
        optional_fields={
            "user_name": user_name,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "title": title,
            "department": department,
            "manager": manager,
            "phone": phone,
            "mobile_phone": mobile_phone,
            "location": location,
            "user_password": password,  # Note: password field name change
            "active": active,
        }
    )

    # Make request
    try:
        response = http_client.patch(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        # Handle role assignments if provided
        if roles:
            assign_roles_to_user_impl(user_id, roles)

        return format_success_response(
            "User updated successfully",
            user_id=result.get("sys_id"),
            user_name=result.get("user_name"),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to update user: {e}")
        return format_error_response("update user", e)


@mcp.tool()
def get_user(
    user_id: Optional[str] = Field(None, description="User ID or sys_id"),
    user_name: Optional[str] = Field(None, description="Username of the user"),
    email: Optional[str] = Field(None, description="Email address of the user"),
) -> str:
    """
    Get a user from ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    
    api_url = f"{config.api_url}/table/{USER_TABLE}"
    query_params = {}

    # Resolve user ID - determine which identifier to use
    identifier = user_id or user_name or email
    if not identifier:
        return format_error_response("get user", ValueError("At least one of user_id, user_name, or email is required"))
    
    lookup_field = "sys_id" if user_id and is_sys_id(user_id) else "user_name" if user_name else "email"
    resolved_id = resolve_record_id(USER_TABLE, identifier, lookup_field=lookup_field)
    if not resolved_id:
        return format_error_response("get user", ValueError(f"User not found: {identifier}"))
    
    # Build query parameters
    query_params["sysparm_query"] = f"sys_id={resolved_id}"

    query_params["sysparm_limit"] = "1"
    query_params["sysparm_display_value"] = "true"

    # Make request
    try:
        response = http_client.get(
            api_url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", [])
        if not result:
            return format_error_response("get user", ValueError("User not found"))

        return format_success_response(
            "User retrieved successfully",
            user=result[0],
        )

    except requests.RequestException as e:
        logger.error(f"Failed to get user: {e}")
        return format_error_response("get user", e)


@mcp.tool()
def list_users(
    limit: int = Field(10, description="Maximum number of users to return"),
    offset: int = Field(0, description="Offset for pagination"),
    active: Optional[bool] = Field(None, description="Filter by active status"),
    department: Optional[str] = Field(None, description="Filter by department"),
    query: Optional[str] = Field(
        None,
        description="Case-insensitive search term .",
    ),
) -> str:
    """
    List users from ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    limit, offset = validate_pagination(limit, offset)
    
    api_url = f"{config.api_url}/table/{USER_TABLE}"
    query_params = {
        "sysparm_limit": str(limit),
        "sysparm_offset": str(offset),
        "sysparm_display_value": "true",
    }

    # Build query
    filters = []
    if active is not None:
        filters.append(f"active={str(active).lower()}")
    if department:
        filters.append(f"department={department}")
    if query:
        filters.append(f"^nameLIKE{query}^ORuser_nameLIKE{query}^ORemailLIKE{query}")
    
    if filters:
        query_params["sysparm_query"] = "^".join(filters)

    # Make request
    try:
        response = http_client.get(
            api_url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", [])

        return format_list_response(result, "users", limit, offset)

    except requests.RequestException as e:
        logger.error(f"Failed to list users: {e}")
        return format_error_response("list users", e)


@mcp.tool()
def assign_roles_to_user(
    user_id: str = Field(..., description="User ID or sys_id"),
    roles: List[str] = Field(..., description="List of roles to assign"),
) -> str:
    """
    Assign roles to a user in ServiceNow.
    """
    success = assign_roles_to_user_impl(user_id, roles)
    if success:
        return format_success_response("Roles assigned successfully", user_id=user_id, roles=roles)
    else:
        return format_error_response("assign roles", ValueError("Failed to assign some or all roles"))


@mcp.tool()
def create_group(
    name: str = Field(..., description="Name of the group"),
    description: Optional[str] = Field(None, description="Description of the group"),
    manager: Optional[str] = Field(None, description="Manager of the group (sys_id or username)"),
    parent: Optional[str] = Field(None, description="Parent group (sys_id or name)"),
    type: Optional[str] = Field(None, description="Type of the group"),
    email: Optional[str] = Field(None, description="Email address for the group"),
    members: Optional[List[str]] = Field(
        None, description="List of user sys_ids or usernames to add as members"
    ),
    active: bool = Field(True, description="Whether the group is active"),
) -> str:
    """
    Create a new group in ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    api_url = f"{config.api_url}/table/{USER_GROUP_TABLE}"

    # Build request data using helper
    data = build_request_data(
        required_fields={"name": name},
        optional_fields={
            "description": description,
            "manager": manager,
            "parent": parent,
            "type": type,
            "email": email,
            "active": active,
        }
    )

    # Make request
    try:
        response = http_client.post(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})
        group_id = result.get("sys_id")

        # Add members if provided
        if members and group_id:
            add_group_members_impl(group_id, members)

        return format_success_response(
            "Group created successfully",
            group_id=group_id,
            group_name=result.get("name"),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to create group: {e}")
        return format_error_response("create group", e)


@mcp.tool()
def update_group(
    group_id: str = Field(..., description="Group ID or sys_id to update"),
    name: Optional[str] = Field(None, description="Name of the group"),
    description: Optional[str] = Field(None, description="Description of the group"),
    manager: Optional[str] = Field(None, description="Manager of the group (sys_id or username)"),
    parent: Optional[str] = Field(None, description="Parent group (sys_id or name)"),
    type: Optional[str] = Field(None, description="Type of the group"),
    email: Optional[str] = Field(None, description="Email address for the group"),
    active: Optional[bool] = Field(None, description="Whether the group is active"),
) -> str:
    """
    Update an existing group in ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    api_url = f"{config.api_url}/table/{USER_GROUP_TABLE}/{group_id}"

    # Build request data using helper
    data = build_request_data(
        required_fields={},
        optional_fields={
            "name": name,
            "description": description,
            "manager": manager,
            "parent": parent,
            "type": type,
            "email": email,
            "active": active,
        }
    )

    # Make request
    try:
        response = http_client.patch(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})

        return format_success_response(
            "Group updated successfully",
            group_id=result.get("sys_id"),
            group_name=result.get("name"),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to update group: {e}")
        return format_error_response("update group", e)

def add_group_members_impl(
    group_id: str,
    members: List[str],
) -> dict:
    config = get_config()
    auth_manager = get_auth_manager()
    api_url = f"{config.api_url}/table/{USER_GROUP_MEMBER_TABLE}"

    success = True
    failed_members = []
    
    # Need to access tools directly or via helper to resolve names
    # Reuse valid get_user logic if possible, or just reimplement resolution query
    
    for member in members:
        user_id = member
        # Simple heuristic to detect if it's already a sys_id (32 hex chars)
        if len(member) != 32 or any(c not in "0123456789abcdef" for c in member):
             # Try to resolve via username
             # NOTE: Invoking other tool functions directly from within tool works if they return values,
             # but here they return strings (JSON). We need direct logic.
             
             # Resolve user
             u_api_url = f"{config.api_url}/table/{USER_TABLE}"
             u_params = {"sysparm_query": f"user_name={member}", "sysparm_limit": "1"}
             try:
                resp = http_client.get(u_api_url, params=u_params, headers=auth_manager.get_headers(), timeout=config.timeout)
                if resp.status_code == 200:
                    results = resp.json().get("result", [])
                    if results:
                        user_id = results[0]["sys_id"]
                    else:
                        # Try email
                        u_params["sysparm_query"] = f"email={member}"
                        resp = http_client.get(u_api_url, params=u_params, headers=auth_manager.get_headers(), timeout=config.timeout)
                        if resp.status_code == 200:
                             results = resp.json().get("result", [])
                             if results:
                                 user_id = results[0]["sys_id"]
                             else:
                                 success = False
                                 failed_members.append(member)
                                 continue
             except Exception:
                 success=False
                 continue

        # Create group membership
        data = {
            "group": group_id,
            "user": user_id,
        }

        try:
            response = http_client.post(
                api_url,
                json=data,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to add member '{member}' to group: {e}")
            success = False
            failed_members.append(member)
            
    return {"success": success, "failed_members": failed_members}


@mcp.tool()
def add_group_members(
    group_id: str = Field(..., description="Group ID or sys_id"),
    members: List[str] = Field(
        ..., description="List of user sys_ids or usernames to add as members"
    ),
) -> str:
    """
    Add members to a group in ServiceNow.
    """
    result = add_group_members_impl(group_id, members)
    return json.dumps(result, indent=2)


@mcp.tool()
def list_groups(
    limit: int = Field(10, description="Maximum number of groups to return"),
    offset: int = Field(0, description="Offset for pagination"),
    active: Optional[bool] = Field(None, description="Filter by active status"),
    query: Optional[str] = Field(
        None,
        description="Case-insensitive search term.",
    ),
    type: Optional[str] = Field(None, description="Filter by group type"),
) -> str:
    """
    List groups from ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    api_url = f"{config.api_url}/table/{USER_GROUP_TABLE}"
    query_params = {
        "sysparm_limit": str(limit),
        "sysparm_offset": str(offset),
        "sysparm_display_value": "true",
    }

    # Build query
    query_parts = []
    if active is not None:
        query_parts.append(f"active={str(active).lower()}")
    if type:
        query_parts.append(f"type={type}")
    if query:
        query_parts.append(f"^nameLIKE{query}^ORdescriptionLIKE{query}")

    if query_parts:
        query_params["sysparm_query"] = "^".join(query_parts)

    # Make request
    try:
        response = http_client.get(
            api_url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", [])
        
        return format_list_response(result, "groups", limit, offset)

    except requests.RequestException as e:
        logger.error(f"Failed to list groups: {e}")
        return format_error_response("list groups", e)
