"""
Workflow management tools for the ServiceNow MCP server.

This module provides tools for viewing and managing workflows in ServiceNow.
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
    format_success_response,
    format_error_response,
)

logger = logging.getLogger(__name__)

# Table name constants
WORKFLOW_TABLE = "wf_workflow"
WORKFLOW_VERSION_TABLE = "wf_workflow_version"
WORKFLOW_ACTIVITY_TABLE = "wf_activity"


@mcp.tool()
def list_workflows(
    limit: int = Field(10, description="Maximum number of records to return"),
    offset: int = Field(0, description="Offset to start from"),
    active: Optional[bool] = Field(None, description="Filter by active status"),
    name: Optional[str] = Field(None, description="Filter by name (contains)"),
    query: Optional[str] = Field(None, description="Additional query string"),
) -> str:
    """
    List workflows from ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()

    query_params = {
        "sysparm_limit": limit,
        "sysparm_offset": offset,
    }
    
    # Build query string
    query_parts = []
    if active is not None:
        query_parts.append(f"active={str(active).lower()}")
    if name:
        query_parts.append(f"nameLIKE{name}")
    if query:
        query_parts.append(query)
    
    if query_parts:
        query_params["sysparm_query"] = "^".join(query_parts)
    
    try:
        url = f"{config.instance_url}/api/now/table/{WORKFLOW_TABLE}"
        response = http_client.get(url, headers=auth_manager.get_headers(), params=query_params)
        response.raise_for_status()
        
        result = response.json()
        workflows = result.get("result", [])
        
        output = {
            "workflows": workflows,
            "count": len(workflows),
            "total": int(response.headers.get("X-Total-Count", 0)),
        }
        return json.dumps(output, indent=2)

    except requests.RequestException as e:
        logger.error(f"Error listing workflows: {e}")
        return format_error_response("list workflows", e)


@mcp.tool()
def get_workflow_details(
    workflow_id: str = Field(..., description="Workflow ID or sys_id"),
    include_versions: bool = Field(False, description="Include workflow versions"),
) -> str:
    """
    Get detailed information about a specific workflow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    
    try:
        url = f"{config.instance_url}/api/now/table/{WORKFLOW_TABLE}/{workflow_id}"
        response = http_client.get(url, headers=auth_manager.get_headers())
        response.raise_for_status()
        
        result = response.json()
        return format_success_response("Workflow retrieved", workflow=result.get("result", {}))

    except requests.RequestException as e:
        logger.error(f"Error getting workflow details: {e}")
        return format_error_response("get workflow details", e)


@mcp.tool()
def list_workflow_versions(
    workflow_id: str = Field(..., description="Workflow ID or sys_id"),
    limit: int = Field(10, description="Maximum number of records to return"),
    offset: int = Field(0, description="Offset to start from"),
) -> str:
    """
    List versions of a specific workflow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    
    query_params = {
        "sysparm_query": f"workflow={workflow_id}",
        "sysparm_limit": limit,
        "sysparm_offset": offset,
    }
    
    try:
        url = f"{config.instance_url}/api/now/table/{WORKFLOW_VERSION_TABLE}"
        response = http_client.get(url, headers=auth_manager.get_headers(), params=query_params)
        response.raise_for_status()
        
        result = response.json()
        versions = result.get("result", [])
        
        output = {
            "versions": versions,
            "count": len(versions),
            "total": int(response.headers.get("X-Total-Count", 0)),
            "workflow_id": workflow_id,
        }
        return json.dumps(output, indent=2)

    except requests.RequestException as e:
        logger.error(f"Error listing workflow versions: {e}")
        return format_error_response("list workflow versions", e)


@mcp.tool()
def get_workflow_activities(
    workflow_id: str = Field(..., description="Workflow ID or sys_id"),
    version: Optional[str] = Field(None, description="Specific version to get activities for"),
) -> str:
    """
    Get activities for a specific workflow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    
    version_id = version
    
    # If no version specified, get the latest published version
    if not version_id:
        try:
            version_url = f"{config.instance_url}/api/now/table/{WORKFLOW_VERSION_TABLE}"
            version_params = {
                "sysparm_query": f"workflow={workflow_id}^published=true",
                "sysparm_limit": 1,
                "sysparm_orderby": "version DESC",
            }
            
            version_response = http_client.get(version_url, headers=auth_manager.get_headers(), params=version_params)
            version_response.raise_for_status()
            
            versions = version_response.json().get("result", [])
            if not versions:
                return f"No published versions found for workflow {workflow_id}"
            
            version_id = versions[0]["sys_id"]

        except requests.RequestException as e:
            logger.error(f"Error getting workflow version: {e}")
            return format_error_response("get workflow version", e)
    
    # Get activities for the version
    try:
        activities_url = f"{config.instance_url}/api/now/table/{WORKFLOW_ACTIVITY_TABLE}"
        activities_params = {
            "sysparm_query": f"workflow_version={version_id}",
            "sysparm_orderby": "order",
        }
        
        activities_response = http_client.get(activities_url, headers=auth_manager.get_headers(), params=activities_params)
        activities_response.raise_for_status()
        
        activities = activities_response.json().get("result", [])
        output = {
            "activities": activities,
            "count": len(activities),
            "workflow_id": workflow_id,
            "version_id": version_id,
        }
        return json.dumps(output, indent=2)

    except requests.RequestException as e:
        logger.error(f"Error getting workflow activities: {e}")
        return format_error_response("get workflow activities", e)


@mcp.tool()
def create_workflow(
    name: str = Field(..., description="Name of the workflow"),
    description: Optional[str] = Field(None, description="Description of the workflow"),
    table: Optional[str] = Field(None, description="Table the workflow applies to"),
    active: bool = Field(True, description="Whether the workflow is active"),
) -> str:
    """
    Create a new workflow in ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    
    # Build request data using helper
    data = build_request_data(
        required_fields={"name": name},
        optional_fields={
            "description": description,
            "table": table,
            "active": active,
        }
    )
    
    try:
        url = f"{config.instance_url}/api/now/table/{WORKFLOW_TABLE}"
        response = http_client.post(url, headers=auth_manager.get_headers(), json=data)
        response.raise_for_status()
        
        result = response.json()
        return format_success_response("Workflow created successfully", workflow=result.get("result", {}))

    except requests.RequestException as e:
        logger.error(f"Error creating workflow: {e}")
        return format_error_response("create workflow", e)


@mcp.tool()
def update_workflow(
    workflow_id: str = Field(..., description="Workflow ID or sys_id"),
    name: Optional[str] = Field(None, description="Name of the workflow"),
    description: Optional[str] = Field(None, description="Description of the workflow"),
    table: Optional[str] = Field(None, description="Table the workflow applies to"),
    active: Optional[bool] = Field(None, description="Whether the workflow is active"),
) -> str:
    """
    Update an existing workflow in ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    
    # Build request data using helper
    data = build_request_data(
        required_fields={},
        optional_fields={
            "name": name,
            "description": description,
            "table": table,
            "active": active,
        }
    )
    
    if not data:
        return "No update parameters provided"
    
    try:
        url = f"{config.instance_url}/api/now/table/{WORKFLOW_TABLE}/{workflow_id}"
        response = http_client.patch(url, headers=auth_manager.get_headers(), json=data)
        response.raise_for_status()
        
        result = response.json()
        return format_success_response("Workflow updated successfully", workflow=result.get("result", {}))

    except requests.RequestException as e:
        logger.error(f"Error updating workflow: {e}")
        return format_error_response("update workflow", e)


@mcp.tool()
def activate_workflow(
    workflow_id: str = Field(..., description="Workflow ID or sys_id"),
) -> str:
    """
    Activate a workflow in ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    
    try:
        url = f"{config.instance_url}/api/now/table/{WORKFLOW_TABLE}/{workflow_id}"
        response = http_client.patch(url, headers=auth_manager.get_headers(), json={"active": "true"})
        response.raise_for_status()
        
        result = response.json()
        return format_success_response("Workflow activated successfully", workflow=result.get("result", {}))

    except requests.RequestException as e:
        logger.error(f"Error activating workflow: {e}")
        return format_error_response("activate workflow", e)


@mcp.tool()
def deactivate_workflow(
    workflow_id: str = Field(..., description="Workflow ID or sys_id"),
) -> str:
    """
    Deactivate a workflow in ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    
    try:
        url = f"{config.instance_url}/api/now/table/{WORKFLOW_TABLE}/{workflow_id}"
        response = http_client.patch(url, headers=auth_manager.get_headers(), json={"active": "false"})
        response.raise_for_status()
        
        result = response.json()
        return format_success_response("Workflow deactivated successfully", workflow=result.get("result", {}))

    except requests.RequestException as e:
        logger.error(f"Error deactivating workflow: {e}")
        return format_error_response("deactivate workflow", e)
