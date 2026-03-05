"""
eLite IPVPN CFS Order tools for the ServiceNow MCP server.

This module provides tools for managing eLite IPVPN CFS Order
(u_task_elite_ipvpn_cfs_order) records in ServiceNow.
The table extends task via TINA CFS Order.

Only list, get, and update operations are provided (no create/delete).
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
ELITE_IPVPN_CFS_ORDER_TABLE = "u_task_elite_ipvpn_cfs_order"

# Common fields to retrieve in list/get operations
ELITE_IPVPN_CFS_ORDER_FIELDS = ",".join([
    # --- inherited task fields ---
    "sys_id",
    "number",
    "short_description",
    "description",
    "state",
    "priority",
    "urgency",
    "active",
    "assigned_to",
    "assignment_group",
    "opened_by",
    "opened_at",
    "closed_at",
    "closed_by",
    "work_notes",
    "comments",
    "contact_type",
    "parent",
    "made_sla",
    "sla_due",
    "upon_approval",
    "upon_reject",
    "approval",
    "approval_set",
    "approval_history",
    "due_date",
    "expected_start",
    "work_start",
    "work_end",
    "order",
    "activity_due",
    "follow_up",
    "reassignment_count",
    "escalation",
    "additional_assignee_list",
    "sys_class_name",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
    "sys_updated_by",
    # --- custom fields (String) ---
    "u_bgp_md5_password",
    "u_bpj_evc_router_id",
    "u_cpe_model",
    "u_elite_type",
    "u_email_address",
    "u_email_generated",
    "u_fibre_code",
    "u_fibre_no",
    "u_node_name",
    "u_other_authorized_installer",
    "u_port",
    "u_port_no",
    "u_project_no",
    "u_slot",
    "u_svlan_inner_vlan_id",
    "u_vlan_id",
    "u_work_item_name",
    # --- custom fields (Choice) ---
    "u_authorized_installer",
    "u_internet_framing_bytes",
    "u_order_from",
    "u_routing_protocol",
    # --- custom fields (Reference) ---
    "u_customer_location_a",
    "u_customer_location_b",
    "u_inner_vlan",
    # --- custom fields (Other) ---
    "u_add_component",
    "u_glide_list_1",
    "u_table_name_1",
])


def _parse_elite_ipvpn_cfs_order(item: dict) -> dict:
    """Parse a raw ServiceNow eLite IPVPN CFS Order record into a clean dictionary."""
    return {
        # --- inherited task fields ---
        "sys_id": item.get("sys_id"),
        "number": item.get("number"),
        "short_description": item.get("short_description"),
        "description": item.get("description"),
        "state": item.get("state"),
        "priority": item.get("priority"),
        "urgency": item.get("urgency"),
        "active": item.get("active"),
        "assigned_to": extract_display_value(item.get("assigned_to")),
        "assignment_group": extract_display_value(item.get("assignment_group")),
        "opened_by": extract_display_value(item.get("opened_by")),
        "opened_at": item.get("opened_at"),
        "closed_at": item.get("closed_at"),
        "closed_by": extract_display_value(item.get("closed_by")),
        "work_notes": item.get("work_notes"),
        "comments": item.get("comments"),
        "contact_type": item.get("contact_type"),
        "parent": extract_display_value(item.get("parent")),
        "made_sla": item.get("made_sla"),
        "sla_due": item.get("sla_due"),
        "upon_approval": item.get("upon_approval"),
        "upon_reject": item.get("upon_reject"),
        "approval": item.get("approval"),
        "approval_set": item.get("approval_set"),
        "approval_history": item.get("approval_history"),
        "due_date": item.get("due_date"),
        "expected_start": item.get("expected_start"),
        "work_start": item.get("work_start"),
        "work_end": item.get("work_end"),
        "order": item.get("order"),
        "activity_due": item.get("activity_due"),
        "follow_up": item.get("follow_up"),
        "reassignment_count": item.get("reassignment_count"),
        "escalation": item.get("escalation"),
        "additional_assignee_list": item.get("additional_assignee_list"),
        "sys_class_name": item.get("sys_class_name"),
        "created_on": item.get("sys_created_on"),
        "updated_on": item.get("sys_updated_on"),
        "created_by": item.get("sys_created_by"),
        "updated_by": item.get("sys_updated_by"),
        # --- custom fields (String) ---
        "u_bgp_md5_password": item.get("u_bgp_md5_password"),
        "u_bpj_evc_router_id": item.get("u_bpj_evc_router_id"),
        "u_cpe_model": item.get("u_cpe_model"),
        "u_elite_type": item.get("u_elite_type"),
        "u_email_address": item.get("u_email_address"),
        "u_email_generated": item.get("u_email_generated"),
        "u_fibre_code": item.get("u_fibre_code"),
        "u_fibre_no": item.get("u_fibre_no"),
        "u_node_name": item.get("u_node_name"),
        "u_other_authorized_installer": item.get("u_other_authorized_installer"),
        "u_port": item.get("u_port"),
        "u_port_no": item.get("u_port_no"),
        "u_project_no": item.get("u_project_no"),
        "u_slot": item.get("u_slot"),
        "u_svlan_inner_vlan_id": item.get("u_svlan_inner_vlan_id"),
        "u_vlan_id": item.get("u_vlan_id"),
        "u_work_item_name": item.get("u_work_item_name"),
        # --- custom fields (Choice) ---
        "u_authorized_installer": item.get("u_authorized_installer"),
        "u_internet_framing_bytes": item.get("u_internet_framing_bytes"),
        "u_order_from": item.get("u_order_from"),
        "u_routing_protocol": item.get("u_routing_protocol"),
        # --- custom fields (Reference) ---
        "u_customer_location_a": extract_display_value(item.get("u_customer_location_a")),
        "u_customer_location_b": extract_display_value(item.get("u_customer_location_b")),
        "u_inner_vlan": extract_display_value(item.get("u_inner_vlan")),
        # --- custom fields (Other) ---
        "u_add_component": item.get("u_add_component"),
        "u_glide_list_1": item.get("u_glide_list_1"),
        "u_table_name_1": item.get("u_table_name_1"),
    }


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
@mcp.tool()
def list_elite_ipvpn_cfs_orders(
    limit: int = Field(10, description="Maximum number of eLite IPVPN CFS Orders to return"),
    offset: int = Field(0, description="Offset for pagination"),
    number: Optional[str] = Field(None, description="Filter by order number"),
    state: Optional[str] = Field(None, description="Filter by state"),
    assigned_to: Optional[str] = Field(None, description="Filter by assigned user"),
    assignment_group: Optional[str] = Field(None, description="Filter by assignment group"),
    u_order_from: Optional[str] = Field(None, description="Filter by Order From"),
    u_routing_protocol: Optional[str] = Field(None, description="Filter by Routing Protocol"),
    u_authorized_installer: Optional[str] = Field(None, description="Filter by Authorized Installer"),
    u_elite_type: Optional[str] = Field(None, description="Filter by eLite Type"),
    active: Optional[str] = Field(None, description="Filter by active status (true/false)"),
    priority: Optional[str] = Field(None, description="Filter by priority"),
    query: Optional[str] = Field(None, description="Encoded query string for advanced filtering"),
) -> str:
    """List eLite IPVPN CFS Order records from ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    try:
        url = f"{config.api_url}/table/{ELITE_IPVPN_CFS_ORDER_TABLE}"

        query_params = {
            "sysparm_limit": str(limit),
            "sysparm_offset": str(offset),
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
            "sysparm_fields": ELITE_IPVPN_CFS_ORDER_FIELDS,
        }

        query_parts: list[str] = []
        if number:
            query_parts.append(f"number={number}")
        if state:
            query_parts.append(f"state={state}")
        if assigned_to:
            query_parts.append(f"assigned_to={assigned_to}")
        if assignment_group:
            query_parts.append(f"assignment_group={assignment_group}")
        if u_order_from:
            query_parts.append(f"u_order_from={u_order_from}")
        if u_routing_protocol:
            query_parts.append(f"u_routing_protocol={u_routing_protocol}")
        if u_authorized_installer:
            query_parts.append(f"u_authorized_installer={u_authorized_installer}")
        if u_elite_type:
            query_parts.append(f"u_elite_typeLIKE{u_elite_type}")
        if active:
            query_parts.append(f"active={active}")
        if priority:
            query_parts.append(f"priority={priority}")
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
        orders = [_parse_elite_ipvpn_cfs_order(item) for item in data.get("result", [])]

        return format_list_response(orders, "elite_ipvpn_cfs_orders", limit, offset)

    except Exception as e:
        logger.error(f"Error listing eLite IPVPN CFS Orders: {e}")
        return format_error_response("list eLite IPVPN CFS Orders", e)


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------
@mcp.tool()
def get_elite_ipvpn_cfs_order(
    order_id: str = Field(
        ..., description="eLite IPVPN CFS Order sys_id or number"
    ),
) -> str:
    """Get a specific eLite IPVPN CFS Order record from ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    try:
        query_params = {
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
            "sysparm_fields": ELITE_IPVPN_CFS_ORDER_FIELDS,
        }

        if is_sys_id(order_id):
            url = f"{config.api_url}/table/{ELITE_IPVPN_CFS_ORDER_TABLE}/{order_id}"
        else:
            url = f"{config.api_url}/table/{ELITE_IPVPN_CFS_ORDER_TABLE}"
            query_params["sysparm_query"] = f"number={order_id}"
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
            return f"eLite IPVPN CFS Order not found: {order_id}"

        result = data["result"]
        if isinstance(result, list):
            if not result:
                return f"eLite IPVPN CFS Order not found: {order_id}"
            item = result[0]
        else:
            item = result

        order = _parse_elite_ipvpn_cfs_order(item)

        return format_success_response(
            f"Found eLite IPVPN CFS Order: {item.get('number')}",
            elite_ipvpn_cfs_order=order,
        )

    except Exception as e:
        logger.error(f"Error getting eLite IPVPN CFS Order: {e}")
        return format_error_response("get eLite IPVPN CFS Order", e)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
@mcp.tool()
def update_elite_ipvpn_cfs_order(
    order_id: str = Field(..., description="eLite IPVPN CFS Order sys_id or number"),
    # --- inherited task fields ---
    short_description: Optional[str] = Field(None, description="Short description"),
    description: Optional[str] = Field(None, description="Detailed description"),
    state: Optional[str] = Field(None, description="State of the order"),
    priority: Optional[str] = Field(None, description="Priority"),
    urgency: Optional[str] = Field(None, description="Urgency"),
    assigned_to: Optional[str] = Field(None, description="User assigned to the order (sys_id or display value)"),
    assignment_group: Optional[str] = Field(None, description="Group assigned to the order (sys_id or display value)"),
    work_notes: Optional[str] = Field(None, description="Work notes to add to the order"),
    comments: Optional[str] = Field(None, description="Additional comments"),
    due_date: Optional[str] = Field(None, description="Due date (YYYY-MM-DD HH:MM:SS)"),
    # --- custom fields (String) ---
    u_bgp_md5_password: Optional[str] = Field(None, description="BGP - MD5 Password"),
    u_bpj_evc_router_id: Optional[str] = Field(None, description="BPJ EVC Router ID"),
    u_cpe_model: Optional[str] = Field(None, description="CPE Model"),
    u_elite_type: Optional[str] = Field(None, description="eLite Type"),
    u_email_address: Optional[str] = Field(None, description="Email Address"),
    u_email_generated: Optional[str] = Field(None, description="Email Generated"),
    u_fibre_code: Optional[str] = Field(None, description="Fibre Code"),
    u_fibre_no: Optional[str] = Field(None, description="Fibre No"),
    u_node_name: Optional[str] = Field(None, description="Node Name"),
    u_other_authorized_installer: Optional[str] = Field(None, description="Other Authorized Installer"),
    u_port: Optional[str] = Field(None, description="Port"),
    u_port_no: Optional[str] = Field(None, description="Port No"),
    u_project_no: Optional[str] = Field(None, description="Project No"),
    u_slot: Optional[str] = Field(None, description="Slot"),
    u_svlan_inner_vlan_id: Optional[str] = Field(None, description="SVLAN/Inner VLAN ID"),
    u_vlan_id: Optional[str] = Field(None, description="VLAN ID"),
    u_work_item_name: Optional[str] = Field(None, description="Work Item Name"),
    # --- custom fields (Choice) ---
    u_authorized_installer: Optional[str] = Field(None, description="Authorized Installer"),
    u_internet_framing_bytes: Optional[str] = Field(None, description="Internet Framing (Bytes)"),
    u_order_from: Optional[str] = Field(None, description="Order From"),
    u_routing_protocol: Optional[str] = Field(None, description="Routing Protocol"),
    # --- custom fields (Reference) ---
    u_customer_location_a: Optional[str] = Field(None, description="Customer Location A (sys_id or display value)"),
    u_customer_location_b: Optional[str] = Field(None, description="Customer Location B (sys_id or display value)"),
    u_inner_vlan: Optional[str] = Field(None, description="Inner VLAN (sys_id or display value)"),
) -> str:
    """Update an existing eLite IPVPN CFS Order record in ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    # Resolve to sys_id if a number was provided
    sys_id_to_update = order_id
    if not is_sys_id(order_id):
        search_url = f"{config.api_url}/table/{ELITE_IPVPN_CFS_ORDER_TABLE}"
        search_params = {
            "sysparm_query": f"number={order_id}",
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
                return f"eLite IPVPN CFS Order not found: {order_id}"
            sys_id_to_update = s_res[0]["sys_id"]
        except Exception as e:
            return f"Error resolving eLite IPVPN CFS Order ID: {str(e)}"

    url = f"{config.api_url}/table/{ELITE_IPVPN_CFS_ORDER_TABLE}/{sys_id_to_update}"

    # Build the request body — only include fields that were explicitly set
    body: dict = {}
    field_map = {
        # inherited task fields
        "short_description": short_description,
        "description": description,
        "state": state,
        "priority": priority,
        "urgency": urgency,
        "assigned_to": assigned_to,
        "assignment_group": assignment_group,
        "work_notes": work_notes,
        "comments": comments,
        "due_date": due_date,
        # custom fields (String)
        "u_bgp_md5_password": u_bgp_md5_password,
        "u_bpj_evc_router_id": u_bpj_evc_router_id,
        "u_cpe_model": u_cpe_model,
        "u_elite_type": u_elite_type,
        "u_email_address": u_email_address,
        "u_email_generated": u_email_generated,
        "u_fibre_code": u_fibre_code,
        "u_fibre_no": u_fibre_no,
        "u_node_name": u_node_name,
        "u_other_authorized_installer": u_other_authorized_installer,
        "u_port": u_port,
        "u_port_no": u_port_no,
        "u_project_no": u_project_no,
        "u_slot": u_slot,
        "u_svlan_inner_vlan_id": u_svlan_inner_vlan_id,
        "u_vlan_id": u_vlan_id,
        "u_work_item_name": u_work_item_name,
        # custom fields (Choice)
        "u_authorized_installer": u_authorized_installer,
        "u_internet_framing_bytes": u_internet_framing_bytes,
        "u_order_from": u_order_from,
        "u_routing_protocol": u_routing_protocol,
        # custom fields (Reference)
        "u_customer_location_a": u_customer_location_a,
        "u_customer_location_b": u_customer_location_b,
        "u_inner_vlan": u_inner_vlan,
    }

    for key, value in field_map.items():
        if value is not None:
            body[key] = value

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
            return "Failed to update eLite IPVPN CFS Order"

        result = data["result"]
        return format_success_response(
            f"eLite IPVPN CFS Order updated successfully: {result.get('number')}",
            sys_id=result.get("sys_id"),
            number=result.get("number"),
        )

    except Exception as e:
        logger.error(f"Error updating eLite IPVPN CFS Order: {e}")
        return format_error_response("update eLite IPVPN CFS Order", e)
