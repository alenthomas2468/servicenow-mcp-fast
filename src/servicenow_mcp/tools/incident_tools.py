"""
Incident tools for the ServiceNow MCP server.

This module provides tools for managing incidents in ServiceNow.
"""

import logging
from typing import Optional

import requests
from pydantic import Field

from servicenow_mcp.application import mcp, get_auth_manager, get_config
from servicenow_mcp.utils import http_client

logger = logging.getLogger(__name__)


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
    api_url = f"{config.api_url}/table/incident"

    # Build request data
    data = {
        "short_description": short_description,
    }

    if description:
        data["description"] = description
    if caller_id:
        data["caller_id"] = caller_id
    if category:
        data["category"] = category
    if subcategory:
        data["subcategory"] = subcategory
    if priority:
        data["priority"] = priority
    if impact:
        data["impact"] = impact
    if urgency:
        data["urgency"] = urgency
    if assigned_to:
        data["assigned_to"] = assigned_to
    if assignment_group:
        data["assignment_group"] = assignment_group

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
        incident_number = result.get("number")
        return f"Incident created successfully. Number: {incident_number}, Sys ID: {result.get('sys_id')}"

    except requests.RequestException as e:
        logger.error(f"Failed to create incident: {e}")
        return f"Failed to create incident: {str(e)}"


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

    # Determine if incident_id is a number or sys_id
    if len(incident_id) == 32 and all(c in "0123456789abcdef" for c in incident_id):
        # This is likely a sys_id
        api_url = f"{config.api_url}/table/incident/{incident_id}"
    else:
        # This is likely an incident number
        # First, we need to get the sys_id
        try:
            query_url = f"{config.api_url}/table/incident"
            query_params = {
                "sysparm_query": f"number={incident_id}",
                "sysparm_limit": 1,
            }

            response = http_client.get(
                query_url,
                params=query_params,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            response.raise_for_status()

            result = response.json().get("result", [])
            if not result:
                return f"Incident not found: {incident_id}"

            sys_id = result[0].get("sys_id")
            api_url = f"{config.api_url}/table/incident/{sys_id}"

        except requests.RequestException as e:
            logger.error(f"Failed to find incident: {e}")
            return f"Failed to find incident: {str(e)}"

    # Build request data
    data = {}

    if short_description:
        data["short_description"] = short_description
    if description:
        data["description"] = description
    if state:
        data["state"] = state
    if category:
        data["category"] = category
    if subcategory:
        data["subcategory"] = subcategory
    if priority:
        data["priority"] = priority
    if impact:
        data["impact"] = impact
    if urgency:
        data["urgency"] = urgency
    if assigned_to:
        data["assigned_to"] = assigned_to
    if assignment_group:
        data["assignment_group"] = assignment_group
    if work_notes:
        data["work_notes"] = work_notes
    if close_notes:
        data["close_notes"] = close_notes
    if close_code:
        data["close_code"] = close_code

    # Make request
    try:
        response = http_client.put(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})
        return f"Incident updated successfully. Number: {result.get('number')}"

    except requests.RequestException as e:
        logger.error(f"Failed to update incident: {e}")
        return f"Failed to update incident: {str(e)}"


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

    # Determine if incident_id is a number or sys_id
    if len(incident_id) == 32 and all(c in "0123456789abcdef" for c in incident_id):
        # This is likely a sys_id
        api_url = f"{config.api_url}/table/incident/{incident_id}"
    else:
        # This is likely an incident number
        # First, we need to get the sys_id
        try:
            query_url = f"{config.api_url}/table/incident"
            query_params = {
                "sysparm_query": f"number={incident_id}",
                "sysparm_limit": 1,
            }

            response = http_client.get(
                query_url,
                params=query_params,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            response.raise_for_status()

            result = response.json().get("result", [])
            if not result:
                return f"Incident not found: {incident_id}"

            sys_id = result[0].get("sys_id")
            api_url = f"{config.api_url}/table/incident/{sys_id}"

        except requests.RequestException as e:
            logger.error(f"Failed to find incident: {e}")
            return f"Failed to find incident: {str(e)}"

    # Build request data
    data = {}

    if is_work_note:
        data["work_notes"] = comment
    else:
        data["comments"] = comment

    # Make request
    try:
        response = http_client.put(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})
        return f"Comment added successfully to incident {result.get('number')}"

    except requests.RequestException as e:
        logger.error(f"Failed to add comment: {e}")
        return f"Failed to add comment: {str(e)}"


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

    # Determine if incident_id is a number or sys_id
    if len(incident_id) == 32 and all(c in "0123456789abcdef" for c in incident_id):
        # This is likely a sys_id
        api_url = f"{config.api_url}/table/incident/{incident_id}"
    else:
        # This is likely an incident number
        # First, we need to get the sys_id
        try:
            query_url = f"{config.api_url}/table/incident"
            query_params = {
                "sysparm_query": f"number={incident_id}",
                "sysparm_limit": 1,
            }

            response = http_client.get(
                query_url,
                params=query_params,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            response.raise_for_status()

            result = response.json().get("result", [])
            if not result:
                return f"Incident not found: {incident_id}"

            sys_id = result[0].get("sys_id")
            api_url = f"{config.api_url}/table/incident/{sys_id}"

        except requests.RequestException as e:
            logger.error(f"Failed to find incident: {e}")
            return f"Failed to find incident: {str(e)}"

    # Build request data
    data = {
        "state": "6",  # Resolved
        "close_code": resolution_code,
        "close_notes": resolution_notes,
        "resolved_at": "now",
    }

    # Make request
    try:
        response = http_client.put(
            api_url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        result = response.json().get("result", {})
        return f"Incident {result.get('number')} resolved successfully"

    except requests.RequestException as e:
        logger.error(f"Failed to resolve incident: {e}")
        return f"Failed to resolve incident: {str(e)}"


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
    api_url = f"{config.api_url}/table/incident"

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
    
    # Make request
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
            # Handle assigned_to field which could be a string or a dictionary
            assigned_to_val = incident_data.get("assigned_to")
            if isinstance(assigned_to_val, dict):
                assigned_to_val = assigned_to_val.get("display_value")
            
            incident = {
                "sys_id": incident_data.get("sys_id"),
                "number": incident_data.get("number"),
                "short_description": incident_data.get("short_description"),
                "description": incident_data.get("description"),
                "state": incident_data.get("state"),
                "priority": incident_data.get("priority"),
                "assigned_to": assigned_to_val,
                "category": incident_data.get("category"),
                "subcategory": incident_data.get("subcategory"),
                "created_on": incident_data.get("sys_created_on"),
                "updated_on": incident_data.get("sys_updated_on"),
            }
            incidents.append(incident)
        
        # Serialize list to string for tool output
        import json
        return json.dumps(incidents, indent=2)
        
    except requests.RequestException as e:
        logger.error(f"Failed to list incidents: {e}")
        return f"Failed to list incidents: {str(e)}"


@mcp.tool()
def get_incident_by_number(
    incident_number: str = Field(..., description="The number of the incident to fetch"),
) -> str:
    """
    Fetch a single incident from ServiceNow by its number.
    """
    config = get_config()
    auth_manager = get_auth_manager()
    api_url = f"{config.api_url}/table/incident"

    # Build query parameters
    query_params = {
        "sysparm_query": f"number={incident_number}",
        "sysparm_limit": 1,
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }

    # Make request
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
        assigned_to = incident_data.get("assigned_to")
        if isinstance(assigned_to, dict):
            assigned_to = assigned_to.get("display_value")

        incident = {
            "sys_id": incident_data.get("sys_id"),
            "number": incident_data.get("number"),
            "short_description": incident_data.get("short_description"),
            "description": incident_data.get("description"),
            "state": incident_data.get("state"),
            "priority": incident_data.get("priority"),
            "assigned_to": assigned_to,
            "category": incident_data.get("category"),
            "subcategory": incident_data.get("subcategory"),
            "created_on": incident_data.get("sys_created_on"),
            "updated_on": incident_data.get("sys_updated_on"),
        }

        import json
        return json.dumps(incident, indent=2)

    except requests.RequestException as e:
        logger.error(f"Failed to fetch incident: {e}")
        return f"Failed to fetch incident: {str(e)}"
