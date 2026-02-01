"""
Workflow management tools for the ServiceNow MCP server.

This module provides tools for viewing and managing workflows in ServiceNow.
"""

import logging
from typing import Any, Dict, List, Optional
import json

import requests
from pydantic import Field

from servicenow_mcp.application import mcp, get_auth_manager, get_config
from servicenow_mcp.utils import http_client

logger = logging.getLogger(__name__)


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

    # Convert parameters to ServiceNow query format
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
    
    # Make the API request
    try:
        headers = auth_manager.get_headers()
        url = f"{config.instance_url}/api/now/table/wf_workflow"
        
        response = http_client.get(url, headers=headers, params=query_params)
        response.raise_for_status()
        
        result = response.json()
        output = {
            "workflows": result.get("result", []),
            "count": len(result.get("result", [])),
            "total": int(response.headers.get("X-Total-Count", 0)),
        }
        return json.dumps(output, indent=2)
    except requests.RequestException as e:
        logger.error(f"Error listing workflows: {e}")
        return f"Error listing workflows: {str(e)}"


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
    
    # Make the API request
    try:
        headers = auth_manager.get_headers()
        url = f"{config.instance_url}/api/now/table/wf_workflow/{workflow_id}"
        
        response = http_client.get(url, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        output = {
            "workflow": result.get("result", {}),
        }
        return json.dumps(output, indent=2)
    except requests.RequestException as e:
        logger.error(f"Error getting workflow details: {e}")
        return f"Error getting workflow details: {str(e)}"


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
    
    # Convert parameters to ServiceNow query format
    query_params = {
        "sysparm_query": f"workflow={workflow_id}",
        "sysparm_limit": limit,
        "sysparm_offset": offset,
    }
    
    # Make the API request
    try:
        headers = auth_manager.get_headers()
        url = f"{config.instance_url}/api/now/table/wf_workflow_version"
        
        response = http_client.get(url, headers=headers, params=query_params)
        response.raise_for_status()
        
        result = response.json()
        output = {
            "versions": result.get("result", []),
            "count": len(result.get("result", [])),
            "total": int(response.headers.get("X-Total-Count", 0)),
            "workflow_id": workflow_id,
        }
        return json.dumps(output, indent=2)
    except requests.RequestException as e:
        logger.error(f"Error listing workflow versions: {e}")
        return f"Error listing workflow versions: {str(e)}"


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
            headers = auth_manager.get_headers()
            version_url = f"{config.instance_url}/api/now/table/wf_workflow_version"
            version_params = {
                "sysparm_query": f"workflow={workflow_id}^published=true",
                "sysparm_limit": 1,
                "sysparm_orderby": "version DESC",
            }
            
            version_response = http_client.get(version_url, headers=headers, params=version_params)
            version_response.raise_for_status()
            
            version_result = version_response.json()
            versions = version_result.get("result", [])
            
            if not versions:
                return f"No published versions found for workflow {workflow_id}"
            
            version_id = versions[0]["sys_id"]
        except requests.RequestException as e:
            logger.error(f"Error getting workflow version: {e}")
            return f"Error getting workflow version: {str(e)}"
    
    # Get activities for the version
    try:
        headers = auth_manager.get_headers()
        activities_url = f"{config.instance_url}/api/now/table/wf_activity"
        activities_params = {
            "sysparm_query": f"workflow_version={version_id}",
            "sysparm_orderby": "order",
        }
        
        activities_response = http_client.get(activities_url, headers=headers, params=activities_params)
        activities_response.raise_for_status()
        
        activities_result = activities_response.json()
        output = {
            "activities": activities_result.get("result", []),
            "count": len(activities_result.get("result", [])),
            "workflow_id": workflow_id,
            "version_id": version_id,
        }
        return json.dumps(output, indent=2)
    except requests.RequestException as e:
        logger.error(f"Error getting workflow activities: {e}")
        return f"Error getting workflow activities: {str(e)}"


@mcp.tool()
def create_workflow(
    name: str = Field(..., description="Name of the workflow"),
    description: Optional[str] = Field(None, description="Description of the workflow"),
    table: Optional[str] = Field(None, description="Table the workflow applies to"),
    active: bool = Field(True, description="Whether the workflow is active"),
    # Accessing dict argument in FastMCP tools can be tricky if expecting complex JSON.
    # FastMCP supports complex types but for simplicity we'll avoid specialized parsing if not needed.
    # If attributes is complex, it should be a JSON string or simplified.
    # Given previous code used Dict[str, Any], we'll assume the client sends valid JSON or dict.
) -> str:
    """
    Create a new workflow in ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    
    # Prepare data for the API request
    data = {
        "name": name,
    }
    
    if description:
        data["description"] = description
    
    if table:
        data["table"] = table
    
    data["active"] = str(active).lower()
    
    # Make the API request
    try:
        headers = auth_manager.get_headers()
        url = f"{config.instance_url}/api/now/table/wf_workflow"
        
        response = http_client.post(url, headers=headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        output = {
            "workflow": result.get("result", {}),
            "message": "Workflow created successfully",
        }
        return json.dumps(output, indent=2)
    except requests.RequestException as e:
        logger.error(f"Error creating workflow: {e}")
        return f"Error creating workflow: {str(e)}"


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
    
    # Prepare data for the API request
    data = {}
    
    if name:
        data["name"] = name
    
    if description is not None:
        data["description"] = description
    
    if table:
        data["table"] = table
    
    if active is not None:
        data["active"] = str(active).lower()
    
    if not data:
        return "No update parameters provided"
    
    # Make the API request
    try:
        headers = auth_manager.get_headers()
        url = f"{config.instance_url}/api/now/table/wf_workflow/{workflow_id}"
        
        response = http_client.patch(url, headers=headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        output = {
            "workflow": result.get("result", {}),
            "message": "Workflow updated successfully",
        }
        return json.dumps(output, indent=2)
    except requests.RequestException as e:
        logger.error(f"Error updating workflow: {e}")
        return f"Error updating workflow: {str(e)}"


@mcp.tool()
def activate_workflow(
    workflow_id: str = Field(..., description="Workflow ID or sys_id"),
) -> str:
    """
    Activate a workflow in ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    
    data = {"active": "true"}
    
    # Make the API request
    try:
        headers = auth_manager.get_headers()
        url = f"{config.instance_url}/api/now/table/wf_workflow/{workflow_id}"
        
        response = http_client.patch(url, headers=headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        output = {
            "workflow": result.get("result", {}),
            "message": "Workflow activated successfully",
        }
        return json.dumps(output, indent=2)
    except requests.RequestException as e:
        logger.error(f"Error activating workflow: {e}")
        return f"Error activating workflow: {str(e)}"

@mcp.tool()
def deactivate_workflow(
    workflow_id: str = Field(..., description="Workflow ID or sys_id"),
) -> str:
    """
    Deactivate a workflow in ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    
    data = {"active": "false"}
    
    # Make the API request
    try:
        headers = auth_manager.get_headers()
        url = f"{config.instance_url}/api/now/table/wf_workflow/{workflow_id}"
        
        response = http_client.patch(url, headers=headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        output = {
            "workflow": result.get("result", {}),
            "message": "Workflow deactivated successfully",
        }
        return json.dumps(output, indent=2)
    except requests.RequestException as e:
        logger.error(f"Error deactivating workflow: {e}")
        return f"Error deactivating workflow: {str(e)}"
