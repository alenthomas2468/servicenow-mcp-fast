"""
Network Element tools for the ServiceNow MCP server.

This module provides tools for managing Network Element (u_cmdb_ci_network_element)
CI records in ServiceNow. The table extends cmdb_ci (Configuration Item).
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
NETWORK_ELEMENT_TABLE = "u_cmdb_ci_network_element"

# Common fields to retrieve in list/get operations
NETWORK_ELEMENT_FIELDS = ",".join([
    "sys_id",
    "name",
    "short_description",
    "comments",
    "category",
    "subcategory",
    "ip_address",
    "mac_address",
    "fqdn",
    "dns_domain",
    "serial_number",
    "asset_tag",
    "model_id",
    "model_number",
    "manufacturer",
    "vendor",
    "company",
    "department",
    "location",
    "environment",
    "assigned_to",
    "owned_by",
    "managed_by",
    "managed_by_group",
    "support_group",
    "assignment_group",
    "supported_by",
    "install_status",
    "operational_status",
    "monitor",
    "cost",
    "cost_center",
    "cost_cc",
    "schedule",
    "maintenance_schedule",
    "lease_id",
    "po_number",
    "gl_account",
    "invoice_number",
    "asset",
    "install_date",
    "purchase_date",
    "start_date",
    "due",
    "delivery_date",
    "order_date",
    "warranty_expiration",
    "checked_in",
    "checked_out",
    "first_discovered",
    "last_discovered",
    "discovery_source",
    "correlation_id",
    "product_instance_id",
    "duplicate_of",
    "fault_count",
    "can_print",
    "skip_sync",
    "unverified",
    "justification",
    "due_in",
    "attestation_status",
    "attestation_score",
    "attested",
    "attested_by",
    "attested_date",
    "life_cycle_stage",
    "life_cycle_stage_status",
    "business_unit",
    "change_control",
    "sys_class_name",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
    "sys_updated_by",
])


def _parse_network_element(item: dict) -> dict:
    """Parse a raw ServiceNow network element record into a clean dictionary."""
    return {
        "sys_id": item.get("sys_id"),
        "name": item.get("name"),
        "short_description": item.get("short_description"),
        "comments": item.get("comments"),
        "category": item.get("category"),
        "subcategory": item.get("subcategory"),
        "ip_address": item.get("ip_address"),
        "mac_address": item.get("mac_address"),
        "fqdn": item.get("fqdn"),
        "dns_domain": item.get("dns_domain"),
        "serial_number": item.get("serial_number"),
        "asset_tag": item.get("asset_tag"),
        "model_id": extract_display_value(item.get("model_id")),
        "model_number": item.get("model_number"),
        "manufacturer": extract_display_value(item.get("manufacturer")),
        "vendor": extract_display_value(item.get("vendor")),
        "company": extract_display_value(item.get("company")),
        "department": extract_display_value(item.get("department")),
        "location": extract_display_value(item.get("location")),
        "environment": item.get("environment"),
        "assigned_to": extract_display_value(item.get("assigned_to")),
        "owned_by": extract_display_value(item.get("owned_by")),
        "managed_by": extract_display_value(item.get("managed_by")),
        "managed_by_group": extract_display_value(item.get("managed_by_group")),
        "support_group": extract_display_value(item.get("support_group")),
        "assignment_group": extract_display_value(item.get("assignment_group")),
        "supported_by": extract_display_value(item.get("supported_by")),
        "install_status": item.get("install_status"),
        "operational_status": item.get("operational_status"),
        "monitor": item.get("monitor"),
        "cost": item.get("cost"),
        "cost_center": extract_display_value(item.get("cost_center")),
        "schedule": extract_display_value(item.get("schedule")),
        "maintenance_schedule": extract_display_value(item.get("maintenance_schedule")),
        "lease_id": item.get("lease_id"),
        "install_date": item.get("install_date"),
        "purchase_date": item.get("purchase_date"),
        "warranty_expiration": item.get("warranty_expiration"),
        "first_discovered": item.get("first_discovered"),
        "last_discovered": item.get("last_discovered"),
        "discovery_source": item.get("discovery_source"),
        "fault_count": item.get("fault_count"),
        "life_cycle_stage": extract_display_value(item.get("life_cycle_stage")),
        "life_cycle_stage_status": extract_display_value(item.get("life_cycle_stage_status")),
        "business_unit": extract_display_value(item.get("business_unit")),
        "sys_class_name": item.get("sys_class_name"),
        "created_on": item.get("sys_created_on"),
        "updated_on": item.get("sys_updated_on"),
        "created_by": extract_display_value(item.get("sys_created_by")),
        "updated_by": extract_display_value(item.get("sys_updated_by")),
    }


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
@mcp.tool()
def list_network_elements(
    limit: int = Field(10, description="Maximum number of network elements to return"),
    offset: int = Field(0, description="Offset for pagination"),
    name: Optional[str] = Field(None, description="Filter by name (contains)"),
    ip_address: Optional[str] = Field(None, description="Filter by IP address"),
    category: Optional[str] = Field(None, description="Filter by category"),
    subcategory: Optional[str] = Field(None, description="Filter by subcategory"),
    install_status: Optional[str] = Field(None, description="Filter by install status (e.g. 1=Installed, 2=Retired)"),
    operational_status: Optional[str] = Field(None, description="Filter by operational status (e.g. 1=Operational)"),
    environment: Optional[str] = Field(None, description="Filter by environment"),
    company: Optional[str] = Field(None, description="Filter by company"),
    location: Optional[str] = Field(None, description="Filter by location"),
    assigned_to: Optional[str] = Field(None, description="Filter by assigned user"),
    assignment_group: Optional[str] = Field(None, description="Filter by assignment/change group"),
    manufacturer: Optional[str] = Field(None, description="Filter by manufacturer"),
    discovery_source: Optional[str] = Field(None, description="Filter by discovery source"),
    query: Optional[str] = Field(None, description="Encoded query string for advanced filtering"),
) -> str:
    """List Network Element CI records from ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    try:
        url = f"{config.api_url}/table/{NETWORK_ELEMENT_TABLE}"

        query_params = {
            "sysparm_limit": str(limit),
            "sysparm_offset": str(offset),
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
            "sysparm_fields": NETWORK_ELEMENT_FIELDS,
        }

        # Build encoded query from filters
        query_parts: list[str] = []
        if name:
            query_parts.append(f"nameLIKE{name}")
        if ip_address:
            query_parts.append(f"ip_address={ip_address}")
        if category:
            query_parts.append(f"category={category}")
        if subcategory:
            query_parts.append(f"subcategory={subcategory}")
        if install_status:
            query_parts.append(f"install_status={install_status}")
        if operational_status:
            query_parts.append(f"operational_status={operational_status}")
        if environment:
            query_parts.append(f"environment={environment}")
        if company:
            query_parts.append(f"company={company}")
        if location:
            query_parts.append(f"location={location}")
        if assigned_to:
            query_parts.append(f"assigned_to={assigned_to}")
        if assignment_group:
            query_parts.append(f"assignment_group={assignment_group}")
        if manufacturer:
            query_parts.append(f"manufacturer={manufacturer}")
        if discovery_source:
            query_parts.append(f"discovery_source={discovery_source}")
        if query:
            query_parts.append(query)

        if query_parts:
            query_params["sysparm_query"] = "^".join(query_parts)

        response = http_client.get(
            url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        data = response.json()
        elements = [_parse_network_element(item) for item in data.get("result", [])]

        return format_list_response(elements, "network_elements", limit, offset)

    except Exception as e:
        logger.error(f"Error listing network elements: {e}")
        return format_error_response("list network elements", e)


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------
@mcp.tool()
def get_network_element(
    network_element_id: str = Field(
        ..., description="Network element sys_id or name"
    ),
) -> str:
    """Get a specific Network Element CI record from ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    try:
        query_params = {
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
            "sysparm_fields": NETWORK_ELEMENT_FIELDS,
        }

        if is_sys_id(network_element_id):
            url = f"{config.api_url}/table/{NETWORK_ELEMENT_TABLE}/{network_element_id}"
        else:
            # Query by name
            url = f"{config.api_url}/table/{NETWORK_ELEMENT_TABLE}"
            query_params["sysparm_query"] = f"name={network_element_id}"
            query_params["sysparm_limit"] = "1"

        response = http_client.get(
            url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        data = response.json()

        if "result" not in data:
            return f"Network element not found: {network_element_id}"

        result = data["result"]
        if isinstance(result, list):
            if not result:
                return f"Network element not found: {network_element_id}"
            item = result[0]
        else:
            item = result

        element = _parse_network_element(item)

        return format_success_response(
            f"Found network element: {item.get('name')}",
            network_element=element,
        )

    except Exception as e:
        logger.error(f"Error getting network element: {e}")
        return format_error_response("get network element", e)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
@mcp.tool()
def create_network_element(
    name: str = Field(..., description="Name of the network element"),
    short_description: Optional[str] = Field(None, description="Short description of the network element"),
    comments: Optional[str] = Field(None, description="Additional comments"),
    category: Optional[str] = Field(None, description="Category"),
    subcategory: Optional[str] = Field(None, description="Subcategory"),
    ip_address: Optional[str] = Field(None, description="IP address"),
    mac_address: Optional[str] = Field(None, description="MAC address"),
    fqdn: Optional[str] = Field(None, description="Fully qualified domain name"),
    dns_domain: Optional[str] = Field(None, description="DNS domain"),
    serial_number: Optional[str] = Field(None, description="Serial number"),
    asset_tag: Optional[str] = Field(None, description="Asset tag"),
    model_id: Optional[str] = Field(None, description="Model ID (sys_id or display value)"),
    model_number: Optional[str] = Field(None, description="Model number"),
    manufacturer: Optional[str] = Field(None, description="Manufacturer (sys_id or display value)"),
    vendor: Optional[str] = Field(None, description="Vendor (sys_id or display value)"),
    company: Optional[str] = Field(None, description="Company (sys_id or display value)"),
    department: Optional[str] = Field(None, description="Department (sys_id or display value)"),
    location: Optional[str] = Field(None, description="Location (sys_id or display value)"),
    environment: Optional[str] = Field(None, description="Environment"),
    assigned_to: Optional[str] = Field(None, description="Assigned to (user sys_id or display value)"),
    owned_by: Optional[str] = Field(None, description="Owned by (user sys_id or display value)"),
    managed_by: Optional[str] = Field(None, description="Managed by (user sys_id or display value)"),
    managed_by_group: Optional[str] = Field(None, description="Managed by group (sys_id or display value)"),
    support_group: Optional[str] = Field(None, description="Support group (sys_id or display value)"),
    assignment_group: Optional[str] = Field(None, description="Change/assignment group (sys_id or display value)"),
    install_status: Optional[str] = Field(None, description="Install status (e.g. 1=Installed)"),
    operational_status: Optional[str] = Field(None, description="Operational status (e.g. 1=Operational)"),
    monitor: Optional[bool] = Field(None, description="Whether to monitor this element"),
    cost: Optional[str] = Field(None, description="Cost value"),
    cost_center: Optional[str] = Field(None, description="Cost center (sys_id or display value)"),
    schedule: Optional[str] = Field(None, description="Schedule (sys_id or display value)"),
    maintenance_schedule: Optional[str] = Field(None, description="Maintenance schedule (sys_id or display value)"),
    lease_id: Optional[str] = Field(None, description="Lease contract ID"),
    po_number: Optional[str] = Field(None, description="Purchase order number"),
    gl_account: Optional[str] = Field(None, description="GL account"),
    invoice_number: Optional[str] = Field(None, description="Invoice number"),
    justification: Optional[str] = Field(None, description="Justification"),
    discovery_source: Optional[str] = Field(None, description="Discovery source"),
) -> str:
    """Create a new Network Element CI record in ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    url = f"{config.api_url}/table/{NETWORK_ELEMENT_TABLE}"

    body = build_request_data(
        required_fields={"name": name},
        optional_fields={
            "short_description": short_description,
            "comments": comments,
            "category": category,
            "subcategory": subcategory,
            "ip_address": ip_address,
            "mac_address": mac_address,
            "fqdn": fqdn,
            "dns_domain": dns_domain,
            "serial_number": serial_number,
            "asset_tag": asset_tag,
            "model_id": model_id,
            "model_number": model_number,
            "manufacturer": manufacturer,
            "vendor": vendor,
            "company": company,
            "department": department,
            "location": location,
            "environment": environment,
            "assigned_to": assigned_to,
            "owned_by": owned_by,
            "managed_by": managed_by,
            "managed_by_group": managed_by_group,
            "support_group": support_group,
            "assignment_group": assignment_group,
            "install_status": install_status,
            "operational_status": operational_status,
            "monitor": str(monitor).lower() if monitor is not None else None,
            "cost": cost,
            "cost_center": cost_center,
            "schedule": schedule,
            "maintenance_schedule": maintenance_schedule,
            "lease_id": lease_id,
            "po_number": po_number,
            "gl_account": gl_account,
            "invoice_number": invoice_number,
            "justification": justification,
            "discovery_source": discovery_source,
        },
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
            return "Failed to create network element"

        result = data["result"]
        return format_success_response(
            f"Network element created successfully: {result.get('name')}",
            sys_id=result.get("sys_id"),
            name=result.get("name"),
        )

    except Exception as e:
        logger.error(f"Error creating network element: {e}")
        return format_error_response("create network element", e)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
@mcp.tool()
def update_network_element(
    network_element_id: str = Field(..., description="Network element sys_id or name"),
    name: Optional[str] = Field(None, description="Name of the network element"),
    short_description: Optional[str] = Field(None, description="Short description"),
    comments: Optional[str] = Field(None, description="Additional comments"),
    category: Optional[str] = Field(None, description="Category"),
    subcategory: Optional[str] = Field(None, description="Subcategory"),
    ip_address: Optional[str] = Field(None, description="IP address"),
    mac_address: Optional[str] = Field(None, description="MAC address"),
    fqdn: Optional[str] = Field(None, description="Fully qualified domain name"),
    dns_domain: Optional[str] = Field(None, description="DNS domain"),
    serial_number: Optional[str] = Field(None, description="Serial number"),
    asset_tag: Optional[str] = Field(None, description="Asset tag"),
    model_id: Optional[str] = Field(None, description="Model ID (sys_id or display value)"),
    model_number: Optional[str] = Field(None, description="Model number"),
    manufacturer: Optional[str] = Field(None, description="Manufacturer (sys_id or display value)"),
    vendor: Optional[str] = Field(None, description="Vendor (sys_id or display value)"),
    company: Optional[str] = Field(None, description="Company (sys_id or display value)"),
    department: Optional[str] = Field(None, description="Department (sys_id or display value)"),
    location: Optional[str] = Field(None, description="Location (sys_id or display value)"),
    environment: Optional[str] = Field(None, description="Environment"),
    assigned_to: Optional[str] = Field(None, description="Assigned to (user sys_id or display value)"),
    owned_by: Optional[str] = Field(None, description="Owned by (user sys_id or display value)"),
    managed_by: Optional[str] = Field(None, description="Managed by (user sys_id or display value)"),
    managed_by_group: Optional[str] = Field(None, description="Managed by group"),
    support_group: Optional[str] = Field(None, description="Support group"),
    assignment_group: Optional[str] = Field(None, description="Change/assignment group"),
    install_status: Optional[str] = Field(None, description="Install status"),
    operational_status: Optional[str] = Field(None, description="Operational status"),
    monitor: Optional[bool] = Field(None, description="Whether to monitor this element"),
    cost: Optional[str] = Field(None, description="Cost value"),
    cost_center: Optional[str] = Field(None, description="Cost center"),
    schedule: Optional[str] = Field(None, description="Schedule"),
    maintenance_schedule: Optional[str] = Field(None, description="Maintenance schedule"),
    lease_id: Optional[str] = Field(None, description="Lease contract ID"),
    po_number: Optional[str] = Field(None, description="Purchase order number"),
    gl_account: Optional[str] = Field(None, description="GL account"),
    invoice_number: Optional[str] = Field(None, description="Invoice number"),
    justification: Optional[str] = Field(None, description="Justification"),
    discovery_source: Optional[str] = Field(None, description="Discovery source"),
) -> str:
    """Update an existing Network Element CI record in ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    # Resolve to sys_id if a name was provided
    sys_id_to_update = network_element_id
    if not is_sys_id(network_element_id):
        search_url = f"{config.api_url}/table/{NETWORK_ELEMENT_TABLE}"
        search_params = {
            "sysparm_query": f"name={network_element_id}",
            "sysparm_limit": "1",
            "sysparm_fields": "sys_id",
        }
        try:
            s_resp = http_client.get(
                search_url,
                params=search_params,
                headers=auth_manager.get_headers(),
                timeout=config.timeout,
            )
            s_resp.raise_for_status()
            s_res = s_resp.json().get("result", [])
            if not s_res:
                return f"Network element not found: {network_element_id}"
            sys_id_to_update = s_res[0]["sys_id"]
        except Exception as e:
            return f"Error resolving network element ID: {str(e)}"

    url = f"{config.api_url}/table/{NETWORK_ELEMENT_TABLE}/{sys_id_to_update}"

    # Build the request body — only include fields that were explicitly set
    body: dict = {}
    field_map = {
        "name": name,
        "short_description": short_description,
        "comments": comments,
        "category": category,
        "subcategory": subcategory,
        "ip_address": ip_address,
        "mac_address": mac_address,
        "fqdn": fqdn,
        "dns_domain": dns_domain,
        "serial_number": serial_number,
        "asset_tag": asset_tag,
        "model_id": model_id,
        "model_number": model_number,
        "manufacturer": manufacturer,
        "vendor": vendor,
        "company": company,
        "department": department,
        "location": location,
        "environment": environment,
        "assigned_to": assigned_to,
        "owned_by": owned_by,
        "managed_by": managed_by,
        "managed_by_group": managed_by_group,
        "support_group": support_group,
        "assignment_group": assignment_group,
        "install_status": install_status,
        "operational_status": operational_status,
        "cost": cost,
        "cost_center": cost_center,
        "schedule": schedule,
        "maintenance_schedule": maintenance_schedule,
        "lease_id": lease_id,
        "po_number": po_number,
        "gl_account": gl_account,
        "invoice_number": invoice_number,
        "justification": justification,
        "discovery_source": discovery_source,
    }

    for key, value in field_map.items():
        if value is not None:
            body[key] = value

    if monitor is not None:
        body["monitor"] = str(monitor).lower()

    if not body:
        return "No changes provided to update."

    try:
        response = http_client.patch(
            url,
            json=body,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        data = response.json()
        if "result" not in data:
            return "Failed to update network element"

        result = data["result"]
        return format_success_response(
            f"Network element updated successfully: {result.get('name')}",
            sys_id=result.get("sys_id"),
            name=result.get("name"),
        )

    except Exception as e:
        logger.error(f"Error updating network element: {e}")
        return format_error_response("update network element", e)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------
@mcp.tool()
def delete_network_element(
    network_element_id: str = Field(
        ..., description="Network element sys_id or name"
    ),
) -> str:
    """Delete a Network Element CI record from ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    # Resolve to sys_id
    sys_id = network_element_id
    if not is_sys_id(network_element_id):
        sys_id = resolve_record_id(
            NETWORK_ELEMENT_TABLE, network_element_id, lookup_field="name"
        )
        if not sys_id:
            return f"Network element not found: {network_element_id}"

    url = f"{config.api_url}/table/{NETWORK_ELEMENT_TABLE}/{sys_id}"

    try:
        response = http_client.delete(
            url,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()

        return format_success_response(
            f"Deleted network element: {network_element_id}",
            sys_id=sys_id,
        )

    except Exception as e:
        logger.error(f"Error deleting network element: {e}")
        return format_error_response("delete network element", e)
