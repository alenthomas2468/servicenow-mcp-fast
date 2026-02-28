"""
Story management tools for the ServiceNow MCP server.

This module provides tools for managing stories in ServiceNow.
"""

import json
import logging
from datetime import datetime
from typing import Optional

import requests
from pydantic import Field

from servicenow_mcp.application import mcp, get_auth_manager, get_config
from servicenow_mcp.utils import http_client
from servicenow_mcp.utils.helpers import (
    build_request_data,
    format_success_response,
    format_error_response,
    format_list_response,
)

logger = logging.getLogger(__name__)

# Table name constants
STORY_TABLE = "rm_story"
STORY_DEPENDENCY_TABLE = "m2m_story_dependencies"


@mcp.tool()
def create_story(
    short_description: str = Field(..., description="Short description of the story"),
    acceptance_criteria: str = Field(..., description="Acceptance criteria for the story"),
    description: Optional[str] = Field(None, description="Detailed description of the story"),
    state: Optional[str] = Field(None, description="State of story (-6 is Draft,-7 is Ready for Testing,-8 is Testing,1 is Ready, 2 is Work in progress, 3 is Complete, 4 is Cancelled)"),
    assignment_group: Optional[str] = Field(None, description="Group assigned to the story"),
    story_points: int = Field(10, description="Points value for the story"),
    assigned_to: Optional[str] = Field(None, description="User assigned to the story"),
    epic: Optional[str] = Field(None, description="Epic that the story belongs to. It requires the System ID of the epic."),
    project: Optional[str] = Field(None, description="Project that the story belongs to. It requires the System ID of the project."),
    work_notes: Optional[str] = Field(None, description="Work notes to add to the story. Used for adding notes and comments to a story"),
) -> str:
    """
    Create a new story in ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    
    # Build request data using helper
    data = build_request_data(
        required_fields={
            "short_description": short_description,
            "acceptance_criteria": acceptance_criteria,
            "story_points": story_points,
        },
        optional_fields={
            "description": description,
            "state": state,
            "assignment_group": assignment_group,
            "assigned_to": assigned_to,
            "epic": epic,
            "project": project,
            "work_notes": work_notes,
        }
    )
    
    try:
        url = f"{config.api_url}/table/{STORY_TABLE}"
        response = http_client.post(url, json=data, headers=auth_manager.get_headers())
        response.raise_for_status()
        
        result = response.json()
        return format_success_response("Story created successfully", story=result["result"])

    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating story: {e}")
        return format_error_response("create story", e)


@mcp.tool()
def update_story(
    story_id: str = Field(..., description="Story IDNumber or sys_id. You will need to fetch the story to get the sys_id if you only have the story number"),
    short_description: Optional[str] = Field(None, description="Short description of the story"),
    acceptance_criteria: Optional[str] = Field(None, description="Acceptance criteria for the story"),
    description: Optional[str] = Field(None, description="Detailed description of the story"),
    state: Optional[str] = Field(None, description="State of story (-6 is Draft,-7 is Ready for Testing,-8 is Testing,1 is Ready, 2 is Work in progress, 3 is Complete, 4 is Cancelled)"),
    assignment_group: Optional[str] = Field(None, description="Group assigned to the story"),
    story_points: Optional[int] = Field(None, description="Points value for the story"),
    assigned_to: Optional[str] = Field(None, description="User assigned to the story"),
    epic: Optional[str] = Field(None, description="Epic that the story belongs to. It requires the System ID of the epic."),
    project: Optional[str] = Field(None, description="Project that the story belongs to. It requires the System ID of the project."),
    work_notes: Optional[str] = Field(None, description="Work notes to add to the story. Used for adding notes and comments to a story"),
) -> str:
    """
    Update an existing story in ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    
    # Build request data using helper
    data = build_request_data(
        required_fields={},
        optional_fields={
            "short_description": short_description,
            "acceptance_criteria": acceptance_criteria,
            "description": description,
            "state": state,
            "assignment_group": assignment_group,
            "story_points": story_points,
            "assigned_to": assigned_to,
            "epic": epic,
            "project": project,
            "work_notes": work_notes,
        }
    )
    
    try:
        url = f"{config.api_url}/table/{STORY_TABLE}/{story_id}"
        response = http_client.put(url, json=data, headers=auth_manager.get_headers())
        response.raise_for_status()
        
        result = response.json()
        return format_success_response("Story updated successfully", story=result["result"])

    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating story: {e}")
        return format_error_response("update story", e)


@mcp.tool()
def list_stories(
    limit: int = Field(10, description="Maximum number of records to return"),
    offset: int = Field(0, description="Offset to start from"),
    state: Optional[str] = Field(None, description="Filter by state"),
    assignment_group: Optional[str] = Field(None, description="Filter by assignment group"),
    timeframe: Optional[str] = Field(None, description="Filter by timeframe (upcoming, in-progress, completed)"),
    query: Optional[str] = Field(None, description="Additional query string"),
) -> str:
    """
    List stories from ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    
    # Build the query
    query_parts = []
    
    if state:
        query_parts.append(f"state={state}")
    if assignment_group:
        query_parts.append(f"assignment_group={assignment_group}")
    
    # Handle timeframe filtering
    if timeframe:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if timeframe == "upcoming":
            query_parts.append(f"start_date>{now}")
        elif timeframe == "in-progress":
            query_parts.append(f"start_date<{now}^end_date>{now}")
        elif timeframe == "completed":
            query_parts.append(f"end_date<{now}")
    
    if query:
        query_parts.append(query)
    
    params = {
        "sysparm_limit": limit,
        "sysparm_offset": offset,
        "sysparm_query": "^".join(query_parts) if query_parts else "",
        "sysparm_display_value": "true",
    }
    
    try:
        url = f"{config.api_url}/table/{STORY_TABLE}"
        response = http_client.get(url, headers=auth_manager.get_headers(), params=params)
        response.raise_for_status()
        
        stories = response.json().get("result", [])
        return format_list_response(stories, "stories", limit, offset)

    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing stories: {e}")
        return format_error_response("list stories", e)


@mcp.tool()
def list_story_dependencies(
    limit: int = Field(10, description="Maximum number of records to return"),
    offset: int = Field(0, description="Offset to start from"),
    query: Optional[str] = Field(None, description="Additional query string"),
    dependent_story: Optional[str] = Field(None, description="Sys_id of the dependent story is required"),
    prerequisite_story: Optional[str] = Field(None, description="Sys_id that this story depends on is required"),
) -> str:
    """
    List story dependencies from ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    
    # Build the query
    query_parts = []
    if dependent_story:
        query_parts.append(f"dependent_story={dependent_story}")
    if prerequisite_story:
        query_parts.append(f"prerequisite_story={prerequisite_story}")
    if query:
        query_parts.append(query)
    
    params = {
        "sysparm_limit": limit,
        "sysparm_offset": offset,
        "sysparm_query": "^".join(query_parts) if query_parts else "",
        "sysparm_display_value": "true",
    }
    
    try:
        url = f"{config.api_url}/table/{STORY_DEPENDENCY_TABLE}"
        response = http_client.get(url, headers=auth_manager.get_headers(), params=params)
        response.raise_for_status()
        
        dependencies = response.json().get("result", [])
        return format_list_response(dependencies, "story_dependencies", limit, offset)

    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing story dependencies: {e}")
        return format_error_response("list story dependencies", e)


@mcp.tool()
def create_story_dependency(
    dependent_story: str = Field(..., description="Sys_id of the dependent story is required"),
    prerequisite_story: str = Field(..., description="Sys_id that this story depends on is required"),
) -> str:
    """
    Create a dependency between two stories in ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    
    data = {
        "dependent_story": dependent_story,
        "prerequisite_story": prerequisite_story,
    }
    
    try:
        url = f"{config.api_url}/table/{STORY_DEPENDENCY_TABLE}"
        response = http_client.post(url, json=data, headers=auth_manager.get_headers())
        response.raise_for_status()
        
        result = response.json()
        return format_success_response(
            "Story dependency created successfully",
            story_dependency=result["result"],
        )

    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating story dependency: {e}")
        return format_error_response("create story dependency", e)


@mcp.tool()
def delete_story_dependency(
    dependency_id: str = Field(..., description="Sys_id of the dependency is required"),
) -> str:
    """
    Delete a story dependency in ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    
    try:
        url = f"{config.api_url}/table/{STORY_DEPENDENCY_TABLE}/{dependency_id}"
        response = http_client.delete(url, headers=auth_manager.get_headers())
        response.raise_for_status()
        
        return format_success_response("Story dependency deleted successfully")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error deleting story dependency: {e}")
        return format_error_response("delete story dependency", e)
