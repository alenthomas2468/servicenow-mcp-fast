"""
Common helper utilities for ServiceNow MCP tools.

This module provides reusable functions for building request data,
resolving ServiceNow IDs, handling responses, and standardized error handling.
"""

import json
import logging
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

import requests

from servicenow_mcp.application import get_auth_manager, get_config
from servicenow_mcp.utils import http_client

logger = logging.getLogger(__name__)

# Constants
SYS_ID_LENGTH = 32
SYS_ID_CHARS = set("0123456789abcdef")


def is_sys_id(value: str) -> bool:
    """
    Check if a value is a ServiceNow sys_id (32-character hex string).
    
    Args:
        value: The string to check.
        
    Returns:
        True if the value is a valid sys_id format.
    """
    return len(value) == SYS_ID_LENGTH and all(c in SYS_ID_CHARS for c in value.lower())


def build_request_data(required_fields: Dict[str, Any], optional_fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build request data by combining required fields with non-None optional fields.
    
    Args:
        required_fields: Dictionary of required fields (always included).
        optional_fields: Dictionary of optional fields (only included if value is not None).
        
    Returns:
        Combined dictionary with all required fields and non-None optional fields.
    """
    data = dict(required_fields)
    for key, value in optional_fields.items():
        if value is not None:
            # Convert booleans to lowercase string for ServiceNow API
            if isinstance(value, bool):
                data[key] = str(value).lower()
            else:
                data[key] = value
    return data


def build_query_string(filters: Dict[str, Any], separator: str = "^") -> str:
    """
    Build a ServiceNow query string from a dictionary of filters.
    
    Args:
        filters: Dictionary of field names to values.
        separator: Query separator (default: "^" for AND).
        
    Returns:
        ServiceNow-formatted query string.
    """
    query_parts = []
    for key, value in filters.items():
        if value is not None:
            if isinstance(value, bool):
                query_parts.append(f"{key}={str(value).lower()}")
            else:
                query_parts.append(f"{key}={value}")
    return separator.join(query_parts)


def resolve_record_id(
    table: str,
    identifier: str,
    lookup_field: str = "number",
) -> Optional[str]:
    """
    Resolve a record identifier to a sys_id.
    
    If the identifier is already a sys_id, returns it directly.
    Otherwise, looks up the record by the specified field.
    
    Args:
        table: The ServiceNow table name (e.g., "incident", "sys_user").
        identifier: The identifier (could be sys_id or a field value like number).
        lookup_field: The field to query if identifier is not a sys_id.
        
    Returns:
        The sys_id of the record, or None if not found.
    """
    # If it's already a sys_id, return it directly
    if is_sys_id(identifier):
        return identifier
    
    config = get_config()
    auth_manager = get_auth_manager()
    
    api_url = f"{config.api_url}/table/{table}"
    query_params = {
        "sysparm_query": f"{lookup_field}={identifier}",
        "sysparm_limit": "1",
        "sysparm_fields": "sys_id",
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
        if result:
            return result[0].get("sys_id")
        return None
        
    except requests.RequestException as e:
        logger.error(f"Failed to resolve {table} ID '{identifier}': {e}")
        return None


def format_success_response(
    message: str,
    data: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> str:
    """
    Format a successful response as JSON.
    
    Args:
        message: Success message.
        data: Optional data dictionary to include.
        **kwargs: Additional fields to include in the response.
        
    Returns:
        JSON-formatted success response.
    """
    output = {
        "success": True,
        "message": message,
    }
    if data:
        output.update(data)
    output.update(kwargs)
    return json.dumps(output, indent=2)


def format_error_response(operation: str, error: Exception) -> str:
    """
    Format an error response consistently.
    
    Args:
        operation: Description of the operation that failed.
        error: The exception that occurred.
        
    Returns:
        Formatted error message string.
    """
    return f"Failed to {operation}: {str(error)}"


def format_list_response(
    items: List[Dict[str, Any]],
    item_name: str,
    limit: int,
    offset: int,
    total: Optional[int] = None,
) -> str:
    """
    Format a list response with pagination info.
    
    Args:
        items: List of items to return.
        item_name: Name of the items (e.g., "incidents", "users").
        limit: The limit used in the query.
        offset: The offset used in the query.
        total: Optional total count from response headers.
        
    Returns:
        JSON-formatted list response.
    """
    output = {
        "success": True,
        "message": f"Found {len(items)} {item_name}",
        item_name: items,
        "count": len(items),
        "limit": limit,
        "offset": offset,
    }
    if total is not None:
        output["total"] = total
    return json.dumps(output, indent=2)


T = TypeVar("T")


def servicenow_api_call(operation: str) -> Callable:
    """
    Decorator for ServiceNow API calls with standardized error handling.
    
    Args:
        operation: Description of the operation for error messages.
        
    Returns:
        Decorated function with error handling.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., Union[T, str]]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Union[T, str]:
            try:
                return func(*args, **kwargs)
            except requests.RequestException as e:
                logger.error(f"Error {operation}: {e}")
                return format_error_response(operation, e)
            except Exception as e:
                logger.error(f"Unexpected error {operation}: {e}")
                return format_error_response(operation, e)
        return wrapper
    return decorator


def extract_display_value(field: Any, default: str = "") -> str:
    """
    Safely extract display value from a ServiceNow field.
    
    ServiceNow fields can be strings, dicts with display_value, or None.
    
    Args:
        field: The field value from ServiceNow API response.
        default: Default value if extraction fails.
        
    Returns:
        The extracted display value or default.
    """
    if field is None:
        return default
    if isinstance(field, dict):
        return field.get("display_value", default)
    return str(field)


def parse_bool_field(value: Any) -> bool:
    """
    Parse a ServiceNow boolean field.
    
    ServiceNow returns booleans as strings ("true"/"false").
    
    Args:
        value: The field value to parse.
        
    Returns:
        Boolean value.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value)


def format_kb_response(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format knowledge base response data with standardized structure.
    
    Args:
        result: Raw result from ServiceNow API.
        
    Returns:
        Formatted knowledge base response.
    """
    return {
        "success": True,
        "message": "Knowledge base operation successful",
        "kb_id": result.get("sys_id"),
        "title": result.get("title"),
    }
