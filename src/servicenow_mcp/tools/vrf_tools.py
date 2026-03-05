"""
VRF (Virtual Routing and Forwarding) tools for the ServiceNow MCP server.

This module provides tools for managing VRF (u_cmdb_ci_vrf)
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
VRF_TABLE = "u_cmdb_ci_vrf"

# Common fields to retrieve in list/get operations
VRF_FIELDS = ",".join([
    # --- inherited cmdb_ci fields ---
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
    # --- custom VRF fields ---
    "u_activation_status",
    "u_active_version",
    "u_afi",
    "u_assigned_interfaces",
    "u_auto_export",
    "u_autonomous_system",
    "u_bgp_enabled",
    "u_bgp_family",
    "u_bgp_mpls_vpn",
    "u_bgp_neighbor",
    "u_bgp_peer_group",
    "u_cisco_vrf_type",
    "u_created_when",
    "u_default_information_originate",
    "u_discovery_status",
    "u_export_policy",
    "u_export_rts",
    "u_filter_input",
    "u_filter_output",
    "u_group",
    "u_idle_timeout",
    "u_import_path_limit",
    "u_import_path_selection",
    "u_import_policy",
    "u_import_rts",
    "u_inactive",
    "u_inbound_routing_policy",
    "u_interfaces",
    "u_is_preconfigured_object",
    "u_logical_system",
    "u_maximum_ebgp_and_ibgp_paths",
    "u_maximum_ebgp_and_ibgp_redundant_paths",
    "u_maximum_routes",
    "u_maximum_unequal_cost_ibgp_paths",
    "u_modified_when",
    "u_multicast",
    "u_multipath",
    "u_network_element",
    "u_network_for_ne",
    "u_operational_status_desired",
    "u_ospf_area",
    "u_outbound_routing_policy",
    "u_parent_network_element",
    "u_parent_ri_object",
    "u_prefix_limit",
    "u_previous_value_stored",
    "u_protocol_type",
    "u_rd",
    "u_redistribution_routing_policy",
    "u_redistribution_static_and_connected",
    "u_related_cfs_instances",
    "u_related_cfs_orders",
    "u_related_rfs_instances",
    "u_related_rfs_orders",
    "u_rt",
    "u_safi",
    "u_source_rfs_order",
    "u_static_route",
    "u_status",
    "u_teardown",
    "u_tina_rfs_order",
    "u_top_vpn_numerical_resources",
    "u_type",
    "u_used_by",
    "u_vendor_vrf",
    "u_virtual_tunnel_interface",
    "u_vpn_counter",
    "u_vrf_id",
    "u_vrf_multicast",
    "u_vrf_table_label",
    "u_vsi",
    "u_wip_object",
    "u_wip_object_updated",
    "u_wip_of",
    "u_wip_ref",
    "u_work_in_progress_version",
])


def _parse_vrf(item: dict) -> dict:
    """Parse a raw ServiceNow VRF record into a clean dictionary."""
    return {
        # --- inherited cmdb_ci fields ---
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
        # --- custom VRF fields ---
        "u_activation_status": item.get("u_activation_status"),
        "u_active_version": item.get("u_active_version"),
        "u_afi": item.get("u_afi"),
        "u_assigned_interfaces": item.get("u_assigned_interfaces"),
        "u_auto_export": item.get("u_auto_export"),
        "u_autonomous_system": extract_display_value(item.get("u_autonomous_system")),
        "u_bgp_enabled": item.get("u_bgp_enabled"),
        "u_bgp_family": extract_display_value(item.get("u_bgp_family")),
        "u_bgp_mpls_vpn": item.get("u_bgp_mpls_vpn"),
        "u_bgp_neighbor": extract_display_value(item.get("u_bgp_neighbor")),
        "u_bgp_peer_group": extract_display_value(item.get("u_bgp_peer_group")),
        "u_cisco_vrf_type": item.get("u_cisco_vrf_type"),
        "u_created_when": item.get("u_created_when"),
        "u_default_information_originate": item.get("u_default_information_originate"),
        "u_discovery_status": item.get("u_discovery_status"),
        "u_export_policy": extract_display_value(item.get("u_export_policy")),
        "u_export_rts": item.get("u_export_rts"),
        "u_filter_input": extract_display_value(item.get("u_filter_input")),
        "u_filter_output": extract_display_value(item.get("u_filter_output")),
        "u_group": extract_display_value(item.get("u_group")),
        "u_idle_timeout": item.get("u_idle_timeout"),
        "u_import_path_limit": item.get("u_import_path_limit"),
        "u_import_path_selection": item.get("u_import_path_selection"),
        "u_import_policy": extract_display_value(item.get("u_import_policy")),
        "u_import_rts": item.get("u_import_rts"),
        "u_inactive": item.get("u_inactive"),
        "u_inbound_routing_policy": extract_display_value(item.get("u_inbound_routing_policy")),
        "u_interfaces": extract_display_value(item.get("u_interfaces")),
        "u_is_preconfigured_object": item.get("u_is_preconfigured_object"),
        "u_logical_system": extract_display_value(item.get("u_logical_system")),
        "u_maximum_ebgp_and_ibgp_paths": item.get("u_maximum_ebgp_and_ibgp_paths"),
        "u_maximum_ebgp_and_ibgp_redundant_paths": item.get("u_maximum_ebgp_and_ibgp_redundant_paths"),
        "u_maximum_routes": item.get("u_maximum_routes"),
        "u_maximum_unequal_cost_ibgp_paths": item.get("u_maximum_unequal_cost_ibgp_paths"),
        "u_modified_when": item.get("u_modified_when"),
        "u_multicast": extract_display_value(item.get("u_multicast")),
        "u_multipath": item.get("u_multipath"),
        "u_network_element": extract_display_value(item.get("u_network_element")),
        "u_network_for_ne": extract_display_value(item.get("u_network_for_ne")),
        "u_operational_status_desired": item.get("u_operational_status_desired"),
        "u_ospf_area": extract_display_value(item.get("u_ospf_area")),
        "u_outbound_routing_policy": extract_display_value(item.get("u_outbound_routing_policy")),
        "u_parent_network_element": extract_display_value(item.get("u_parent_network_element")),
        "u_parent_ri_object": extract_display_value(item.get("u_parent_ri_object")),
        "u_prefix_limit": item.get("u_prefix_limit"),
        "u_previous_value_stored": item.get("u_previous_value_stored"),
        "u_protocol_type": item.get("u_protocol_type"),
        "u_rd": extract_display_value(item.get("u_rd")),
        "u_redistribution_routing_policy": extract_display_value(item.get("u_redistribution_routing_policy")),
        "u_redistribution_static_and_connected": item.get("u_redistribution_static_and_connected"),
        "u_related_cfs_instances": item.get("u_related_cfs_instances"),
        "u_related_cfs_orders": item.get("u_related_cfs_orders"),
        "u_related_rfs_instances": item.get("u_related_rfs_instances"),
        "u_related_rfs_orders": item.get("u_related_rfs_orders"),
        "u_rt": extract_display_value(item.get("u_rt")),
        "u_safi": item.get("u_safi"),
        "u_source_rfs_order": extract_display_value(item.get("u_source_rfs_order")),
        "u_static_route": extract_display_value(item.get("u_static_route")),
        "u_status": item.get("u_status"),
        "u_teardown": item.get("u_teardown"),
        "u_tina_rfs_order": extract_display_value(item.get("u_tina_rfs_order")),
        "u_top_vpn_numerical_resources": extract_display_value(item.get("u_top_vpn_numerical_resources")),
        "u_type": item.get("u_type"),
        "u_used_by": item.get("u_used_by"),
        "u_vendor_vrf": item.get("u_vendor_vrf"),
        "u_virtual_tunnel_interface": extract_display_value(item.get("u_virtual_tunnel_interface")),
        "u_vpn_counter": item.get("u_vpn_counter"),
        "u_vrf_id": item.get("u_vrf_id"),
        "u_vrf_multicast": item.get("u_vrf_multicast"),
        "u_vrf_table_label": item.get("u_vrf_table_label"),
        "u_vsi": extract_display_value(item.get("u_vsi")),
        "u_wip_object": item.get("u_wip_object"),
        "u_wip_object_updated": item.get("u_wip_object_updated"),
        "u_wip_of": extract_display_value(item.get("u_wip_of")),
        "u_wip_ref": extract_display_value(item.get("u_wip_ref")),
        "u_work_in_progress_version": extract_display_value(item.get("u_work_in_progress_version")),
    }


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
@mcp.tool()
def list_vrfs(
    limit: int = Field(10, description="Maximum number of VRFs to return"),
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
    """List VRF (Virtual Routing and Forwarding) CI records from ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    try:
        url = f"{config.api_url}/table/{VRF_TABLE}"

        query_params = {
            "sysparm_limit": str(limit),
            "sysparm_offset": str(offset),
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
            "sysparm_fields": VRF_FIELDS,
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
        vrfs = [_parse_vrf(item) for item in data.get("result", [])]

        return format_list_response(vrfs, "vrfs", limit, offset)

    except Exception as e:
        logger.error(f"Error listing VRFs: {e}")
        return format_error_response("list VRFs", e)


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------
@mcp.tool()
def get_vrf(
    vrf_id: str = Field(..., description="VRF sys_id or name"),
) -> str:
    """Get a specific VRF (Virtual Routing and Forwarding) CI record from ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    try:
        query_params = {
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
            "sysparm_fields": VRF_FIELDS,
        }

        if is_sys_id(vrf_id):
            url = f"{config.api_url}/table/{VRF_TABLE}/{vrf_id}"
        else:
            # Query by name
            url = f"{config.api_url}/table/{VRF_TABLE}"
            query_params["sysparm_query"] = f"name={vrf_id}"
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
            return f"VRF not found: {vrf_id}"

        result = data["result"]
        if isinstance(result, list):
            if not result:
                return f"VRF not found: {vrf_id}"
            item = result[0]
        else:
            item = result

        vrf = _parse_vrf(item)

        return format_success_response(
            f"Found VRF: {item.get('name')}",
            vrf=vrf,
        )

    except Exception as e:
        logger.error(f"Error getting VRF: {e}")
        return format_error_response("get VRF", e)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
@mcp.tool()
def create_vrf(
    name: str = Field(..., description="Name of the VRF"),
    short_description: Optional[str] = Field(None, description="Short description of the VRF"),
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
    monitor: Optional[bool] = Field(None, description="Whether to monitor this VRF"),
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
    # --- custom VRF fields ---
    u_activation_status: Optional[str] = Field(None, description="Activation Status"),
    u_active_version: Optional[str] = Field(None, description="Active Version"),
    u_afi: Optional[str] = Field(None, description="AFI"),
    u_assigned_interfaces: Optional[str] = Field(None, description="Assigned Interfaces"),
    u_auto_export: Optional[str] = Field(None, description="Auto Export"),
    u_autonomous_system: Optional[str] = Field(None, description="Autonomous System"),
    u_bgp_enabled: Optional[str] = Field(None, description="BGP Enabled"),
    u_bgp_family: Optional[str] = Field(None, description="BGP Family"),
    u_bgp_mpls_vpn: Optional[str] = Field(None, description="BGP MPLS VPN"),
    u_bgp_neighbor: Optional[str] = Field(None, description="BGP Neighbor"),
    u_bgp_peer_group: Optional[str] = Field(None, description="BGP Peer Group"),
    u_cisco_vrf_type: Optional[str] = Field(None, description="Cisco VRF Type"),
    u_created_when: Optional[str] = Field(None, description="Created When"),
    u_default_information_originate: Optional[str] = Field(None, description="Default Information Originate"),
    u_discovery_status: Optional[str] = Field(None, description="Discovery Status"),
    u_export_policy: Optional[str] = Field(None, description="Export Policy"),
    u_export_rts: Optional[str] = Field(None, description="Export RTs"),
    u_filter_input: Optional[str] = Field(None, description="Filter Input"),
    u_filter_output: Optional[str] = Field(None, description="Filter Output"),
    u_group: Optional[str] = Field(None, description="Group"),
    u_idle_timeout: Optional[int] = Field(None, description="Idle Timeout"),
    u_import_path_limit: Optional[int] = Field(None, description="Import Path Limit"),
    u_import_path_selection: Optional[str] = Field(None, description="Import Path Selection"),
    u_import_policy: Optional[str] = Field(None, description="Import Policy"),
    u_import_rts: Optional[str] = Field(None, description="Import RTs"),
    u_inactive: Optional[str] = Field(None, description="Inactive"),
    u_inbound_routing_policy: Optional[str] = Field(None, description="Inbound Routing Policy"),
    u_interfaces: Optional[str] = Field(None, description="Interfaces"),
    u_is_preconfigured_object: Optional[bool] = Field(None, description="Is Preconfigured Object"),
    u_logical_system: Optional[str] = Field(None, description="Logical System"),
    u_maximum_ebgp_and_ibgp_paths: Optional[int] = Field(None, description="Maximum eBGP and iBGP Paths"),
    u_maximum_ebgp_and_ibgp_redundant_paths: Optional[int] = Field(None, description="Maximum eBGP and iBGP Redundant Paths"),
    u_maximum_routes: Optional[int] = Field(None, description="Maximum Routes"),
    u_maximum_unequal_cost_ibgp_paths: Optional[int] = Field(None, description="Maximum Unequal Cost iBGP Paths"),
    u_modified_when: Optional[str] = Field(None, description="Modified When"),
    u_multicast: Optional[str] = Field(None, description="Multicast"),
    u_multipath: Optional[str] = Field(None, description="Multipath"),
    u_network_element: Optional[str] = Field(None, description="Network Element"),
    u_network_for_ne: Optional[str] = Field(None, description="Network for NE"),
    u_operational_status_desired: Optional[int] = Field(None, description="Operational Status Desired"),
    u_ospf_area: Optional[str] = Field(None, description="OSPF Area"),
    u_outbound_routing_policy: Optional[str] = Field(None, description="Outbound Routing Policy"),
    u_parent_network_element: Optional[str] = Field(None, description="Parent Network Element"),
    u_parent_ri_object: Optional[str] = Field(None, description="Parent RI Object"),
    u_prefix_limit: Optional[int] = Field(None, description="Prefix Limit"),
    u_previous_value_stored: Optional[str] = Field(None, description="Previous Value Stored"),
    u_protocol_type: Optional[str] = Field(None, description="Protocol Type"),
    u_rd: Optional[str] = Field(None, description="RD"),
    u_redistribution_routing_policy: Optional[str] = Field(None, description="Redistribution Routing Policy"),
    u_redistribution_static_and_connected: Optional[str] = Field(None, description="Redistribution Static and Connected"),
    u_related_cfs_instances: Optional[str] = Field(None, description="Related CFS Instances"),
    u_related_cfs_orders: Optional[str] = Field(None, description="Related CFS Orders"),
    u_related_rfs_instances: Optional[str] = Field(None, description="Related RFS Instances"),
    u_related_rfs_orders: Optional[str] = Field(None, description="Related RFS Orders"),
    u_rt: Optional[str] = Field(None, description="RT"),
    u_safi: Optional[str] = Field(None, description="SAFI"),
    u_source_rfs_order: Optional[str] = Field(None, description="Source RFS Order"),
    u_static_route: Optional[str] = Field(None, description="Static Route"),
    u_status: Optional[str] = Field(None, description="Status"),
    u_teardown: Optional[int] = Field(None, description="Teardown"),
    u_tina_rfs_order: Optional[str] = Field(None, description="TINA RFS Order"),
    u_top_vpn_numerical_resources: Optional[str] = Field(None, description="Top VPN Numerical Resources"),
    u_type: Optional[str] = Field(None, description="Type"),
    u_used_by: Optional[str] = Field(None, description="Used By"),
    u_vendor_vrf: Optional[str] = Field(None, description="Vendor VRF"),
    u_virtual_tunnel_interface: Optional[str] = Field(None, description="Virtual Tunnel Interface"),
    u_vpn_counter: Optional[str] = Field(None, description="VPN Counter"),
    u_vrf_id: Optional[str] = Field(None, description="VRF ID"),
    u_vrf_multicast: Optional[str] = Field(None, description="VRF Multicast"),
    u_vrf_table_label: Optional[str] = Field(None, description="VRF Table Label"),
    u_vsi: Optional[str] = Field(None, description="VSI"),
    u_wip_object: Optional[bool] = Field(None, description="WIP Object"),
    u_wip_object_updated: Optional[str] = Field(None, description="WIP Object Updated"),
    u_wip_of: Optional[str] = Field(None, description="WIP Of"),
    u_wip_ref: Optional[str] = Field(None, description="WIP Ref"),
    u_work_in_progress_version: Optional[str] = Field(None, description="Work In Progress Version"),
) -> str:
    """Create a new VRF (Virtual Routing and Forwarding) CI record in ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    url = f"{config.api_url}/table/{VRF_TABLE}"

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
            # custom VRF fields
            "u_activation_status": u_activation_status,
            "u_active_version": u_active_version,
            "u_afi": u_afi,
            "u_assigned_interfaces": u_assigned_interfaces,
            "u_auto_export": u_auto_export,
            "u_autonomous_system": u_autonomous_system,
            "u_bgp_enabled": u_bgp_enabled,
            "u_bgp_family": u_bgp_family,
            "u_bgp_mpls_vpn": u_bgp_mpls_vpn,
            "u_bgp_neighbor": u_bgp_neighbor,
            "u_bgp_peer_group": u_bgp_peer_group,
            "u_cisco_vrf_type": u_cisco_vrf_type,
            "u_created_when": u_created_when,
            "u_default_information_originate": u_default_information_originate,
            "u_discovery_status": u_discovery_status,
            "u_export_policy": u_export_policy,
            "u_export_rts": u_export_rts,
            "u_filter_input": u_filter_input,
            "u_filter_output": u_filter_output,
            "u_group": u_group,
            "u_idle_timeout": u_idle_timeout,
            "u_import_path_limit": u_import_path_limit,
            "u_import_path_selection": u_import_path_selection,
            "u_import_policy": u_import_policy,
            "u_import_rts": u_import_rts,
            "u_inactive": u_inactive,
            "u_inbound_routing_policy": u_inbound_routing_policy,
            "u_interfaces": u_interfaces,
            "u_is_preconfigured_object": str(u_is_preconfigured_object).lower() if u_is_preconfigured_object is not None else None,
            "u_logical_system": u_logical_system,
            "u_maximum_ebgp_and_ibgp_paths": u_maximum_ebgp_and_ibgp_paths,
            "u_maximum_ebgp_and_ibgp_redundant_paths": u_maximum_ebgp_and_ibgp_redundant_paths,
            "u_maximum_routes": u_maximum_routes,
            "u_maximum_unequal_cost_ibgp_paths": u_maximum_unequal_cost_ibgp_paths,
            "u_modified_when": u_modified_when,
            "u_multicast": u_multicast,
            "u_multipath": u_multipath,
            "u_network_element": u_network_element,
            "u_network_for_ne": u_network_for_ne,
            "u_operational_status_desired": u_operational_status_desired,
            "u_ospf_area": u_ospf_area,
            "u_outbound_routing_policy": u_outbound_routing_policy,
            "u_parent_network_element": u_parent_network_element,
            "u_parent_ri_object": u_parent_ri_object,
            "u_prefix_limit": u_prefix_limit,
            "u_previous_value_stored": u_previous_value_stored,
            "u_protocol_type": u_protocol_type,
            "u_rd": u_rd,
            "u_redistribution_routing_policy": u_redistribution_routing_policy,
            "u_redistribution_static_and_connected": u_redistribution_static_and_connected,
            "u_related_cfs_instances": u_related_cfs_instances,
            "u_related_cfs_orders": u_related_cfs_orders,
            "u_related_rfs_instances": u_related_rfs_instances,
            "u_related_rfs_orders": u_related_rfs_orders,
            "u_rt": u_rt,
            "u_safi": u_safi,
            "u_source_rfs_order": u_source_rfs_order,
            "u_static_route": u_static_route,
            "u_status": u_status,
            "u_teardown": u_teardown,
            "u_tina_rfs_order": u_tina_rfs_order,
            "u_top_vpn_numerical_resources": u_top_vpn_numerical_resources,
            "u_type": u_type,
            "u_used_by": u_used_by,
            "u_vendor_vrf": u_vendor_vrf,
            "u_virtual_tunnel_interface": u_virtual_tunnel_interface,
            "u_vpn_counter": u_vpn_counter,
            "u_vrf_id": u_vrf_id,
            "u_vrf_multicast": u_vrf_multicast,
            "u_vrf_table_label": u_vrf_table_label,
            "u_vsi": u_vsi,
            "u_wip_object": str(u_wip_object).lower() if u_wip_object is not None else None,
            "u_wip_object_updated": u_wip_object_updated,
            "u_wip_of": u_wip_of,
            "u_wip_ref": u_wip_ref,
            "u_work_in_progress_version": u_work_in_progress_version,
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
            return "Failed to create VRF"

        result = data["result"]
        return format_success_response(
            f"VRF created successfully: {result.get('name')}",
            sys_id=result.get("sys_id"),
            name=result.get("name"),
        )

    except Exception as e:
        logger.error(f"Error creating VRF: {e}")
        return format_error_response("create VRF", e)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
@mcp.tool()
def update_vrf(
    vrf_id: str = Field(..., description="VRF sys_id or name"),
    name: Optional[str] = Field(None, description="Name of the VRF"),
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
    monitor: Optional[bool] = Field(None, description="Whether to monitor this VRF"),
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
    # --- custom VRF fields ---
    u_activation_status: Optional[str] = Field(None, description="Activation Status"),
    u_active_version: Optional[str] = Field(None, description="Active Version"),
    u_afi: Optional[str] = Field(None, description="AFI"),
    u_assigned_interfaces: Optional[str] = Field(None, description="Assigned Interfaces"),
    u_auto_export: Optional[str] = Field(None, description="Auto Export"),
    u_autonomous_system: Optional[str] = Field(None, description="Autonomous System"),
    u_bgp_enabled: Optional[str] = Field(None, description="BGP Enabled"),
    u_bgp_family: Optional[str] = Field(None, description="BGP Family"),
    u_bgp_mpls_vpn: Optional[str] = Field(None, description="BGP MPLS VPN"),
    u_bgp_neighbor: Optional[str] = Field(None, description="BGP Neighbor"),
    u_bgp_peer_group: Optional[str] = Field(None, description="BGP Peer Group"),
    u_cisco_vrf_type: Optional[str] = Field(None, description="Cisco VRF Type"),
    u_created_when: Optional[str] = Field(None, description="Created When"),
    u_default_information_originate: Optional[str] = Field(None, description="Default Information Originate"),
    u_discovery_status: Optional[str] = Field(None, description="Discovery Status"),
    u_export_policy: Optional[str] = Field(None, description="Export Policy"),
    u_export_rts: Optional[str] = Field(None, description="Export RTs"),
    u_filter_input: Optional[str] = Field(None, description="Filter Input"),
    u_filter_output: Optional[str] = Field(None, description="Filter Output"),
    u_group: Optional[str] = Field(None, description="Group"),
    u_idle_timeout: Optional[int] = Field(None, description="Idle Timeout"),
    u_import_path_limit: Optional[int] = Field(None, description="Import Path Limit"),
    u_import_path_selection: Optional[str] = Field(None, description="Import Path Selection"),
    u_import_policy: Optional[str] = Field(None, description="Import Policy"),
    u_import_rts: Optional[str] = Field(None, description="Import RTs"),
    u_inactive: Optional[str] = Field(None, description="Inactive"),
    u_inbound_routing_policy: Optional[str] = Field(None, description="Inbound Routing Policy"),
    u_interfaces: Optional[str] = Field(None, description="Interfaces"),
    u_is_preconfigured_object: Optional[bool] = Field(None, description="Is Preconfigured Object"),
    u_logical_system: Optional[str] = Field(None, description="Logical System"),
    u_maximum_ebgp_and_ibgp_paths: Optional[int] = Field(None, description="Maximum eBGP and iBGP Paths"),
    u_maximum_ebgp_and_ibgp_redundant_paths: Optional[int] = Field(None, description="Maximum eBGP and iBGP Redundant Paths"),
    u_maximum_routes: Optional[int] = Field(None, description="Maximum Routes"),
    u_maximum_unequal_cost_ibgp_paths: Optional[int] = Field(None, description="Maximum Unequal Cost iBGP Paths"),
    u_modified_when: Optional[str] = Field(None, description="Modified When"),
    u_multicast: Optional[str] = Field(None, description="Multicast"),
    u_multipath: Optional[str] = Field(None, description="Multipath"),
    u_network_element: Optional[str] = Field(None, description="Network Element"),
    u_network_for_ne: Optional[str] = Field(None, description="Network for NE"),
    u_operational_status_desired: Optional[int] = Field(None, description="Operational Status Desired"),
    u_ospf_area: Optional[str] = Field(None, description="OSPF Area"),
    u_outbound_routing_policy: Optional[str] = Field(None, description="Outbound Routing Policy"),
    u_parent_network_element: Optional[str] = Field(None, description="Parent Network Element"),
    u_parent_ri_object: Optional[str] = Field(None, description="Parent RI Object"),
    u_prefix_limit: Optional[int] = Field(None, description="Prefix Limit"),
    u_previous_value_stored: Optional[str] = Field(None, description="Previous Value Stored"),
    u_protocol_type: Optional[str] = Field(None, description="Protocol Type"),
    u_rd: Optional[str] = Field(None, description="RD"),
    u_redistribution_routing_policy: Optional[str] = Field(None, description="Redistribution Routing Policy"),
    u_redistribution_static_and_connected: Optional[str] = Field(None, description="Redistribution Static and Connected"),
    u_related_cfs_instances: Optional[str] = Field(None, description="Related CFS Instances"),
    u_related_cfs_orders: Optional[str] = Field(None, description="Related CFS Orders"),
    u_related_rfs_instances: Optional[str] = Field(None, description="Related RFS Instances"),
    u_related_rfs_orders: Optional[str] = Field(None, description="Related RFS Orders"),
    u_rt: Optional[str] = Field(None, description="RT"),
    u_safi: Optional[str] = Field(None, description="SAFI"),
    u_source_rfs_order: Optional[str] = Field(None, description="Source RFS Order"),
    u_static_route: Optional[str] = Field(None, description="Static Route"),
    u_status: Optional[str] = Field(None, description="Status"),
    u_teardown: Optional[int] = Field(None, description="Teardown"),
    u_tina_rfs_order: Optional[str] = Field(None, description="TINA RFS Order"),
    u_top_vpn_numerical_resources: Optional[str] = Field(None, description="Top VPN Numerical Resources"),
    u_type: Optional[str] = Field(None, description="Type"),
    u_used_by: Optional[str] = Field(None, description="Used By"),
    u_vendor_vrf: Optional[str] = Field(None, description="Vendor VRF"),
    u_virtual_tunnel_interface: Optional[str] = Field(None, description="Virtual Tunnel Interface"),
    u_vpn_counter: Optional[str] = Field(None, description="VPN Counter"),
    u_vrf_id: Optional[str] = Field(None, description="VRF ID"),
    u_vrf_multicast: Optional[str] = Field(None, description="VRF Multicast"),
    u_vrf_table_label: Optional[str] = Field(None, description="VRF Table Label"),
    u_vsi: Optional[str] = Field(None, description="VSI"),
    u_wip_object: Optional[bool] = Field(None, description="WIP Object"),
    u_wip_object_updated: Optional[str] = Field(None, description="WIP Object Updated"),
    u_wip_of: Optional[str] = Field(None, description="WIP Of"),
    u_wip_ref: Optional[str] = Field(None, description="WIP Ref"),
    u_work_in_progress_version: Optional[str] = Field(None, description="Work In Progress Version"),
) -> str:
    """Update an existing VRF (Virtual Routing and Forwarding) CI record in ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    # Resolve to sys_id if a name was provided
    sys_id_to_update = vrf_id
    if not is_sys_id(vrf_id):
        search_url = f"{config.api_url}/table/{VRF_TABLE}"
        search_params = {
            "sysparm_query": f"name={vrf_id}",
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
                return f"VRF not found: {vrf_id}"
            sys_id_to_update = s_res[0]["sys_id"]
        except Exception as e:
            return f"Error resolving VRF ID: {str(e)}"

    url = f"{config.api_url}/table/{VRF_TABLE}/{sys_id_to_update}"

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
        # custom VRF fields
        "u_activation_status": u_activation_status,
        "u_active_version": u_active_version,
        "u_afi": u_afi,
        "u_assigned_interfaces": u_assigned_interfaces,
        "u_auto_export": u_auto_export,
        "u_autonomous_system": u_autonomous_system,
        "u_bgp_enabled": u_bgp_enabled,
        "u_bgp_family": u_bgp_family,
        "u_bgp_mpls_vpn": u_bgp_mpls_vpn,
        "u_bgp_neighbor": u_bgp_neighbor,
        "u_bgp_peer_group": u_bgp_peer_group,
        "u_cisco_vrf_type": u_cisco_vrf_type,
        "u_created_when": u_created_when,
        "u_default_information_originate": u_default_information_originate,
        "u_discovery_status": u_discovery_status,
        "u_export_policy": u_export_policy,
        "u_export_rts": u_export_rts,
        "u_filter_input": u_filter_input,
        "u_filter_output": u_filter_output,
        "u_group": u_group,
        "u_idle_timeout": u_idle_timeout,
        "u_import_path_limit": u_import_path_limit,
        "u_import_path_selection": u_import_path_selection,
        "u_import_policy": u_import_policy,
        "u_import_rts": u_import_rts,
        "u_inactive": u_inactive,
        "u_inbound_routing_policy": u_inbound_routing_policy,
        "u_interfaces": u_interfaces,
        "u_is_preconfigured_object": str(u_is_preconfigured_object).lower() if u_is_preconfigured_object is not None else None,
        "u_logical_system": u_logical_system,
        "u_maximum_ebgp_and_ibgp_paths": u_maximum_ebgp_and_ibgp_paths,
        "u_maximum_ebgp_and_ibgp_redundant_paths": u_maximum_ebgp_and_ibgp_redundant_paths,
        "u_maximum_routes": u_maximum_routes,
        "u_maximum_unequal_cost_ibgp_paths": u_maximum_unequal_cost_ibgp_paths,
        "u_modified_when": u_modified_when,
        "u_multicast": u_multicast,
        "u_multipath": u_multipath,
        "u_network_element": u_network_element,
        "u_network_for_ne": u_network_for_ne,
        "u_operational_status_desired": u_operational_status_desired,
        "u_ospf_area": u_ospf_area,
        "u_outbound_routing_policy": u_outbound_routing_policy,
        "u_parent_network_element": u_parent_network_element,
        "u_parent_ri_object": u_parent_ri_object,
        "u_prefix_limit": u_prefix_limit,
        "u_previous_value_stored": u_previous_value_stored,
        "u_protocol_type": u_protocol_type,
        "u_rd": u_rd,
        "u_redistribution_routing_policy": u_redistribution_routing_policy,
        "u_redistribution_static_and_connected": u_redistribution_static_and_connected,
        "u_related_cfs_instances": u_related_cfs_instances,
        "u_related_cfs_orders": u_related_cfs_orders,
        "u_related_rfs_instances": u_related_rfs_instances,
        "u_related_rfs_orders": u_related_rfs_orders,
        "u_rt": u_rt,
        "u_safi": u_safi,
        "u_source_rfs_order": u_source_rfs_order,
        "u_static_route": u_static_route,
        "u_status": u_status,
        "u_teardown": u_teardown,
        "u_tina_rfs_order": u_tina_rfs_order,
        "u_top_vpn_numerical_resources": u_top_vpn_numerical_resources,
        "u_type": u_type,
        "u_used_by": u_used_by,
        "u_vendor_vrf": u_vendor_vrf,
        "u_virtual_tunnel_interface": u_virtual_tunnel_interface,
        "u_vpn_counter": u_vpn_counter,
        "u_vrf_id": u_vrf_id,
        "u_vrf_multicast": u_vrf_multicast,
        "u_vrf_table_label": u_vrf_table_label,
        "u_vsi": u_vsi,
        "u_wip_object": str(u_wip_object).lower() if u_wip_object is not None else None,
        "u_wip_object_updated": u_wip_object_updated,
        "u_wip_of": u_wip_of,
        "u_wip_ref": u_wip_ref,
        "u_work_in_progress_version": u_work_in_progress_version,
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
            return "Failed to update VRF"

        result = data["result"]
        return format_success_response(
            f"VRF updated successfully: {result.get('name')}",
            sys_id=result.get("sys_id"),
            name=result.get("name"),
        )

    except Exception as e:
        logger.error(f"Error updating VRF: {e}")
        return format_error_response("update VRF", e)

