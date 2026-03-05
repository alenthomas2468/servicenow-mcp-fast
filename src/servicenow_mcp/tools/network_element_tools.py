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
    # --- custom network element fields ---
    "u_access_list",
    "u_access_protocol",
    "u_activation_status",
    "u_admin_status",
    "u_aggregate_ports",
    "u_assign_vlans",
    "u_assigned_vlans",
    "u_automatically_push_scripts",
    "u_backup_nms_corba_connection_string",
    "u_backup_server_address",
    "u_backup_server_login",
    "u_backup_server_port",
    "u_bgp_neighbors",
    "u_bgp_peer_group",
    "u_cable_routes",
    "u_cfm_action_profile",
    "u_cfm_maintenance_endpoint",
    "u_channel_group_interface",
    "u_cisco_vrf_definition",
    "u_class_map",
    "u_classifier",
    "u_clli",
    "u_community",
    "u_connect_using_physical_crossconnect",
    "u_connectors",
    "u_crypto_map",
    "u_device_placement",
    "u_dialer_interface",
    "u_discovery_status",
    "u_drop_profile",
    "u_ems_name",
    "u_ethernet_ring",
    "u_evc_instance",
    "u_filter",
    "u_forwarding_class",
    "u_functional_status",
    "u_group",
    "u_ic_node_resources_for_end_points",
    "u_ike_access_profile",
    "u_ike_policy",
    "u_ike_proposal",
    "u_interconnect_node_resources",
    "u_interface_set",
    "u_ipsec_policy",
    "u_ipsec_proposal",
    "u_ipsec_vpn_rule",
    "u_is_preconfigured_object",
    "u_l2_circuit",
    "u_l2_cross_connect",
    "u_l2vpn",
    "u_last_configuration_change",
    "u_lfm_action_profile",
    "u_link_aggregation_interface",
    "u_logical_system",
    "u_login",
    "u_login_for_activation",
    "u_login_for_dnr",
    "u_loopback_interface",
    "u_managed_devices",
    "u_managed_network_elements",
    "u_management_interface",
    "u_management_ip_address",
    "u_model",
    "u_multicast",
    "u_multilink_interface",
    "u_nameservice",
    "u_nat_pool",
    "u_nat_rule",
    "u_network",
    "u_operational_status",
    "u_ospf_area",
    "u_owner",
    "u_parent_network_element",
    "u_parent_ri_object",
    "u_physical_crossconnects",
    "u_physical_paths",
    "u_policer",
    "u_policy_map",
    "u_policy_statement",
    "u_port",
    "u_previous_value_stored",
    "u_primary_nms_corba_connection_string",
    "u_primary_server_address",
    "u_primary_server_login",
    "u_primary_server_port",
    "u_real_ne",
    "u_reference_ip_address",
    "u_related_cfs_instances",
    "u_related_cfs_orders",
    "u_related_rfs_instances",
    "u_related_rfs_orders",
    "u_remove_node_from_ots",
    "u_router_name",
    "u_router_type",
    "u_routing_policy",
    "u_scheduler",
    "u_scheduler_map",
    "u_service_set",
    "u_snmp_community",
    "u_snmp_version",
    "u_stateful_firewall_rule",
    "u_static_route",
    "u_switch_type",
    "u_tina_rfs_order",
    "u_traffic_control_profile",
    "u_tunnel_interface",
    "u_unassign_vlans",
    "u_used_by",
    "u_vendor",
    "u_vendor_name",
    "u_version",
    "u_view_dwdm_network",
    "u_vlan_interface",
    "u_vne",
    "u_vrf",
    "u_vsi",
    "u_wip_object",
    "u_wip_of",
    "u_wip_ref",
])


def _parse_network_element(item: dict) -> dict:
    """Parse a raw ServiceNow network element record into a clean dictionary."""
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
        # --- custom network element fields (Reference) ---
        "u_access_list": extract_display_value(item.get("u_access_list")),
        "u_assigned_vlans": extract_display_value(item.get("u_assigned_vlans")),
        "u_bgp_neighbors": extract_display_value(item.get("u_bgp_neighbors")),
        "u_bgp_peer_group": extract_display_value(item.get("u_bgp_peer_group")),
        "u_cable_routes": extract_display_value(item.get("u_cable_routes")),
        "u_cfm_action_profile": extract_display_value(item.get("u_cfm_action_profile")),
        "u_cfm_maintenance_endpoint": extract_display_value(item.get("u_cfm_maintenance_endpoint")),
        "u_channel_group_interface": extract_display_value(item.get("u_channel_group_interface")),
        "u_class_map": extract_display_value(item.get("u_class_map")),
        "u_classifier": extract_display_value(item.get("u_classifier")),
        "u_community": extract_display_value(item.get("u_community")),
        "u_connect_using_physical_crossconnect": extract_display_value(item.get("u_connect_using_physical_crossconnect")),
        "u_connectors": extract_display_value(item.get("u_connectors")),
        "u_crypto_map": extract_display_value(item.get("u_crypto_map")),
        "u_device_placement": extract_display_value(item.get("u_device_placement")),
        "u_dialer_interface": extract_display_value(item.get("u_dialer_interface")),
        "u_drop_profile": extract_display_value(item.get("u_drop_profile")),
        "u_ethernet_ring": extract_display_value(item.get("u_ethernet_ring")),
        "u_evc_instance": extract_display_value(item.get("u_evc_instance")),
        "u_filter": extract_display_value(item.get("u_filter")),
        "u_forwarding_class": extract_display_value(item.get("u_forwarding_class")),
        "u_group": extract_display_value(item.get("u_group")),
        "u_ic_node_resources_for_end_points": extract_display_value(item.get("u_ic_node_resources_for_end_points")),
        "u_ike_access_profile": extract_display_value(item.get("u_ike_access_profile")),
        "u_ike_policy": extract_display_value(item.get("u_ike_policy")),
        "u_ike_proposal": extract_display_value(item.get("u_ike_proposal")),
        "u_interconnect_node_resources": extract_display_value(item.get("u_interconnect_node_resources")),
        "u_interface_set": extract_display_value(item.get("u_interface_set")),
        "u_ipsec_policy": extract_display_value(item.get("u_ipsec_policy")),
        "u_ipsec_proposal": extract_display_value(item.get("u_ipsec_proposal")),
        "u_ipsec_vpn_rule": extract_display_value(item.get("u_ipsec_vpn_rule")),
        "u_l2_circuit": extract_display_value(item.get("u_l2_circuit")),
        "u_l2_cross_connect": extract_display_value(item.get("u_l2_cross_connect")),
        "u_l2vpn": extract_display_value(item.get("u_l2vpn")),
        "u_lfm_action_profile": extract_display_value(item.get("u_lfm_action_profile")),
        "u_link_aggregation_interface": extract_display_value(item.get("u_link_aggregation_interface")),
        "u_logical_system": extract_display_value(item.get("u_logical_system")),
        "u_loopback_interface": extract_display_value(item.get("u_loopback_interface")),
        "u_managed_devices": extract_display_value(item.get("u_managed_devices")),
        "u_managed_network_elements": extract_display_value(item.get("u_managed_network_elements")),
        "u_management_interface": extract_display_value(item.get("u_management_interface")),
        "u_management_ip_address": extract_display_value(item.get("u_management_ip_address")),
        "u_multicast": extract_display_value(item.get("u_multicast")),
        "u_multilink_interface": extract_display_value(item.get("u_multilink_interface")),
        "u_nat_pool": extract_display_value(item.get("u_nat_pool")),
        "u_nat_rule": extract_display_value(item.get("u_nat_rule")),
        "u_network": extract_display_value(item.get("u_network")),
        "u_ospf_area": extract_display_value(item.get("u_ospf_area")),
        "u_parent_network_element": extract_display_value(item.get("u_parent_network_element")),
        "u_parent_ri_object": extract_display_value(item.get("u_parent_ri_object")),
        "u_physical_crossconnects": extract_display_value(item.get("u_physical_crossconnects")),
        "u_physical_paths": extract_display_value(item.get("u_physical_paths")),
        "u_policer": extract_display_value(item.get("u_policer")),
        "u_policy_map": extract_display_value(item.get("u_policy_map")),
        "u_policy_statement": extract_display_value(item.get("u_policy_statement")),
        "u_real_ne": extract_display_value(item.get("u_real_ne")),
        "u_reference_ip_address": extract_display_value(item.get("u_reference_ip_address")),
        "u_routing_policy": extract_display_value(item.get("u_routing_policy")),
        "u_scheduler": extract_display_value(item.get("u_scheduler")),
        "u_scheduler_map": extract_display_value(item.get("u_scheduler_map")),
        "u_service_set": extract_display_value(item.get("u_service_set")),
        "u_stateful_firewall_rule": extract_display_value(item.get("u_stateful_firewall_rule")),
        "u_static_route": extract_display_value(item.get("u_static_route")),
        "u_tina_rfs_order": extract_display_value(item.get("u_tina_rfs_order")),
        "u_traffic_control_profile": extract_display_value(item.get("u_traffic_control_profile")),
        "u_tunnel_interface": extract_display_value(item.get("u_tunnel_interface")),
        "u_vlan_interface": extract_display_value(item.get("u_vlan_interface")),
        "u_vne": extract_display_value(item.get("u_vne")),
        "u_vrf": extract_display_value(item.get("u_vrf")),
        "u_vsi": extract_display_value(item.get("u_vsi")),
        "u_wip_of": extract_display_value(item.get("u_wip_of")),
        "u_wip_ref": extract_display_value(item.get("u_wip_ref")),
        # --- custom network element fields (Choice/String) ---
        "u_access_protocol": item.get("u_access_protocol"),
        "u_activation_status": item.get("u_activation_status"),
        "u_admin_status": item.get("u_admin_status"),
        "u_aggregate_ports": item.get("u_aggregate_ports"),
        "u_assign_vlans": item.get("u_assign_vlans"),
        "u_automatically_push_scripts": item.get("u_automatically_push_scripts"),
        "u_backup_nms_corba_connection_string": item.get("u_backup_nms_corba_connection_string"),
        "u_backup_server_address": item.get("u_backup_server_address"),
        "u_backup_server_login": item.get("u_backup_server_login"),
        "u_backup_server_port": item.get("u_backup_server_port"),
        "u_cisco_vrf_definition": item.get("u_cisco_vrf_definition"),
        "u_clli": item.get("u_clli"),
        "u_discovery_status": item.get("u_discovery_status"),
        "u_ems_name": item.get("u_ems_name"),
        "u_functional_status": item.get("u_functional_status"),
        "u_last_configuration_change": item.get("u_last_configuration_change"),
        "u_login": item.get("u_login"),
        "u_login_for_activation": item.get("u_login_for_activation"),
        "u_login_for_dnr": item.get("u_login_for_dnr"),
        "u_model": item.get("u_model"),
        "u_nameservice": item.get("u_nameservice"),
        "u_operational_status": item.get("u_operational_status"),
        "u_owner": item.get("u_owner"),
        "u_port": item.get("u_port"),
        "u_previous_value_stored": item.get("u_previous_value_stored"),
        "u_primary_nms_corba_connection_string": item.get("u_primary_nms_corba_connection_string"),
        "u_primary_server_address": item.get("u_primary_server_address"),
        "u_primary_server_login": item.get("u_primary_server_login"),
        "u_primary_server_port": item.get("u_primary_server_port"),
        "u_remove_node_from_ots": item.get("u_remove_node_from_ots"),
        "u_router_name": item.get("u_router_name"),
        "u_router_type": item.get("u_router_type"),
        "u_snmp_community": item.get("u_snmp_community"),
        "u_snmp_version": item.get("u_snmp_version"),
        "u_switch_type": item.get("u_switch_type"),
        "u_unassign_vlans": item.get("u_unassign_vlans"),
        "u_vendor": item.get("u_vendor"),
        "u_vendor_name": item.get("u_vendor_name"),
        "u_version": item.get("u_version"),
        "u_view_dwdm_network": item.get("u_view_dwdm_network"),
        # --- custom network element fields (List) ---
        "u_related_cfs_instances": item.get("u_related_cfs_instances"),
        "u_related_cfs_orders": item.get("u_related_cfs_orders"),
        "u_related_rfs_instances": item.get("u_related_rfs_instances"),
        "u_related_rfs_orders": item.get("u_related_rfs_orders"),
        "u_used_by": item.get("u_used_by"),
        # --- custom network element fields (Boolean) ---
        "u_is_preconfigured_object": item.get("u_is_preconfigured_object"),
        "u_wip_object": item.get("u_wip_object"),
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
    # --- inherited cmdb_ci fields ---
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
    # --- custom fields (Choice/String) ---
    u_access_protocol: Optional[str] = Field(None, description="Access Protocol"),
    u_activation_status: Optional[str] = Field(None, description="Activation Status"),
    u_admin_status: Optional[str] = Field(None, description="Admin Status"),
    u_aggregate_ports: Optional[str] = Field(None, description="Aggregate Ports"),
    u_assign_vlans: Optional[str] = Field(None, description="Assign VLANs"),
    u_automatically_push_scripts: Optional[str] = Field(None, description="Automatically push scripts"),
    u_backup_nms_corba_connection_string: Optional[str] = Field(None, description="Backup NMS CORBA Connection string"),
    u_backup_server_address: Optional[str] = Field(None, description="Backup Server Address"),
    u_backup_server_login: Optional[str] = Field(None, description="Backup Server Login"),
    u_cisco_vrf_definition: Optional[str] = Field(None, description="Cisco VRF Definition"),
    u_clli: Optional[str] = Field(None, description="CLLI"),
    u_discovery_status: Optional[str] = Field(None, description="Discovery Status"),
    u_ems_name: Optional[str] = Field(None, description="EMS Name"),
    u_functional_status: Optional[str] = Field(None, description="Functional Status"),
    u_last_configuration_change: Optional[str] = Field(None, description="Last Configuration Change"),
    u_login: Optional[str] = Field(None, description="Login"),
    u_login_for_activation: Optional[str] = Field(None, description="Login for Activation"),
    u_login_for_dnr: Optional[str] = Field(None, description="Login for DnR"),
    u_model: Optional[str] = Field(None, description="Model"),
    u_nameservice: Optional[str] = Field(None, description="NameService"),
    u_operational_status: Optional[str] = Field(None, description="Operational Status (custom)"),
    u_owner: Optional[str] = Field(None, description="Owner"),
    u_port: Optional[str] = Field(None, description="Port"),
    u_previous_value_stored: Optional[str] = Field(None, description="Previous Value Stored"),
    u_primary_nms_corba_connection_string: Optional[str] = Field(None, description="Primary NMS CORBA Connection string"),
    u_primary_server_address: Optional[str] = Field(None, description="Primary Server Address"),
    u_primary_server_login: Optional[str] = Field(None, description="Primary Server Login"),
    u_remove_node_from_ots: Optional[str] = Field(None, description="Remove Node from OTS"),
    u_router_name: Optional[str] = Field(None, description="Router Name"),
    u_router_type: Optional[str] = Field(None, description="Router Type"),
    u_snmp_community: Optional[str] = Field(None, description="SNMP Community"),
    u_snmp_version: Optional[str] = Field(None, description="SNMP Version"),
    u_switch_type: Optional[str] = Field(None, description="Switch Type"),
    u_unassign_vlans: Optional[str] = Field(None, description="Unassign VLANs"),
    u_vendor: Optional[str] = Field(None, description="Vendor (custom)"),
    u_vendor_name: Optional[str] = Field(None, description="Vendor Name"),
    u_version: Optional[str] = Field(None, description="Firmware Version"),
    u_view_dwdm_network: Optional[str] = Field(None, description="View DWDM Network"),
    # --- custom fields (Reference) ---
    u_access_list: Optional[str] = Field(None, description="Access List (sys_id or display value)"),
    u_assigned_vlans: Optional[str] = Field(None, description="Assigned VLANs (sys_id or display value)"),
    u_bgp_neighbors: Optional[str] = Field(None, description="BGP Neighbors (sys_id or display value)"),
    u_bgp_peer_group: Optional[str] = Field(None, description="BGP Peer Group (sys_id or display value)"),
    u_cable_routes: Optional[str] = Field(None, description="Cable Routes (sys_id or display value)"),
    u_cfm_action_profile: Optional[str] = Field(None, description="CFM Action Profile (sys_id or display value)"),
    u_cfm_maintenance_endpoint: Optional[str] = Field(None, description="CFM Maintenance Endpoint (sys_id or display value)"),
    u_channel_group_interface: Optional[str] = Field(None, description="Channel Group Interface (sys_id or display value)"),
    u_class_map: Optional[str] = Field(None, description="Class Map (sys_id or display value)"),
    u_classifier: Optional[str] = Field(None, description="Classifier (sys_id or display value)"),
    u_community: Optional[str] = Field(None, description="Community (sys_id or display value)"),
    u_connect_using_physical_crossconnect: Optional[str] = Field(None, description="Connect using Physical Crossconnect (sys_id or display value)"),
    u_connectors: Optional[str] = Field(None, description="Connectors (sys_id or display value)"),
    u_crypto_map: Optional[str] = Field(None, description="Crypto Map (sys_id or display value)"),
    u_device_placement: Optional[str] = Field(None, description="Device Placement (sys_id or display value)"),
    u_dialer_interface: Optional[str] = Field(None, description="Dialer Interface (sys_id or display value)"),
    u_drop_profile: Optional[str] = Field(None, description="Drop Profile (sys_id or display value)"),
    u_ethernet_ring: Optional[str] = Field(None, description="Ethernet Ring (sys_id or display value)"),
    u_evc_instance: Optional[str] = Field(None, description="EVC Instance (sys_id or display value)"),
    u_filter: Optional[str] = Field(None, description="Filter (sys_id or display value)"),
    u_forwarding_class: Optional[str] = Field(None, description="Forwarding Class (sys_id or display value)"),
    u_group: Optional[str] = Field(None, description="Group (sys_id or display value)"),
    u_ic_node_resources_for_end_points: Optional[str] = Field(None, description="IC Node Resources for End Points (sys_id or display value)"),
    u_ike_access_profile: Optional[str] = Field(None, description="IKE Access Profile (sys_id or display value)"),
    u_ike_policy: Optional[str] = Field(None, description="IKE Policy (sys_id or display value)"),
    u_ike_proposal: Optional[str] = Field(None, description="IKE Proposal (sys_id or display value)"),
    u_interconnect_node_resources: Optional[str] = Field(None, description="Interconnect Node Resources (sys_id or display value)"),
    u_interface_set: Optional[str] = Field(None, description="Interface Set (sys_id or display value)"),
    u_ipsec_policy: Optional[str] = Field(None, description="IPsec Policy (sys_id or display value)"),
    u_ipsec_proposal: Optional[str] = Field(None, description="IPSec Proposal (sys_id or display value)"),
    u_ipsec_vpn_rule: Optional[str] = Field(None, description="IPSec VPN Rule (sys_id or display value)"),
    u_l2_circuit: Optional[str] = Field(None, description="L2 Circuit (sys_id or display value)"),
    u_l2_cross_connect: Optional[str] = Field(None, description="L2 Cross Connect (sys_id or display value)"),
    u_l2vpn: Optional[str] = Field(None, description="L2VPN (sys_id or display value)"),
    u_lfm_action_profile: Optional[str] = Field(None, description="LFM Action Profile (sys_id or display value)"),
    u_link_aggregation_interface: Optional[str] = Field(None, description="Link Aggregation Interface (sys_id or display value)"),
    u_logical_system: Optional[str] = Field(None, description="Logical System (sys_id or display value)"),
    u_loopback_interface: Optional[str] = Field(None, description="Loopback Interface (sys_id or display value)"),
    u_managed_devices: Optional[str] = Field(None, description="Managed Devices (sys_id or display value)"),
    u_managed_network_elements: Optional[str] = Field(None, description="Managed Network Elements (sys_id or display value)"),
    u_management_interface: Optional[str] = Field(None, description="Management Interface (sys_id or display value)"),
    u_management_ip_address: Optional[str] = Field(None, description="Management IP address (sys_id or display value)"),
    u_multicast: Optional[str] = Field(None, description="Multicast (sys_id or display value)"),
    u_multilink_interface: Optional[str] = Field(None, description="Multilink Interface (sys_id or display value)"),
    u_nat_pool: Optional[str] = Field(None, description="NAT Pool (sys_id or display value)"),
    u_nat_rule: Optional[str] = Field(None, description="NAT Rule (sys_id or display value)"),
    u_network: Optional[str] = Field(None, description="Ethernet Switch Network (sys_id or display value)"),
    u_ospf_area: Optional[str] = Field(None, description="OSPF Area (sys_id or display value)"),
    u_parent_network_element: Optional[str] = Field(None, description="Parent Network Element (sys_id or display value)"),
    u_parent_ri_object: Optional[str] = Field(None, description="Parent RI Object (sys_id or display value)"),
    u_physical_crossconnects: Optional[str] = Field(None, description="Physical Crossconnects (sys_id or display value)"),
    u_physical_paths: Optional[str] = Field(None, description="Physical Paths (sys_id or display value)"),
    u_policer: Optional[str] = Field(None, description="Policer (sys_id or display value)"),
    u_policy_map: Optional[str] = Field(None, description="Policy Map (sys_id or display value)"),
    u_policy_statement: Optional[str] = Field(None, description="Policy Statement (sys_id or display value)"),
    u_real_ne: Optional[str] = Field(None, description="Real NE (sys_id or display value)"),
    u_reference_ip_address: Optional[str] = Field(None, description="Reference Ip Address (sys_id or display value)"),
    u_routing_policy: Optional[str] = Field(None, description="Routing Policy (sys_id or display value)"),
    u_scheduler: Optional[str] = Field(None, description="Scheduler (sys_id or display value)"),
    u_scheduler_map: Optional[str] = Field(None, description="Scheduler Map (sys_id or display value)"),
    u_service_set: Optional[str] = Field(None, description="Service Set (sys_id or display value)"),
    u_stateful_firewall_rule: Optional[str] = Field(None, description="Stateful Firewall Rule (sys_id or display value)"),
    u_static_route: Optional[str] = Field(None, description="Static Route (sys_id or display value)"),
    u_tina_rfs_order: Optional[str] = Field(None, description="TINA RFS Order (sys_id or display value)"),
    u_traffic_control_profile: Optional[str] = Field(None, description="Traffic Control Profile (sys_id or display value)"),
    u_tunnel_interface: Optional[str] = Field(None, description="Tunnel Interface (sys_id or display value)"),
    u_vlan_interface: Optional[str] = Field(None, description="VLAN Interface (sys_id or display value)"),
    u_vne: Optional[str] = Field(None, description="VNE (sys_id or display value)"),
    u_vrf: Optional[str] = Field(None, description="VRF (sys_id or display value)"),
    u_vsi: Optional[str] = Field(None, description="VSI (sys_id or display value)"),
    u_wip_of: Optional[str] = Field(None, description="WIP Of (sys_id or display value)"),
    u_wip_ref: Optional[str] = Field(None, description="WIP Ref (sys_id or display value)"),
    # --- custom fields (List) ---
    u_related_cfs_instances: Optional[str] = Field(None, description="Related CFS Instances (comma-separated sys_ids)"),
    u_related_cfs_orders: Optional[str] = Field(None, description="Related CFS Orders (comma-separated sys_ids)"),
    u_related_rfs_instances: Optional[str] = Field(None, description="Related RFS Instances (comma-separated sys_ids)"),
    u_related_rfs_orders: Optional[str] = Field(None, description="Related RFS Orders (comma-separated sys_ids)"),
    u_used_by: Optional[str] = Field(None, description="Used By (comma-separated sys_ids)"),
    # --- custom fields (Integer) ---
    u_backup_server_port: Optional[int] = Field(None, description="Backup Server Port"),
    u_primary_server_port: Optional[int] = Field(None, description="Primary Server Port"),
    # --- custom fields (Boolean) ---
    u_is_preconfigured_object: Optional[bool] = Field(None, description="Is PreConfigured Object?"),
    u_wip_object: Optional[bool] = Field(None, description="WIP Object"),
) -> str:
    """Create a new Network Element CI record in ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    url = f"{config.api_url}/table/{NETWORK_ELEMENT_TABLE}"

    body = build_request_data(
        required_fields={"name": name},
        optional_fields={
            # inherited cmdb_ci fields
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
            # custom fields (Choice/String)
            "u_access_protocol": u_access_protocol,
            "u_activation_status": u_activation_status,
            "u_admin_status": u_admin_status,
            "u_aggregate_ports": u_aggregate_ports,
            "u_assign_vlans": u_assign_vlans,
            "u_automatically_push_scripts": u_automatically_push_scripts,
            "u_backup_nms_corba_connection_string": u_backup_nms_corba_connection_string,
            "u_backup_server_address": u_backup_server_address,
            "u_backup_server_login": u_backup_server_login,
            "u_cisco_vrf_definition": u_cisco_vrf_definition,
            "u_clli": u_clli,
            "u_discovery_status": u_discovery_status,
            "u_ems_name": u_ems_name,
            "u_functional_status": u_functional_status,
            "u_last_configuration_change": u_last_configuration_change,
            "u_login": u_login,
            "u_login_for_activation": u_login_for_activation,
            "u_login_for_dnr": u_login_for_dnr,
            "u_model": u_model,
            "u_nameservice": u_nameservice,
            "u_operational_status": u_operational_status,
            "u_owner": u_owner,
            "u_port": u_port,
            "u_previous_value_stored": u_previous_value_stored,
            "u_primary_nms_corba_connection_string": u_primary_nms_corba_connection_string,
            "u_primary_server_address": u_primary_server_address,
            "u_primary_server_login": u_primary_server_login,
            "u_remove_node_from_ots": u_remove_node_from_ots,
            "u_router_name": u_router_name,
            "u_router_type": u_router_type,
            "u_snmp_community": u_snmp_community,
            "u_snmp_version": u_snmp_version,
            "u_switch_type": u_switch_type,
            "u_unassign_vlans": u_unassign_vlans,
            "u_vendor": u_vendor,
            "u_vendor_name": u_vendor_name,
            "u_version": u_version,
            "u_view_dwdm_network": u_view_dwdm_network,
            # custom fields (Reference)
            "u_access_list": u_access_list,
            "u_assigned_vlans": u_assigned_vlans,
            "u_bgp_neighbors": u_bgp_neighbors,
            "u_bgp_peer_group": u_bgp_peer_group,
            "u_cable_routes": u_cable_routes,
            "u_cfm_action_profile": u_cfm_action_profile,
            "u_cfm_maintenance_endpoint": u_cfm_maintenance_endpoint,
            "u_channel_group_interface": u_channel_group_interface,
            "u_class_map": u_class_map,
            "u_classifier": u_classifier,
            "u_community": u_community,
            "u_connect_using_physical_crossconnect": u_connect_using_physical_crossconnect,
            "u_connectors": u_connectors,
            "u_crypto_map": u_crypto_map,
            "u_device_placement": u_device_placement,
            "u_dialer_interface": u_dialer_interface,
            "u_drop_profile": u_drop_profile,
            "u_ethernet_ring": u_ethernet_ring,
            "u_evc_instance": u_evc_instance,
            "u_filter": u_filter,
            "u_forwarding_class": u_forwarding_class,
            "u_group": u_group,
            "u_ic_node_resources_for_end_points": u_ic_node_resources_for_end_points,
            "u_ike_access_profile": u_ike_access_profile,
            "u_ike_policy": u_ike_policy,
            "u_ike_proposal": u_ike_proposal,
            "u_interconnect_node_resources": u_interconnect_node_resources,
            "u_interface_set": u_interface_set,
            "u_ipsec_policy": u_ipsec_policy,
            "u_ipsec_proposal": u_ipsec_proposal,
            "u_ipsec_vpn_rule": u_ipsec_vpn_rule,
            "u_l2_circuit": u_l2_circuit,
            "u_l2_cross_connect": u_l2_cross_connect,
            "u_l2vpn": u_l2vpn,
            "u_lfm_action_profile": u_lfm_action_profile,
            "u_link_aggregation_interface": u_link_aggregation_interface,
            "u_logical_system": u_logical_system,
            "u_loopback_interface": u_loopback_interface,
            "u_managed_devices": u_managed_devices,
            "u_managed_network_elements": u_managed_network_elements,
            "u_management_interface": u_management_interface,
            "u_management_ip_address": u_management_ip_address,
            "u_multicast": u_multicast,
            "u_multilink_interface": u_multilink_interface,
            "u_nat_pool": u_nat_pool,
            "u_nat_rule": u_nat_rule,
            "u_network": u_network,
            "u_ospf_area": u_ospf_area,
            "u_parent_network_element": u_parent_network_element,
            "u_parent_ri_object": u_parent_ri_object,
            "u_physical_crossconnects": u_physical_crossconnects,
            "u_physical_paths": u_physical_paths,
            "u_policer": u_policer,
            "u_policy_map": u_policy_map,
            "u_policy_statement": u_policy_statement,
            "u_real_ne": u_real_ne,
            "u_reference_ip_address": u_reference_ip_address,
            "u_routing_policy": u_routing_policy,
            "u_scheduler": u_scheduler,
            "u_scheduler_map": u_scheduler_map,
            "u_service_set": u_service_set,
            "u_stateful_firewall_rule": u_stateful_firewall_rule,
            "u_static_route": u_static_route,
            "u_tina_rfs_order": u_tina_rfs_order,
            "u_traffic_control_profile": u_traffic_control_profile,
            "u_tunnel_interface": u_tunnel_interface,
            "u_vlan_interface": u_vlan_interface,
            "u_vne": u_vne,
            "u_vrf": u_vrf,
            "u_vsi": u_vsi,
            "u_wip_of": u_wip_of,
            "u_wip_ref": u_wip_ref,
            # custom fields (List)
            "u_related_cfs_instances": u_related_cfs_instances,
            "u_related_cfs_orders": u_related_cfs_orders,
            "u_related_rfs_instances": u_related_rfs_instances,
            "u_related_rfs_orders": u_related_rfs_orders,
            "u_used_by": u_used_by,
            # custom fields (Integer)
            "u_backup_server_port": str(u_backup_server_port) if u_backup_server_port is not None else None,
            "u_primary_server_port": str(u_primary_server_port) if u_primary_server_port is not None else None,
            # custom fields (Boolean)
            "u_is_preconfigured_object": str(u_is_preconfigured_object).lower() if u_is_preconfigured_object is not None else None,
            "u_wip_object": str(u_wip_object).lower() if u_wip_object is not None else None,
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
    # --- inherited cmdb_ci fields ---
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
    # --- custom fields (Choice/String) ---
    u_access_protocol: Optional[str] = Field(None, description="Access Protocol"),
    u_activation_status: Optional[str] = Field(None, description="Activation Status"),
    u_admin_status: Optional[str] = Field(None, description="Admin Status"),
    u_aggregate_ports: Optional[str] = Field(None, description="Aggregate Ports"),
    u_assign_vlans: Optional[str] = Field(None, description="Assign VLANs"),
    u_automatically_push_scripts: Optional[str] = Field(None, description="Automatically push scripts"),
    u_backup_nms_corba_connection_string: Optional[str] = Field(None, description="Backup NMS CORBA Connection string"),
    u_backup_server_address: Optional[str] = Field(None, description="Backup Server Address"),
    u_backup_server_login: Optional[str] = Field(None, description="Backup Server Login"),
    u_cisco_vrf_definition: Optional[str] = Field(None, description="Cisco VRF Definition"),
    u_clli: Optional[str] = Field(None, description="CLLI"),
    u_discovery_status: Optional[str] = Field(None, description="Discovery Status"),
    u_ems_name: Optional[str] = Field(None, description="EMS Name"),
    u_functional_status: Optional[str] = Field(None, description="Functional Status"),
    u_last_configuration_change: Optional[str] = Field(None, description="Last Configuration Change"),
    u_login: Optional[str] = Field(None, description="Login"),
    u_login_for_activation: Optional[str] = Field(None, description="Login for Activation"),
    u_login_for_dnr: Optional[str] = Field(None, description="Login for DnR"),
    u_model: Optional[str] = Field(None, description="Model"),
    u_nameservice: Optional[str] = Field(None, description="NameService"),
    u_operational_status: Optional[str] = Field(None, description="Operational Status (custom)"),
    u_owner: Optional[str] = Field(None, description="Owner"),
    u_port: Optional[str] = Field(None, description="Port"),
    u_previous_value_stored: Optional[str] = Field(None, description="Previous Value Stored"),
    u_primary_nms_corba_connection_string: Optional[str] = Field(None, description="Primary NMS CORBA Connection string"),
    u_primary_server_address: Optional[str] = Field(None, description="Primary Server Address"),
    u_primary_server_login: Optional[str] = Field(None, description="Primary Server Login"),
    u_remove_node_from_ots: Optional[str] = Field(None, description="Remove Node from OTS"),
    u_router_name: Optional[str] = Field(None, description="Router Name"),
    u_router_type: Optional[str] = Field(None, description="Router Type"),
    u_snmp_community: Optional[str] = Field(None, description="SNMP Community"),
    u_snmp_version: Optional[str] = Field(None, description="SNMP Version"),
    u_switch_type: Optional[str] = Field(None, description="Switch Type"),
    u_unassign_vlans: Optional[str] = Field(None, description="Unassign VLANs"),
    u_vendor: Optional[str] = Field(None, description="Vendor (custom)"),
    u_vendor_name: Optional[str] = Field(None, description="Vendor Name"),
    u_version: Optional[str] = Field(None, description="Firmware Version"),
    u_view_dwdm_network: Optional[str] = Field(None, description="View DWDM Network"),
    # --- custom fields (Reference) ---
    u_access_list: Optional[str] = Field(None, description="Access List (sys_id or display value)"),
    u_assigned_vlans: Optional[str] = Field(None, description="Assigned VLANs (sys_id or display value)"),
    u_bgp_neighbors: Optional[str] = Field(None, description="BGP Neighbors (sys_id or display value)"),
    u_bgp_peer_group: Optional[str] = Field(None, description="BGP Peer Group (sys_id or display value)"),
    u_cable_routes: Optional[str] = Field(None, description="Cable Routes (sys_id or display value)"),
    u_cfm_action_profile: Optional[str] = Field(None, description="CFM Action Profile (sys_id or display value)"),
    u_cfm_maintenance_endpoint: Optional[str] = Field(None, description="CFM Maintenance Endpoint (sys_id or display value)"),
    u_channel_group_interface: Optional[str] = Field(None, description="Channel Group Interface (sys_id or display value)"),
    u_class_map: Optional[str] = Field(None, description="Class Map (sys_id or display value)"),
    u_classifier: Optional[str] = Field(None, description="Classifier (sys_id or display value)"),
    u_community: Optional[str] = Field(None, description="Community (sys_id or display value)"),
    u_connect_using_physical_crossconnect: Optional[str] = Field(None, description="Connect using Physical Crossconnect (sys_id or display value)"),
    u_connectors: Optional[str] = Field(None, description="Connectors (sys_id or display value)"),
    u_crypto_map: Optional[str] = Field(None, description="Crypto Map (sys_id or display value)"),
    u_device_placement: Optional[str] = Field(None, description="Device Placement (sys_id or display value)"),
    u_dialer_interface: Optional[str] = Field(None, description="Dialer Interface (sys_id or display value)"),
    u_drop_profile: Optional[str] = Field(None, description="Drop Profile (sys_id or display value)"),
    u_ethernet_ring: Optional[str] = Field(None, description="Ethernet Ring (sys_id or display value)"),
    u_evc_instance: Optional[str] = Field(None, description="EVC Instance (sys_id or display value)"),
    u_filter: Optional[str] = Field(None, description="Filter (sys_id or display value)"),
    u_forwarding_class: Optional[str] = Field(None, description="Forwarding Class (sys_id or display value)"),
    u_group: Optional[str] = Field(None, description="Group (sys_id or display value)"),
    u_ic_node_resources_for_end_points: Optional[str] = Field(None, description="IC Node Resources for End Points (sys_id or display value)"),
    u_ike_access_profile: Optional[str] = Field(None, description="IKE Access Profile (sys_id or display value)"),
    u_ike_policy: Optional[str] = Field(None, description="IKE Policy (sys_id or display value)"),
    u_ike_proposal: Optional[str] = Field(None, description="IKE Proposal (sys_id or display value)"),
    u_interconnect_node_resources: Optional[str] = Field(None, description="Interconnect Node Resources (sys_id or display value)"),
    u_interface_set: Optional[str] = Field(None, description="Interface Set (sys_id or display value)"),
    u_ipsec_policy: Optional[str] = Field(None, description="IPsec Policy (sys_id or display value)"),
    u_ipsec_proposal: Optional[str] = Field(None, description="IPSec Proposal (sys_id or display value)"),
    u_ipsec_vpn_rule: Optional[str] = Field(None, description="IPSec VPN Rule (sys_id or display value)"),
    u_l2_circuit: Optional[str] = Field(None, description="L2 Circuit (sys_id or display value)"),
    u_l2_cross_connect: Optional[str] = Field(None, description="L2 Cross Connect (sys_id or display value)"),
    u_l2vpn: Optional[str] = Field(None, description="L2VPN (sys_id or display value)"),
    u_lfm_action_profile: Optional[str] = Field(None, description="LFM Action Profile (sys_id or display value)"),
    u_link_aggregation_interface: Optional[str] = Field(None, description="Link Aggregation Interface (sys_id or display value)"),
    u_logical_system: Optional[str] = Field(None, description="Logical System (sys_id or display value)"),
    u_loopback_interface: Optional[str] = Field(None, description="Loopback Interface (sys_id or display value)"),
    u_managed_devices: Optional[str] = Field(None, description="Managed Devices (sys_id or display value)"),
    u_managed_network_elements: Optional[str] = Field(None, description="Managed Network Elements (sys_id or display value)"),
    u_management_interface: Optional[str] = Field(None, description="Management Interface (sys_id or display value)"),
    u_management_ip_address: Optional[str] = Field(None, description="Management IP address (sys_id or display value)"),
    u_multicast: Optional[str] = Field(None, description="Multicast (sys_id or display value)"),
    u_multilink_interface: Optional[str] = Field(None, description="Multilink Interface (sys_id or display value)"),
    u_nat_pool: Optional[str] = Field(None, description="NAT Pool (sys_id or display value)"),
    u_nat_rule: Optional[str] = Field(None, description="NAT Rule (sys_id or display value)"),
    u_network: Optional[str] = Field(None, description="Ethernet Switch Network (sys_id or display value)"),
    u_ospf_area: Optional[str] = Field(None, description="OSPF Area (sys_id or display value)"),
    u_parent_network_element: Optional[str] = Field(None, description="Parent Network Element (sys_id or display value)"),
    u_parent_ri_object: Optional[str] = Field(None, description="Parent RI Object (sys_id or display value)"),
    u_physical_crossconnects: Optional[str] = Field(None, description="Physical Crossconnects (sys_id or display value)"),
    u_physical_paths: Optional[str] = Field(None, description="Physical Paths (sys_id or display value)"),
    u_policer: Optional[str] = Field(None, description="Policer (sys_id or display value)"),
    u_policy_map: Optional[str] = Field(None, description="Policy Map (sys_id or display value)"),
    u_policy_statement: Optional[str] = Field(None, description="Policy Statement (sys_id or display value)"),
    u_real_ne: Optional[str] = Field(None, description="Real NE (sys_id or display value)"),
    u_reference_ip_address: Optional[str] = Field(None, description="Reference Ip Address (sys_id or display value)"),
    u_routing_policy: Optional[str] = Field(None, description="Routing Policy (sys_id or display value)"),
    u_scheduler: Optional[str] = Field(None, description="Scheduler (sys_id or display value)"),
    u_scheduler_map: Optional[str] = Field(None, description="Scheduler Map (sys_id or display value)"),
    u_service_set: Optional[str] = Field(None, description="Service Set (sys_id or display value)"),
    u_stateful_firewall_rule: Optional[str] = Field(None, description="Stateful Firewall Rule (sys_id or display value)"),
    u_static_route: Optional[str] = Field(None, description="Static Route (sys_id or display value)"),
    u_tina_rfs_order: Optional[str] = Field(None, description="TINA RFS Order (sys_id or display value)"),
    u_traffic_control_profile: Optional[str] = Field(None, description="Traffic Control Profile (sys_id or display value)"),
    u_tunnel_interface: Optional[str] = Field(None, description="Tunnel Interface (sys_id or display value)"),
    u_vlan_interface: Optional[str] = Field(None, description="VLAN Interface (sys_id or display value)"),
    u_vne: Optional[str] = Field(None, description="VNE (sys_id or display value)"),
    u_vrf: Optional[str] = Field(None, description="VRF (sys_id or display value)"),
    u_vsi: Optional[str] = Field(None, description="VSI (sys_id or display value)"),
    u_wip_of: Optional[str] = Field(None, description="WIP Of (sys_id or display value)"),
    u_wip_ref: Optional[str] = Field(None, description="WIP Ref (sys_id or display value)"),
    # --- custom fields (List) ---
    u_related_cfs_instances: Optional[str] = Field(None, description="Related CFS Instances (comma-separated sys_ids)"),
    u_related_cfs_orders: Optional[str] = Field(None, description="Related CFS Orders (comma-separated sys_ids)"),
    u_related_rfs_instances: Optional[str] = Field(None, description="Related RFS Instances (comma-separated sys_ids)"),
    u_related_rfs_orders: Optional[str] = Field(None, description="Related RFS Orders (comma-separated sys_ids)"),
    u_used_by: Optional[str] = Field(None, description="Used By (comma-separated sys_ids)"),
    # --- custom fields (Integer) ---
    u_backup_server_port: Optional[int] = Field(None, description="Backup Server Port"),
    u_primary_server_port: Optional[int] = Field(None, description="Primary Server Port"),
    # --- custom fields (Boolean) ---
    u_is_preconfigured_object: Optional[bool] = Field(None, description="Is PreConfigured Object?"),
    u_wip_object: Optional[bool] = Field(None, description="WIP Object"),
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
        # inherited cmdb_ci fields
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
        # custom fields (Choice/String)
        "u_access_protocol": u_access_protocol,
        "u_activation_status": u_activation_status,
        "u_admin_status": u_admin_status,
        "u_aggregate_ports": u_aggregate_ports,
        "u_assign_vlans": u_assign_vlans,
        "u_automatically_push_scripts": u_automatically_push_scripts,
        "u_backup_nms_corba_connection_string": u_backup_nms_corba_connection_string,
        "u_backup_server_address": u_backup_server_address,
        "u_backup_server_login": u_backup_server_login,
        "u_cisco_vrf_definition": u_cisco_vrf_definition,
        "u_clli": u_clli,
        "u_discovery_status": u_discovery_status,
        "u_ems_name": u_ems_name,
        "u_functional_status": u_functional_status,
        "u_last_configuration_change": u_last_configuration_change,
        "u_login": u_login,
        "u_login_for_activation": u_login_for_activation,
        "u_login_for_dnr": u_login_for_dnr,
        "u_model": u_model,
        "u_nameservice": u_nameservice,
        "u_operational_status": u_operational_status,
        "u_owner": u_owner,
        "u_port": u_port,
        "u_previous_value_stored": u_previous_value_stored,
        "u_primary_nms_corba_connection_string": u_primary_nms_corba_connection_string,
        "u_primary_server_address": u_primary_server_address,
        "u_primary_server_login": u_primary_server_login,
        "u_remove_node_from_ots": u_remove_node_from_ots,
        "u_router_name": u_router_name,
        "u_router_type": u_router_type,
        "u_snmp_community": u_snmp_community,
        "u_snmp_version": u_snmp_version,
        "u_switch_type": u_switch_type,
        "u_unassign_vlans": u_unassign_vlans,
        "u_vendor": u_vendor,
        "u_vendor_name": u_vendor_name,
        "u_version": u_version,
        "u_view_dwdm_network": u_view_dwdm_network,
        # custom fields (Reference)
        "u_access_list": u_access_list,
        "u_assigned_vlans": u_assigned_vlans,
        "u_bgp_neighbors": u_bgp_neighbors,
        "u_bgp_peer_group": u_bgp_peer_group,
        "u_cable_routes": u_cable_routes,
        "u_cfm_action_profile": u_cfm_action_profile,
        "u_cfm_maintenance_endpoint": u_cfm_maintenance_endpoint,
        "u_channel_group_interface": u_channel_group_interface,
        "u_class_map": u_class_map,
        "u_classifier": u_classifier,
        "u_community": u_community,
        "u_connect_using_physical_crossconnect": u_connect_using_physical_crossconnect,
        "u_connectors": u_connectors,
        "u_crypto_map": u_crypto_map,
        "u_device_placement": u_device_placement,
        "u_dialer_interface": u_dialer_interface,
        "u_drop_profile": u_drop_profile,
        "u_ethernet_ring": u_ethernet_ring,
        "u_evc_instance": u_evc_instance,
        "u_filter": u_filter,
        "u_forwarding_class": u_forwarding_class,
        "u_group": u_group,
        "u_ic_node_resources_for_end_points": u_ic_node_resources_for_end_points,
        "u_ike_access_profile": u_ike_access_profile,
        "u_ike_policy": u_ike_policy,
        "u_ike_proposal": u_ike_proposal,
        "u_interconnect_node_resources": u_interconnect_node_resources,
        "u_interface_set": u_interface_set,
        "u_ipsec_policy": u_ipsec_policy,
        "u_ipsec_proposal": u_ipsec_proposal,
        "u_ipsec_vpn_rule": u_ipsec_vpn_rule,
        "u_l2_circuit": u_l2_circuit,
        "u_l2_cross_connect": u_l2_cross_connect,
        "u_l2vpn": u_l2vpn,
        "u_lfm_action_profile": u_lfm_action_profile,
        "u_link_aggregation_interface": u_link_aggregation_interface,
        "u_logical_system": u_logical_system,
        "u_loopback_interface": u_loopback_interface,
        "u_managed_devices": u_managed_devices,
        "u_managed_network_elements": u_managed_network_elements,
        "u_management_interface": u_management_interface,
        "u_management_ip_address": u_management_ip_address,
        "u_multicast": u_multicast,
        "u_multilink_interface": u_multilink_interface,
        "u_nat_pool": u_nat_pool,
        "u_nat_rule": u_nat_rule,
        "u_network": u_network,
        "u_ospf_area": u_ospf_area,
        "u_parent_network_element": u_parent_network_element,
        "u_parent_ri_object": u_parent_ri_object,
        "u_physical_crossconnects": u_physical_crossconnects,
        "u_physical_paths": u_physical_paths,
        "u_policer": u_policer,
        "u_policy_map": u_policy_map,
        "u_policy_statement": u_policy_statement,
        "u_real_ne": u_real_ne,
        "u_reference_ip_address": u_reference_ip_address,
        "u_routing_policy": u_routing_policy,
        "u_scheduler": u_scheduler,
        "u_scheduler_map": u_scheduler_map,
        "u_service_set": u_service_set,
        "u_stateful_firewall_rule": u_stateful_firewall_rule,
        "u_static_route": u_static_route,
        "u_tina_rfs_order": u_tina_rfs_order,
        "u_traffic_control_profile": u_traffic_control_profile,
        "u_tunnel_interface": u_tunnel_interface,
        "u_vlan_interface": u_vlan_interface,
        "u_vne": u_vne,
        "u_vrf": u_vrf,
        "u_vsi": u_vsi,
        "u_wip_of": u_wip_of,
        "u_wip_ref": u_wip_ref,
        # custom fields (List)
        "u_related_cfs_instances": u_related_cfs_instances,
        "u_related_cfs_orders": u_related_cfs_orders,
        "u_related_rfs_instances": u_related_rfs_instances,
        "u_related_rfs_orders": u_related_rfs_orders,
        "u_used_by": u_used_by,
    }

    for key, value in field_map.items():
        if value is not None:
            body[key] = value

    # Handle boolean fields
    if monitor is not None:
        body["monitor"] = str(monitor).lower()
    if u_is_preconfigured_object is not None:
        body["u_is_preconfigured_object"] = str(u_is_preconfigured_object).lower()
    if u_wip_object is not None:
        body["u_wip_object"] = str(u_wip_object).lower()

    # Handle integer fields
    if u_backup_server_port is not None:
        body["u_backup_server_port"] = str(u_backup_server_port)
    if u_primary_server_port is not None:
        body["u_primary_server_port"] = str(u_primary_server_port)

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

