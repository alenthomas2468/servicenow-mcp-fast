"""
User management tools for the ServiceNow MCP server.

This module provides tools for managing users and groups in ServiceNow.
"""

import logging
from typing import List, Optional
import json

import requests
from pydantic import Field

from servicenow_mcp.application import mcp, get_auth_manager, get_config
from servicenow_mcp.utils import http_client

logger = logging.getLogger(__name__)


# --- Helper Functions ---

def get_role_id(
    role_name: str,
) -> Optional[str]:
    """Get the sys_id of a role by its name."""
    config = get_config()
    auth_manager = get_auth_manager()
    
    api_url = f"{config.api_url}/table/sys_user_role"
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
        if not result:
            return None

        return result[0].get("sys_id")

    except requests.RequestException as e:
        logger.error(f"Failed to get role ID: {e}")
        return None


def check_user_has_role(
    user_id: str,
    role_id: str,
) -> bool:
    """Check if a user has a specific role."""
    config = get_config()
    auth_manager = get_auth_manager()
    
    api_url = f"{config.api_url}/table/sys_user_has_role"
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


def assign_roles_to_user_impl(
    user_id: str,
    roles: List[str],
) -> bool:
    """Assign roles to a user in ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()
    
    api_url = f"{config.api_url}/table/sys_user_has_role"

    success = True
    for role in roles:
        # First check if the role exists
        role_id = get_role_id(role)
        if not role_id:
            logger.warning(f"Role '{role}' not found, skipping assignment")
            continue

        # Check if the user already has this role
        if check_user_has_role(user_id, role_id):
            logger.info(f"User already has role '{role}', skipping assignment")
            continue

        # Create the user role assignment
        data = {
            "user": user_id,
            "role": role_id,
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
    api_url = f"{config.api_url}/table/sys_user"

    # Build request data
    data = {
        "user_name": user_name,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "active": str(active).lower(),
    }

    if title:
        data["title"] = title
    if department:
        data["department"] = department
    if manager:
        data["manager"] = manager
    if phone:
        data["phone"] = phone
    if mobile_phone:
        data["mobile_phone"] = mobile_phone
    if location:
        data["location"] = location
    if password:
        data["user_password"] = password

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

        # Handle role assignments if provided
        if roles and result.get("sys_id"):
            assign_roles_to_user_impl(result.get("sys_id"), roles)

        output = {
            "success": True,
            "message": "User created successfully",
            "user_id": result.get("sys_id"),
            "user_name": result.get("user_name"),
        }
        return json.dumps(output, indent=2)

    except requests.RequestException as e:
        logger.error(f"Failed to create user: {e}")
        return f"Failed to create user: {str(e)}"


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
    api_url = f"{config.api_url}/table/sys_user/{user_id}"

    # Build request data
    data = {}
    if user_name:
        data["user_name"] = user_name
    if first_name:
        data["first_name"] = first_name
    if last_name:
        data["last_name"] = last_name
    if email:
        data["email"] = email
    if title:
        data["title"] = title
    if department:
        data["department"] = department
    if manager:
        data["manager"] = manager
    if phone:
        data["phone"] = phone
    if mobile_phone:
        data["mobile_phone"] = mobile_phone
    if location:
        data["location"] = location
    if password:
        data["user_password"] = password
    if active is not None:
        data["active"] = str(active).lower()

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

        output = {
            "success": True,
            "message": "User updated successfully",
            "user_id": result.get("sys_id"),
            "user_name": result.get("user_name"),
        }
        return json.dumps(output, indent=2)

    except requests.RequestException as e:
        logger.error(f"Failed to update user: {e}")
        return f"Failed to update user: {str(e)}"


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
    
    api_url = f"{config.api_url}/table/sys_user"
    query_params = {}

    # Build query parameters
    if user_id:
        query_params["sysparm_query"] = f"sys_id={user_id}"
    elif user_name:
        query_params["sysparm_query"] = f"user_name={user_name}"
    elif email:
        query_params["sysparm_query"] = f"email={email}"
    else:
        return "At least one search parameter is required"

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
            return "User not found"

        return json.dumps(result[0], indent=2)

    except requests.RequestException as e:
        logger.error(f"Failed to get user: {e}")
        return f"Failed to get user: {str(e)}"


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
    
    api_url = f"{config.api_url}/table/sys_user"
    query_params = {
        "sysparm_limit": str(limit),
        "sysparm_offset": str(offset),
        "sysparm_display_value": "true",
    }

    # Build query
    query_parts = []
    if active is not None:
        query_parts.append(f"active={str(active).lower()}")
    if department:
        query_parts.append(f"department={department}")
    if query:
        query_parts.append(
            f"^nameLIKE{query}^ORuser_nameLIKE{query}^ORemailLIKE{query}"
        )

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

        output = {
            "users": result,
            "count": len(result),
        }
        return json.dumps(output, indent=2)

    except requests.RequestException as e:
        logger.error(f"Failed to list users: {e}")
        return f"Failed to list users: {str(e)}"


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
        return "Roles assigned successfully"
    else:
        return "Failed to assign some or all roles"


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
    api_url = f"{config.api_url}/table/sys_user_group"

    # Build request data
    data = {
        "name": name,
        "active": str(active).lower(),
    }

    if description:
        data["description"] = description
    if manager:
        data["manager"] = manager
    if parent:
        data["parent"] = parent
    if type:
        data["type"] = type
    if email:
        data["email"] = email

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

        output = {
            "success": True,
            "message": "Group created successfully",
            "group_id": group_id,
            "group_name": result.get("name"),
        }
        return json.dumps(output, indent=2)

    except requests.RequestException as e:
        logger.error(f"Failed to create group: {e}")
        return f"Failed to create group: {str(e)}"


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
    api_url = f"{config.api_url}/table/sys_user_group/{group_id}"

    # Build request data
    data = {}
    if name:
        data["name"] = name
    if description:
        data["description"] = description
    if manager:
        data["manager"] = manager
    if parent:
        data["parent"] = parent
    if type:
        data["type"] = type
    if email:
        data["email"] = email
    if active is not None:
        data["active"] = str(active).lower()

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

        output = {
            "success": True,
            "message": "Group updated successfully",
            "group_id": result.get("sys_id"),
            "group_name": result.get("name"),
        }
        return json.dumps(output, indent=2)

    except requests.RequestException as e:
        logger.error(f"Failed to update group: {e}")
        return f"Failed to update group: {str(e)}"

def add_group_members_impl(
    group_id: str,
    members: List[str],
) -> dict:
    config = get_config()
    auth_manager = get_auth_manager()
    api_url = f"{config.api_url}/table/sys_user_grmember"

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
             u_api_url = f"{config.api_url}/table/sys_user"
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
    api_url = f"{config.api_url}/table/sys_user_group"
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
        
        output = {
            "groups": result,
            "count": len(result),
        }
        return json.dumps(output, indent=2)

    except requests.RequestException as e:
        logger.error(f"Failed to list groups: {e}")
        return f"Failed to list groups: {str(e)}"
