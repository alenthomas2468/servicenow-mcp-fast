"""
Script Include tools for the ServiceNow MCP server.

This module provides tools for managing script includes in ServiceNow.
"""

import json
import logging
from typing import Optional

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
)

logger = logging.getLogger(__name__)

# Table name constant
SCRIPT_INCLUDE_TABLE = "sys_script_include"

@mcp.tool()
def list_script_includes(
    limit: int = Field(10, description="Maximum number of script includes to return"),
    offset: int = Field(0, description="Offset for pagination"),
    active: Optional[bool] = Field(None, description="Filter by active status"),
    client_callable: Optional[bool] = Field(None, description="Filter by client callable status"),
    query: Optional[str] = Field(None, description="Search query for script includes"),
) -> str:
    """List script includes from ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    try:
        url = f"{config.api_url}/table/{SCRIPT_INCLUDE_TABLE}"
        query_params = {
            "sysparm_limit": str(limit),
            "sysparm_offset": str(offset),
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
            "sysparm_fields": "sys_id,name,script,description,api_name,client_callable,active,access,sys_created_on,sys_updated_on,sys_created_by,sys_updated_by"
        }
        
        # Add filters if provided
        query_parts = []
        if active is not None:
            query_parts.append(f"active={str(active).lower()}")
        if client_callable is not None:
            query_parts.append(f"client_callable={str(client_callable).lower()}")
        if query:
            query_parts.append(f"nameLIKE{query}")
            
        if query_parts:
            query_params["sysparm_query"] = "^".join(query_parts)
            
        response = http_client.get(
            url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        
        # Parse the response
        data = response.json()
        script_includes = []
        
        for item in data.get("result", []):
            script_include = {
                "sys_id": item.get("sys_id"),
                "name": item.get("name"),
                "description": item.get("description"),
                "api_name": item.get("api_name"),
                "client_callable": item.get("client_callable") == "true",
                "active": item.get("active") == "true",
                "access": item.get("access"),
                "created_on": item.get("sys_created_on"),
                "updated_on": item.get("sys_updated_on"),
                "created_by": extract_display_value(item.get("sys_created_by")),
                "updated_by": extract_display_value(item.get("sys_updated_by")),
            }
            script_includes.append(script_include)
            
        return format_list_response(script_includes, "script_includes", limit, offset)
        
    except Exception as e:
        logger.error(f"Error listing script includes: {e}")
        return format_error_response("list script includes", e)


@mcp.tool()
def get_script_include(
    script_include_id: str = Field(..., description="Script include ID or name"),
) -> str:
    """Get a specific script include from ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    try:
        query_params = {
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
            "sysparm_fields": "sys_id,name,script,description,api_name,client_callable,active,access,sys_created_on,sys_updated_on,sys_created_by,sys_updated_by"
        }
        
        # Determine if we're querying by sys_id or name
        if script_include_id.startswith("sys_id:") or is_sys_id(script_include_id):
            sys_id = script_include_id.replace("sys_id:", "")
            url = f"{config.api_url}/table/{SCRIPT_INCLUDE_TABLE}/{sys_id}"
        else:
            # Query by name
            url = f"{config.api_url}/table/{SCRIPT_INCLUDE_TABLE}"
            query_params["sysparm_query"] = f"name={script_include_id}"
            query_params["sysparm_limit"] = "1"
            
        response = http_client.get(
            url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        
        # Parse the response
        data = response.json()
        
        if "result" not in data:
             return f"Script include not found: {script_include_id}"
            
        # Handle both single result and list of results
        result = data["result"]
        if isinstance(result, list):
            if not result:
                return f"Script include not found: {script_include_id}"
            item = result[0]
        else:
            item = result
            
        script_include = {
            "sys_id": item.get("sys_id"),
            "name": item.get("name"),
            "script": item.get("script"),
            "description": item.get("description"),
            "api_name": item.get("api_name"),
            "client_callable": item.get("client_callable") == "true",
            "active": item.get("active") == "true",
            "access": item.get("access"),
            "created_on": item.get("sys_created_on"),
            "updated_on": item.get("sys_updated_on"),
            "created_by": extract_display_value(item.get("sys_created_by")),
            "updated_by": extract_display_value(item.get("sys_updated_by")),
        }
        
        return format_success_response(
            f"Found script include: {item.get('name')}",
            script_include=script_include,
        )
        
    except Exception as e:
        logger.error(f"Error getting script include: {e}")
        return format_error_response("get script include", e)


@mcp.tool()
def create_script_include(
    name: str = Field(..., description="Name of the script include"),
    script: str = Field(..., description="Script content"),
    description: Optional[str] = Field(None, description="Description of the script include"),
    api_name: Optional[str] = Field(None, description="API name of the script include"),
    client_callable: bool = Field(False, description="Whether the script include is client callable"),
    active: bool = Field(True, description="Whether the script include is active"),
    access: str = Field("package_private", description="Access level of the script include"),
) -> str:
    """Create a new script include in ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    url = f"{config.api_url}/table/{SCRIPT_INCLUDE_TABLE}"
    
    # Build request data using helper
    body = build_request_data(
        required_fields={
            "name": name,
            "script": script,
            "access": access,
        },
        optional_fields={
            "description": description,
            "api_name": api_name,
            "client_callable": client_callable,
            "active": active,
        }
    )
        
    try:
        response = http_client.post(
            url,
            json=body,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        
        data = response.json()
        
        if "result" not in data:
            return "Failed to create script include"
            
        result = data["result"]
        
        return format_success_response(
            f"Created script include: {result.get('name')}",
            script_include_id=result.get("sys_id"),
            script_include_name=result.get("name"),
        )
        
    except Exception as e:
        logger.error(f"Error creating script include: {e}")
        return format_error_response("create script include", e)


@mcp.tool()
def update_script_include(
    script_include_id: str = Field(..., description="Script include ID or name"),
    script: Optional[str] = Field(None, description="Script content"),
    description: Optional[str] = Field(None, description="Description of the script include"),
    api_name: Optional[str] = Field(None, description="API name of the script include"),
    client_callable: Optional[bool] = Field(None, description="Whether the script include is client callable"),
    active: Optional[bool] = Field(None, description="Whether the script include is active"),
    access: Optional[str] = Field(None, description="Access level of the script include"),
) -> str:
    """Update an existing script include in ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()
    
    # First, get the script include sys_id to update (in case name is passed)
    # We can reuse get_script_include logic properly by calling the function logic here,
    # but to avoid recursion and string parsing, let's just resolve the ID.
    
    sys_id_to_update = script_include_id
    if not (len(script_include_id) == 32 and all(c in "0123456789abcdef" for c in script_include_id)):
         # It's likely a name, need to resolve to sys_id
         search_url = f"{config.api_url}/table/{SCRIPT_INCLUDE_TABLE}"
         search_params = {"sysparm_query": f"name={script_include_id}", "sysparm_limit": "1", "sysparm_fields": "sys_id"}
         try:
             s_resp = http_client.get(search_url, params=search_params, headers=auth_manager.get_headers(), timeout=config.timeout)
             s_resp.raise_for_status()
             s_res = s_resp.json().get("result", [])
             if not s_res:
                 return f"Script include not found: {script_include_id}"
             sys_id_to_update = s_res[0]["sys_id"]
         except Exception as e:
             return f"Error resolving script include ID: {str(e)}"


    # Build the URL
    url = f"{config.api_url}/table/{SCRIPT_INCLUDE_TABLE}/{sys_id_to_update}"
    
    # Build the request body
    body = build_request_data(
        required_fields={},
        optional_fields={
            "script": script,
            "description": description,
            "api_name": api_name,
            "client_callable": client_callable,
            "active": active,
            "access": access,
        }
    )
        
    # If no fields to update, return success
    if not body:
         return format_error_response("update script include", ValueError("No changes provided to update"))
        
    # Make the request
    headers = auth_manager.get_headers()
    
    try:
        response = http_client.patch(
            url,
            json=body,
            headers=headers,
            timeout=config.timeout,
        )
        response.raise_for_status()
        
        # Parse the response
        data = response.json()
        
        if "result" not in data:
             return format_error_response("update script include", ValueError("No result in response"))
            
        result = data["result"]
        
        return format_success_response(
            f"Updated script include: {result.get('name')}",
            script_include_id=result.get("sys_id"),
            script_include_name=result.get("name"),
        )
        
    except Exception as e:
        logger.error(f"Error updating script include: {e}")
        return format_error_response("update script include", e)

