"""
Incident tools for the ServiceNow MCP server.

This module provides tools for managing incidents in ServiceNow.
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
    validate_pagination,
)

logger = logging.getLogger(__name__)

# Table name constant
INCIDENT_TABLE = "incident"


@mcp.tool()
def create_incident(
    short_description: str = Field(..., description="Short description of the incident"),
    description: Optional[str] = Field(None, description="Detailed description of the incident"),
    caller_id: Optional[str] = Field(None, description="User who reported the incident"),
    category: Optional[str] = Field(None, description="Category of the incident"),
    subcategory: Optional[str] = Field(None, description="Subcategory of the incident"),
    priority: Optional[str] = Field(None, description="Priority of the incident"),
    impact: Optional[str] = Field(None, description="Impact of the incident"),
    urgency: Optional[str] = Field(None, description="Urgency of the incident"),
    assigned_to: Optional[str] = Field(None, description="User assigned to the incident"),
    assignment_group: Optional[str] = Field(None, description="Group assigned to the incident"),
) -> str:
    """
    Create a new incident in ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    api_url = f"{config.api_url}/table/{INCIDENT_TABLE}"

    # Build request data using helper
    data = build_request_data(
        required_fields={"short_description": short_description},
        optional_fields={
            "description": description,
            "caller_id": caller_id,
            "category": category,
            "subcategory": subcategory,
            "priority": priority,
            "impact": impact,
            "urgency": urgency,
            "assigned_to": assigned_to,
            "assignment_group": assignment_group,
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
        return format_success_response(
            f"Incident created successfully. Number: {result.get('number')}",
            sys_id=result.get("sys_id"),
            number=result.get("number"),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to create incident: {e}")
        return format_error_response("create incident", e)


@mcp.tool()
def update_incident(
    incident_id: str = Field(..., description="Incident ID or sys_id"),
    short_description: Optional[str] = Field(None, description="Short description of the incident"),
    description: Optional[str] = Field(None, description="Detailed description of the incident"),
    state: Optional[str] = Field(None, description="State of the incident"),
    category: Optional[str] = Field(None, description="Category of the incident"),
    subcategory: Optional[str] = Field(None, description="Subcategory of the incident"),
    priority: Optional[str] = Field(None, description="Priority of the incident"),
    impact: Optional[str] = Field(None, description="Impact of the incident"),
    urgency: Optional[str] = Field(None, description="Urgency of the incident"),
    assigned_to: Optional[str] = Field(None, description="User assigned to the incident"),
    assignment_group: Optional[str] = Field(None, description="Group assigned to the incident"),
    work_notes: Optional[str] = Field(None, description="Work notes to add to the incident"),
    close_notes: Optional[str] = Field(None, description="Close notes to add to the incident"),
    close_code: Optional[str] = Field(None, description="Close code for the incident"),
) -> str:
    """
    Update an existing incident in ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()

    # Resolve incident ID to sys_id
    sys_id = resolve_record_id(INCIDENT_TABLE, incident_id, lookup_field="number")
    if not sys_id:
        return f"Incident not found: {incident_id}"

    api_url = f"{config.api_url}/table/{INCIDENT_TABLE}/{sys_id}"

    # Build request data using helper
    data = build_request_data(
        required_fields={},
        optional_fields={
            "short_description": short_description,
            "description": description,
            "state": state,
            "category": category,
            "subcategory": subcategory,
            "priority": priority,
            "impact": impact,
            "urgency": urgency,
            "assigned_to": assigned_to,
            "assignment_group": assignment_group,
            "work_notes": work_notes,
            "close_notes": close_notes,
            "close_code": close_code,
        }
    )

    try:
        response = http_client.put(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})
        return format_success_response(
            f"Incident updated successfully. Number: {result.get('number')}",
            number=result.get("number"),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to update incident: {e}")
        return format_error_response("update incident", e)


@mcp.tool()
def add_comment(
    incident_id: str = Field(..., description="Incident ID or sys_id"),
    comment: str = Field(..., description="Comment to add to the incident"),
    is_work_note: bool = Field(False, description="Whether the comment is a work note"),
) -> str:
    """
    Add a comment to an incident in ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()

    # Resolve incident ID to sys_id
    sys_id = resolve_record_id(INCIDENT_TABLE, incident_id, lookup_field="number")
    if not sys_id:
        return f"Incident not found: {incident_id}"

    api_url = f"{config.api_url}/table/{INCIDENT_TABLE}/{sys_id}"

    # Build request data
    data = {"work_notes": comment} if is_work_note else {"comments": comment}

    try:
        response = http_client.put(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})
        return format_success_response(
            f"Comment added successfully to incident {result.get('number')}",
            number=result.get("number"),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to add comment: {e}")
        return format_error_response("add comment", e)


@mcp.tool()
def resolve_incident(
    incident_id: str = Field(..., description="Incident ID or sys_id"),
    resolution_code: str = Field(..., description="Resolution code for the incident"),
    resolution_notes: str = Field(..., description="Resolution notes for the incident"),
) -> str:
    """
    Resolve an incident in ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()

    # Resolve incident ID to sys_id
    sys_id = resolve_record_id(INCIDENT_TABLE, incident_id, lookup_field="number")
    if not sys_id:
        return f"Incident not found: {incident_id}"

    api_url = f"{config.api_url}/table/{INCIDENT_TABLE}/{sys_id}"

    # Build request data
    data = {
        "state": "6",  # Resolved
        "close_code": resolution_code,
        "close_notes": resolution_notes,
        "resolved_at": "now",
    }

    try:
        response = http_client.put(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})
        return format_success_response(
            f"Incident {result.get('number')} resolved successfully",
            number=result.get("number"),
        )

    except requests.RequestException as e:
        logger.error(f"Failed to resolve incident: {e}")
        return format_error_response("resolve incident", e)


@mcp.tool()
def list_incidents(
    limit: int = Field(10, description="Maximum number of incidents to return"),
    offset: int = Field(0, description="Offset for pagination"),
    state: Optional[str] = Field(None, description="Filter by incident state"),
    assigned_to: Optional[str] = Field(None, description="Filter by assigned user"),
    category: Optional[str] = Field(None, description="Filter by category"),
    query: Optional[str] = Field(None, description="Search query for incidents"),
) -> str:
    """
    List incidents from ServiceNow.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    api_url = f"{config.api_url}/table/{INCIDENT_TABLE}"
    limit, offset = validate_pagination(limit, offset)

    # Build query parameters
    query_params = {
        "sysparm_limit": limit,
        "sysparm_offset": offset,
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }
    
    # Add filters
    filters = []
    if state:
        filters.append(f"state={state}")
    if assigned_to:
        filters.append(f"assigned_to={assigned_to}")
    if category:
        filters.append(f"category={category}")
    if query:
        filters.append(f"short_descriptionLIKE{query}^ORdescriptionLIKE{query}")
    
    if filters:
        query_params["sysparm_query"] = "^".join(filters)
    
    try:
        response = http_client.get(
            api_url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        
        data = response.json()
        incidents = []
        
        for incident_data in data.get("result", []):
            incident = {
                "sys_id": incident_data.get("sys_id"),
                "number": incident_data.get("number"),
                "short_description": incident_data.get("short_description"),
                "description": incident_data.get("description"),
                "state": incident_data.get("state"),
                "priority": incident_data.get("priority"),
                "assigned_to": extract_display_value(incident_data.get("assigned_to")),
                "category": incident_data.get("category"),
                "subcategory": incident_data.get("subcategory"),
                "created_on": incident_data.get("sys_created_on"),
                "updated_on": incident_data.get("sys_updated_on"),
            }
            incidents.append(incident)
        
        return format_list_response(incidents, "incidents", limit, offset)
        
    except requests.RequestException as e:
        logger.error(f"Failed to list incidents: {e}")
        return format_error_response("list incidents", e)


@mcp.tool()
def get_incident_by_number(
    incident_number: str = Field(..., description="The number of the incident to fetch"),
) -> str:
    """
    Fetch a single incident from ServiceNow by its number.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    api_url = f"{config.api_url}/table/{INCIDENT_TABLE}"

    query_params = {
        "sysparm_query": f"number={incident_number}",
        "sysparm_limit": 1,
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }

    try:
        response = http_client.get(
            api_url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        data = response.json()
        result = data.get("result", [])

        if not result:
            return f"Incident not found: {incident_number}"

        incident_data = result[0]
        incident = {
            "sys_id": incident_data.get("sys_id"),
            "number": incident_data.get("number"),
            "short_description": incident_data.get("short_description"),
            "description": incident_data.get("description"),
            "state": incident_data.get("state"),
            "priority": incident_data.get("priority"),
            "assigned_to": extract_display_value(incident_data.get("assigned_to")),
            "category": incident_data.get("category"),
            "subcategory": incident_data.get("subcategory"),
            "created_on": incident_data.get("sys_created_on"),
            "updated_on": incident_data.get("sys_updated_on"),
        }

        return format_success_response(
            f"Found incident: {incident_number}",
            incident=incident,
        )

    except requests.RequestException as e:
        logger.error(f"Failed to fetch incident: {e}")
        return format_error_response("fetch incident", e)
