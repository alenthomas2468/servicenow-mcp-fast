"""
Generic table query tools for the ServiceNow MCP server.

This module provides tools for querying any ServiceNow table dynamically,
including schema discovery via sys_dictionary.
"""

import json
import logging
from typing import Optional

import requests
from pydantic import Field

from servicenow_mcp.application import mcp, get_auth_manager, get_config
from servicenow_mcp.utils import http_client
from servicenow_mcp.utils.helpers import (
    format_success_response,
    format_error_response,
    format_list_response,
    is_sys_id,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Query any table
# ---------------------------------------------------------------------------
@mcp.tool()
def query_table(
    table: str = Field(..., description="ServiceNow table name (e.g. 'incident', 'sys_dictionary', 'u_cmdb_ci_vrf')"),
    query: Optional[str] = Field(None, description="ServiceNow encoded query string (e.g. 'name=u_cmdb_ci_vrf^elementSTARTSWITHu_')"),
    fields: Optional[str] = Field(None, description="Comma-separated list of fields to return (e.g. 'sys_id,name,element'). If omitted, all fields are returned."),
    limit: int = Field(10, description="Maximum number of records to return"),
    offset: int = Field(0, description="Offset for pagination"),
    display_value: str = Field("true", description="Return display values: 'true', 'false', or 'all'"),
) -> str:
    """
    Query any ServiceNow table. Use this for ad-hoc lookups, schema discovery,
    or querying tables that don't have dedicated tools.

    Examples:
      - Get custom fields on a table:
          table='sys_dictionary', query='name=u_cmdb_ci_vrf^elementSTARTSWITHu_',
          fields='element,column_label,internal_type,max_length,mandatory,reference,active'
      - Get choice values for a field:
          table='sys_choice', query='name=incident^element=state',
          fields='value,label'
      - Query any custom table:
          table='u_cmdb_ci_vrf', limit=5
    """
    config = get_config()
    auth_manager = get_auth_manager()

    try:
        url = f"{config.api_url}/table/{table}"

        query_params = {
            "sysparm_limit": str(limit),
            "sysparm_offset": str(offset),
            "sysparm_display_value": display_value,
            "sysparm_exclude_reference_link": "true",
        }

        if fields:
            query_params["sysparm_fields"] = fields

        if query:
            query_params["sysparm_query"] = query

        response = http_client.get(
            url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        data = response.json()
        records = data.get("result", [])

        return format_list_response(records, "records", limit, offset)

    except Exception as e:
        logger.error(f"Error querying table '{table}': {e}")
        return format_error_response(f"query table '{table}'", e)


# ---------------------------------------------------------------------------
# Get table schema (fields/columns)
# ---------------------------------------------------------------------------
@mcp.tool()
def get_table_schema(
    table: str = Field(..., description="ServiceNow table name to inspect (e.g. 'u_cmdb_ci_vrf', 'incident')"),
    custom_fields_only: bool = Field(False, description="If true, only return custom fields (starting with 'u_')"),
    limit: int = Field(100, description="Maximum number of field definitions to return"),
) -> str:
    """
    Get the schema (field definitions) of any ServiceNow table by querying sys_dictionary.
    Returns field name, label, type, max length, mandatory flag, and reference table.
    """
    config = get_config()
    auth_manager = get_auth_manager()

    try:
        url = f"{config.api_url}/table/sys_dictionary"

        # Build query: filter by table name, exclude empty elements (table-level record)
        query_parts = [
            f"name={table}",
            "element!=",           # exclude the table-level row (empty element)
            "internal_type!=collection",  # exclude collection types
        ]
        if custom_fields_only:
            query_parts.append("elementSTARTSWITHu_")

        query_params = {
            "sysparm_query": "^".join(query_parts),
            "sysparm_fields": "element,column_label,internal_type,max_length,mandatory,reference,default_value,active",
            "sysparm_limit": str(limit),
            "sysparm_offset": "0",
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
        }

        response = http_client.get(
            url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        data = response.json()
        fields = data.get("result", [])

        # Clean up into a simpler format
        parsed_fields = []
        for f in fields:
            parsed_fields.append({
                "field_name": f.get("element"),
                "label": f.get("column_label"),
                "type": f.get("internal_type"),
                "max_length": f.get("max_length"),
                "mandatory": f.get("mandatory"),
                "reference_table": f.get("reference") or None,
                "default_value": f.get("default_value") or None,
                "active": f.get("active"),
            })

        # Sort by field name for readability
        parsed_fields.sort(key=lambda x: x.get("field_name", ""))

        return format_list_response(parsed_fields, "fields", limit, 0)

    except Exception as e:
        logger.error(f"Error getting schema for table '{table}': {e}")
        return format_error_response(f"get schema for table '{table}'", e)
