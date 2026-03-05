"""
PE Router RFS Instance tools for the ServiceNow MCP server.

This module provides tools for managing PE Router RFS Instance
(u_cmdb_pe_router_rfs_instance) CI records in ServiceNow.
The table extends cmdb_ci via TINA RFS Instance.

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
PE_ROUTER_RFS_INSTANCE_TABLE = "u_cmdb_pe_router_rfs_instance"

# Common fields to retrieve in list/get operations
PE_ROUTER_RFS_INSTANCE_FIELDS = ",".join([
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
    "fault_count",
    "justification",
    "life_cycle_stage",
    "life_cycle_stage_status",
    "sys_class_name",
    "sys_created_on",
    "sys_updated_on",
    "sys_created_by",
    "sys_updated_by",
    # --- custom fields (Reference) ---
    "u_access_port_interface",
    "u_activation_logs",
    "u_activation_process",
    "u_activation_tree",
    "u_bgp_neighbors",
    "u_ce_loopbacks",
    "u_cfs_instance",
    "u_check_script",
    "u_classes_of_service",
    "u_combined_scripts",
    "u_component_instance",
    "u_component_specification",
    "u_cross_connect_egress_port_interface",
    "u_cross_connect_egress_port_subinterface",
    "u_cross_connect_ingress_evc_instance",
    "u_cross_connect_ingress_port_interface",
    "u_cross_connect_ingress_port_subinterface",
    "u_customer_account",
    "u_customer_location_a",
    "u_customer_wan_ipv4_address",
    "u_customer_wan_ipv4_address_gateway",
    "u_customer_wan_ipv6_address",
    "u_dependent_instances",
    "u_e_access_ingress_egress_cross_connect",
    "u_ethernet_link_router_port_interface",
    "u_ethernet_link_switch_port_interface",
    "u_evpl_evc",
    "u_final_scripts",
    "u_first_circuit_aendpoint",
    "u_inner_vlan",
    "u_interface_set",
    "u_internet_gateway_vrf",
    "u_ipsec",
    "u_ipv4_lan_ip_address",
    "u_ipv6_lan_ip_address",
    "u_loopback_ipv4_address",
    "u_loopback_ipv6_address",
    "u_mac_addresses",
    "u_mlppp_bundle_interfaces",
    "u_multicasts",
    "u_nat",
    "u_network_element",
    "u_network_product",
    "u_orders",
    "u_originating_location",
    "u_outer_vlan",
    "u_output_policy",
    "u_outside_service_port_interface",
    "u_outside_service_port_interface_ipv4_address",
    "u_parent_network_element",
    "u_parent_ri_object",
    "u_passive_access_port_interface",
    "u_passive_service_port_interface",
    "u_pre_patching_details",
    "u_previous_snapshot",
    "u_previous_snapshot_version",
    "u_resource_inventory_configuration",
    "u_rfs_instances",
    "u_rfs_specification",
    "u_router_backup_port",
    "u_router_interface_active",
    "u_router_main_port",
    "u_router_slot",
    "u_router_sub_interface",
    "u_search_profile_id",
    "u_service_order_no",
    "u_service_port_interface",
    "u_singtel_virtual_ipv4_address",
    "u_singtel_virtual_ipv4_address_gateway",
    "u_singtel_wan_ipv4_address",
    "u_singtel_wan_ipv4_address_gateway",
    "u_singtel_wan_ipv6_address",
    "u_specification",
    "u_static_lan_ip_address",
    "u_static_routes",
    "u_static_rp",
    "u_tasks",
    "u_terminating_location",
    "u_terminating_pop_location",
    "u_tina_cfs_order",
    "u_tina_rfs_order",
    "u_top_ip_range",
    "u_trunk_port_interface",
    "u_use_ike_proposal",
    "u_use_ipsec_policy",
    "u_vlanid",
    "u_vrfs",
    "u_vsis",
    "u_wip_of",
    "u_wip_ref",
    # --- custom fields (Choice/String) ---
    "u_activation_status",
    "u_circuit_scheme",
    "u_customer_location_b",
    "u_discovery_status",
    "u_display_message",
    "u_externalid",
    "u_flow_status",
    "u_go_to_metamodel",
    "u_last_circuit_zendpoint",
    "u_legend",
    "u_length_of_term",
    "u_naming_trigger",
    "u_new_service_instance_name",
    "u_nni_link_type",
    "u_originating_llc_partner_name",
    "u_originating_llc_partner_reference",
    "u_originating_pegasus_service_number",
    "u_originating_pop_location",
    "u_originating_work_order_number",
    "u_part_of_bundle",
    "u_previous_value_stored",
    "u_product_code",
    "u_project_code",
    "u_record_source",
    "u_router_interface_standby",
    "u_service_number",
    "u_service_type",
    "u_set_value_flow_status",
    "u_snapshot_state",
    "u_status",
    "u_tariff_codes",
    "u_terminating_llc_partner_name",
    "u_terminating_llc_partner_reference",
    "u_terminating_pegasus_np_service_number",
    "u_terminating_work_order_number",
    "u_vpi_vci",
    "u_vrf",
    # --- custom fields (Date) ---
    "u_activated_when",
    "u_construction_completion_date",
    "u_date_service_ordered",
    "u_date_service_provided",
    "u_date_service_requested",
    "u_disconnected_when",
    # --- custom fields (Integer) ---
    "u_downlink_speed_kbps",
    "u_install_charges",
    "u_original",
    "u_uplink_speed_kbps",
    "u_vlan_id",
    # --- custom fields (List) ---
    "u_related_cfs_instances",
    "u_related_cfs_orders",
    "u_related_rfs_instances",
    "u_related_rfs_orders",
    "u_used_by",
    # --- custom fields (Boolean) ---
    "u_is_preconfigured_object",
    "u_wip_object",
])


def _parse_pe_router_rfs_instance(item: dict) -> dict:
    """Parse a raw ServiceNow PE Router RFS Instance record into a clean dictionary."""
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
        "sys_class_name": item.get("sys_class_name"),
        "created_on": item.get("sys_created_on"),
        "updated_on": item.get("sys_updated_on"),
        "created_by": item.get("sys_created_by"),
        "updated_by": item.get("sys_updated_by"),
        # --- custom fields (Reference) ---
        "u_access_port_interface": extract_display_value(item.get("u_access_port_interface")),
        "u_activation_logs": extract_display_value(item.get("u_activation_logs")),
        "u_activation_process": extract_display_value(item.get("u_activation_process")),
        "u_activation_tree": extract_display_value(item.get("u_activation_tree")),
        "u_bgp_neighbors": extract_display_value(item.get("u_bgp_neighbors")),
        "u_ce_loopbacks": extract_display_value(item.get("u_ce_loopbacks")),
        "u_cfs_instance": extract_display_value(item.get("u_cfs_instance")),
        "u_check_script": extract_display_value(item.get("u_check_script")),
        "u_classes_of_service": extract_display_value(item.get("u_classes_of_service")),
        "u_combined_scripts": extract_display_value(item.get("u_combined_scripts")),
        "u_component_instance": extract_display_value(item.get("u_component_instance")),
        "u_component_specification": extract_display_value(item.get("u_component_specification")),
        "u_cross_connect_egress_port_interface": extract_display_value(item.get("u_cross_connect_egress_port_interface")),
        "u_cross_connect_egress_port_subinterface": extract_display_value(item.get("u_cross_connect_egress_port_subinterface")),
        "u_cross_connect_ingress_evc_instance": extract_display_value(item.get("u_cross_connect_ingress_evc_instance")),
        "u_cross_connect_ingress_port_interface": extract_display_value(item.get("u_cross_connect_ingress_port_interface")),
        "u_cross_connect_ingress_port_subinterface": extract_display_value(item.get("u_cross_connect_ingress_port_subinterface")),
        "u_customer_account": extract_display_value(item.get("u_customer_account")),
        "u_customer_location_a": extract_display_value(item.get("u_customer_location_a")),
        "u_customer_wan_ipv4_address": extract_display_value(item.get("u_customer_wan_ipv4_address")),
        "u_customer_wan_ipv4_address_gateway": extract_display_value(item.get("u_customer_wan_ipv4_address_gateway")),
        "u_customer_wan_ipv6_address": extract_display_value(item.get("u_customer_wan_ipv6_address")),
        "u_dependent_instances": extract_display_value(item.get("u_dependent_instances")),
        "u_e_access_ingress_egress_cross_connect": extract_display_value(item.get("u_e_access_ingress_egress_cross_connect")),
        "u_ethernet_link_router_port_interface": extract_display_value(item.get("u_ethernet_link_router_port_interface")),
        "u_ethernet_link_switch_port_interface": extract_display_value(item.get("u_ethernet_link_switch_port_interface")),
        "u_evpl_evc": extract_display_value(item.get("u_evpl_evc")),
        "u_final_scripts": extract_display_value(item.get("u_final_scripts")),
        "u_first_circuit_aendpoint": extract_display_value(item.get("u_first_circuit_aendpoint")),
        "u_inner_vlan": extract_display_value(item.get("u_inner_vlan")),
        "u_interface_set": extract_display_value(item.get("u_interface_set")),
        "u_internet_gateway_vrf": extract_display_value(item.get("u_internet_gateway_vrf")),
        "u_ipsec": extract_display_value(item.get("u_ipsec")),
        "u_ipv4_lan_ip_address": extract_display_value(item.get("u_ipv4_lan_ip_address")),
        "u_ipv6_lan_ip_address": extract_display_value(item.get("u_ipv6_lan_ip_address")),
        "u_loopback_ipv4_address": extract_display_value(item.get("u_loopback_ipv4_address")),
        "u_loopback_ipv6_address": extract_display_value(item.get("u_loopback_ipv6_address")),
        "u_mac_addresses": extract_display_value(item.get("u_mac_addresses")),
        "u_mlppp_bundle_interfaces": extract_display_value(item.get("u_mlppp_bundle_interfaces")),
        "u_multicasts": extract_display_value(item.get("u_multicasts")),
        "u_nat": extract_display_value(item.get("u_nat")),
        "u_network_element": extract_display_value(item.get("u_network_element")),
        "u_network_product": extract_display_value(item.get("u_network_product")),
        "u_orders": extract_display_value(item.get("u_orders")),
        "u_originating_location": extract_display_value(item.get("u_originating_location")),
        "u_outer_vlan": extract_display_value(item.get("u_outer_vlan")),
        "u_output_policy": extract_display_value(item.get("u_output_policy")),
        "u_outside_service_port_interface": extract_display_value(item.get("u_outside_service_port_interface")),
        "u_outside_service_port_interface_ipv4_address": extract_display_value(item.get("u_outside_service_port_interface_ipv4_address")),
        "u_parent_network_element": extract_display_value(item.get("u_parent_network_element")),
        "u_parent_ri_object": extract_display_value(item.get("u_parent_ri_object")),
        "u_passive_access_port_interface": extract_display_value(item.get("u_passive_access_port_interface")),
        "u_passive_service_port_interface": extract_display_value(item.get("u_passive_service_port_interface")),
        "u_pre_patching_details": extract_display_value(item.get("u_pre_patching_details")),
        "u_previous_snapshot": extract_display_value(item.get("u_previous_snapshot")),
        "u_previous_snapshot_version": extract_display_value(item.get("u_previous_snapshot_version")),
        "u_resource_inventory_configuration": extract_display_value(item.get("u_resource_inventory_configuration")),
        "u_rfs_instances": extract_display_value(item.get("u_rfs_instances")),
        "u_rfs_specification": extract_display_value(item.get("u_rfs_specification")),
        "u_router_backup_port": extract_display_value(item.get("u_router_backup_port")),
        "u_router_interface_active": extract_display_value(item.get("u_router_interface_active")),
        "u_router_main_port": extract_display_value(item.get("u_router_main_port")),
        "u_router_slot": extract_display_value(item.get("u_router_slot")),
        "u_router_sub_interface": extract_display_value(item.get("u_router_sub_interface")),
        "u_search_profile_id": extract_display_value(item.get("u_search_profile_id")),
        "u_service_order_no": extract_display_value(item.get("u_service_order_no")),
        "u_service_port_interface": extract_display_value(item.get("u_service_port_interface")),
        "u_singtel_virtual_ipv4_address": extract_display_value(item.get("u_singtel_virtual_ipv4_address")),
        "u_singtel_virtual_ipv4_address_gateway": extract_display_value(item.get("u_singtel_virtual_ipv4_address_gateway")),
        "u_singtel_wan_ipv4_address": extract_display_value(item.get("u_singtel_wan_ipv4_address")),
        "u_singtel_wan_ipv4_address_gateway": extract_display_value(item.get("u_singtel_wan_ipv4_address_gateway")),
        "u_singtel_wan_ipv6_address": extract_display_value(item.get("u_singtel_wan_ipv6_address")),
        "u_specification": extract_display_value(item.get("u_specification")),
        "u_static_lan_ip_address": extract_display_value(item.get("u_static_lan_ip_address")),
        "u_static_routes": extract_display_value(item.get("u_static_routes")),
        "u_static_rp": extract_display_value(item.get("u_static_rp")),
        "u_tasks": extract_display_value(item.get("u_tasks")),
        "u_terminating_location": extract_display_value(item.get("u_terminating_location")),
        "u_terminating_pop_location": extract_display_value(item.get("u_terminating_pop_location")),
        "u_tina_cfs_order": extract_display_value(item.get("u_tina_cfs_order")),
        "u_tina_rfs_order": extract_display_value(item.get("u_tina_rfs_order")),
        "u_top_ip_range": extract_display_value(item.get("u_top_ip_range")),
        "u_trunk_port_interface": extract_display_value(item.get("u_trunk_port_interface")),
        "u_use_ike_proposal": extract_display_value(item.get("u_use_ike_proposal")),
        "u_use_ipsec_policy": extract_display_value(item.get("u_use_ipsec_policy")),
        "u_vlanid": extract_display_value(item.get("u_vlanid")),
        "u_vrfs": extract_display_value(item.get("u_vrfs")),
        "u_vsis": extract_display_value(item.get("u_vsis")),
        "u_wip_of": extract_display_value(item.get("u_wip_of")),
        "u_wip_ref": extract_display_value(item.get("u_wip_ref")),
        # --- custom fields (Choice/String) ---
        "u_activation_status": item.get("u_activation_status"),
        "u_circuit_scheme": item.get("u_circuit_scheme"),
        "u_customer_location_b": item.get("u_customer_location_b"),
        "u_discovery_status": item.get("u_discovery_status"),
        "u_display_message": item.get("u_display_message"),
        "u_externalid": item.get("u_externalid"),
        "u_flow_status": item.get("u_flow_status"),
        "u_go_to_metamodel": item.get("u_go_to_metamodel"),
        "u_last_circuit_zendpoint": item.get("u_last_circuit_zendpoint"),
        "u_legend": item.get("u_legend"),
        "u_length_of_term": item.get("u_length_of_term"),
        "u_naming_trigger": item.get("u_naming_trigger"),
        "u_new_service_instance_name": item.get("u_new_service_instance_name"),
        "u_nni_link_type": item.get("u_nni_link_type"),
        "u_originating_llc_partner_name": item.get("u_originating_llc_partner_name"),
        "u_originating_llc_partner_reference": item.get("u_originating_llc_partner_reference"),
        "u_originating_pegasus_service_number": item.get("u_originating_pegasus_service_number"),
        "u_originating_pop_location": item.get("u_originating_pop_location"),
        "u_originating_work_order_number": item.get("u_originating_work_order_number"),
        "u_part_of_bundle": item.get("u_part_of_bundle"),
        "u_previous_value_stored": item.get("u_previous_value_stored"),
        "u_product_code": item.get("u_product_code"),
        "u_project_code": item.get("u_project_code"),
        "u_record_source": item.get("u_record_source"),
        "u_router_interface_standby": item.get("u_router_interface_standby"),
        "u_service_number": item.get("u_service_number"),
        "u_service_type": item.get("u_service_type"),
        "u_set_value_flow_status": item.get("u_set_value_flow_status"),
        "u_snapshot_state": item.get("u_snapshot_state"),
        "u_status": item.get("u_status"),
        "u_tariff_codes": item.get("u_tariff_codes"),
        "u_terminating_llc_partner_name": item.get("u_terminating_llc_partner_name"),
        "u_terminating_llc_partner_reference": item.get("u_terminating_llc_partner_reference"),
        "u_terminating_pegasus_np_service_number": item.get("u_terminating_pegasus_np_service_number"),
        "u_terminating_work_order_number": item.get("u_terminating_work_order_number"),
        "u_vpi_vci": item.get("u_vpi_vci"),
        "u_vrf": item.get("u_vrf"),
        # --- custom fields (Date) ---
        "u_activated_when": item.get("u_activated_when"),
        "u_construction_completion_date": item.get("u_construction_completion_date"),
        "u_date_service_ordered": item.get("u_date_service_ordered"),
        "u_date_service_provided": item.get("u_date_service_provided"),
        "u_date_service_requested": item.get("u_date_service_requested"),
        "u_disconnected_when": item.get("u_disconnected_when"),
        # --- custom fields (Integer) ---
        "u_downlink_speed_kbps": item.get("u_downlink_speed_kbps"),
        "u_install_charges": item.get("u_install_charges"),
        "u_original": item.get("u_original"),
        "u_uplink_speed_kbps": item.get("u_uplink_speed_kbps"),
        "u_vlan_id": item.get("u_vlan_id"),
        # --- custom fields (List) ---
        "u_related_cfs_instances": item.get("u_related_cfs_instances"),
        "u_related_cfs_orders": item.get("u_related_cfs_orders"),
        "u_related_rfs_instances": item.get("u_related_rfs_instances"),
        "u_related_rfs_orders": item.get("u_related_rfs_orders"),
        "u_used_by": item.get("u_used_by"),
        # --- custom fields (Boolean) ---
        "u_is_preconfigured_object": item.get("u_is_preconfigured_object"),
        "u_wip_object": item.get("u_wip_object"),
    }


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
@mcp.tool()
def list_pe_router_rfs_instances(
    limit: int = Field(10, description="Maximum number of PE Router RFS Instances to return"),
    offset: int = Field(0, description="Offset for pagination"),
    name: Optional[str] = Field(None, description="Filter by name (contains)"),
    u_service_number: Optional[str] = Field(None, description="Filter by Service Number"),
    u_status: Optional[str] = Field(None, description="Filter by Status"),
    u_activation_status: Optional[str] = Field(None, description="Filter by Activation Status"),
    u_flow_status: Optional[str] = Field(None, description="Filter by Flow Status"),
    u_service_type: Optional[str] = Field(None, description="Filter by Service Type"),
    u_network_element: Optional[str] = Field(None, description="Filter by Network Element (sys_id or display value)"),
    u_circuit_scheme: Optional[str] = Field(None, description="Filter by Circuit Scheme"),
    u_nni_link_type: Optional[str] = Field(None, description="Filter by NNI Link Type"),
    install_status: Optional[str] = Field(None, description="Filter by install status (e.g. 1=Installed)"),
    operational_status: Optional[str] = Field(None, description="Filter by operational status"),
    query: Optional[str] = Field(None, description="Encoded query string for advanced filtering"),
) -> str:
    """List PE Router RFS Instance CI records from ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    try:
        url = f"{config.api_url}/table/{PE_ROUTER_RFS_INSTANCE_TABLE}"

        query_params = {
            "sysparm_limit": str(limit),
            "sysparm_offset": str(offset),
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
            "sysparm_fields": PE_ROUTER_RFS_INSTANCE_FIELDS,
        }

        query_parts: list[str] = []
        if name:
            query_parts.append(f"nameLIKE{name}")
        if u_service_number:
            query_parts.append(f"u_service_number={u_service_number}")
        if u_status:
            query_parts.append(f"u_status={u_status}")
        if u_activation_status:
            query_parts.append(f"u_activation_status={u_activation_status}")
        if u_flow_status:
            query_parts.append(f"u_flow_status={u_flow_status}")
        if u_service_type:
            query_parts.append(f"u_service_type={u_service_type}")
        if u_network_element:
            query_parts.append(f"u_network_element={u_network_element}")
        if u_circuit_scheme:
            query_parts.append(f"u_circuit_scheme={u_circuit_scheme}")
        if u_nni_link_type:
            query_parts.append(f"u_nni_link_type={u_nni_link_type}")
        if install_status:
            query_parts.append(f"install_status={install_status}")
        if operational_status:
            query_parts.append(f"operational_status={operational_status}")
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
        instances = [_parse_pe_router_rfs_instance(item) for item in data.get("result", [])]

        return format_list_response(instances, "pe_router_rfs_instances", limit, offset)

    except Exception as e:
        logger.error(f"Error listing PE Router RFS Instances: {e}")
        return format_error_response("list PE Router RFS Instances", e)


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------
@mcp.tool()
def get_pe_router_rfs_instance(
    instance_id: str = Field(
        ..., description="PE Router RFS Instance sys_id or name"
    ),
) -> str:
    """Get a specific PE Router RFS Instance CI record from ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    try:
        query_params = {
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
            "sysparm_fields": PE_ROUTER_RFS_INSTANCE_FIELDS,
        }

        if is_sys_id(instance_id):
            url = f"{config.api_url}/table/{PE_ROUTER_RFS_INSTANCE_TABLE}/{instance_id}"
        else:
            url = f"{config.api_url}/table/{PE_ROUTER_RFS_INSTANCE_TABLE}"
            query_params["sysparm_query"] = f"name={instance_id}"
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
            return f"PE Router RFS Instance not found: {instance_id}"

        result = data["result"]
        if isinstance(result, list):
            if not result:
                return f"PE Router RFS Instance not found: {instance_id}"
            item = result[0]
        else:
            item = result

        instance = _parse_pe_router_rfs_instance(item)

        return format_success_response(
            f"Found PE Router RFS Instance: {item.get('name')}",
            pe_router_rfs_instance=instance,
        )

    except Exception as e:
        logger.error(f"Error getting PE Router RFS Instance: {e}")
        return format_error_response("get PE Router RFS Instance", e)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
@mcp.tool()
def update_pe_router_rfs_instance(
    instance_id: str = Field(..., description="PE Router RFS Instance sys_id or name"),
    # --- inherited cmdb_ci fields ---
    name: Optional[str] = Field(None, description="Name"),
    short_description: Optional[str] = Field(None, description="Short description"),
    comments: Optional[str] = Field(None, description="Additional comments"),
    category: Optional[str] = Field(None, description="Category"),
    subcategory: Optional[str] = Field(None, description="Subcategory"),
    ip_address: Optional[str] = Field(None, description="IP address"),
    assigned_to: Optional[str] = Field(None, description="Assigned to (user sys_id or display value)"),
    assignment_group: Optional[str] = Field(None, description="Change/assignment group (sys_id or display value)"),
    install_status: Optional[str] = Field(None, description="Install status"),
    operational_status: Optional[str] = Field(None, description="Operational status"),
    environment: Optional[str] = Field(None, description="Environment"),
    company: Optional[str] = Field(None, description="Company (sys_id or display value)"),
    location: Optional[str] = Field(None, description="Location (sys_id or display value)"),
    discovery_source: Optional[str] = Field(None, description="Discovery source"),
    justification: Optional[str] = Field(None, description="Justification"),
    # --- custom fields (Choice/String) ---
    u_activation_status: Optional[str] = Field(None, description="Activation Status"),
    u_circuit_scheme: Optional[str] = Field(None, description="Circuit Scheme"),
    u_customer_location_b: Optional[str] = Field(None, description="Customer Location B"),
    u_discovery_status: Optional[str] = Field(None, description="Discovery Status"),
    u_display_message: Optional[str] = Field(None, description="Display Message"),
    u_externalid: Optional[str] = Field(None, description="ExternalID"),
    u_flow_status: Optional[str] = Field(None, description="Flow Status"),
    u_go_to_metamodel: Optional[str] = Field(None, description="Go To MetaModel"),
    u_last_circuit_zendpoint: Optional[str] = Field(None, description="Last circuit ZEndPoint"),
    u_legend: Optional[str] = Field(None, description="Legend"),
    u_length_of_term: Optional[str] = Field(None, description="Length Of Term"),
    u_naming_trigger: Optional[str] = Field(None, description="Naming trigger"),
    u_new_service_instance_name: Optional[str] = Field(None, description="New service instance name"),
    u_nni_link_type: Optional[str] = Field(None, description="NNI Link Type"),
    u_originating_llc_partner_name: Optional[str] = Field(None, description="Originating LLC Partner Name"),
    u_originating_llc_partner_reference: Optional[str] = Field(None, description="Originating LLC Partner Reference"),
    u_originating_pegasus_service_number: Optional[str] = Field(None, description="Originating Pegasus Service Number"),
    u_originating_pop_location: Optional[str] = Field(None, description="Originating POP Location"),
    u_originating_work_order_number: Optional[str] = Field(None, description="Originating Work Order Number"),
    u_part_of_bundle: Optional[str] = Field(None, description="Part of Bundle"),
    u_previous_value_stored: Optional[str] = Field(None, description="Previous Value Stored"),
    u_product_code: Optional[str] = Field(None, description="Product Code"),
    u_project_code: Optional[str] = Field(None, description="Project Code"),
    u_record_source: Optional[str] = Field(None, description="Record Source"),
    u_router_interface_standby: Optional[str] = Field(None, description="Router Interface (Standby)"),
    u_service_number: Optional[str] = Field(None, description="Service Number"),
    u_service_type: Optional[str] = Field(None, description="Service Type"),
    u_set_value_flow_status: Optional[str] = Field(None, description="Set value flow status"),
    u_snapshot_state: Optional[str] = Field(None, description="Snapshot State"),
    u_status: Optional[str] = Field(None, description="Status"),
    u_tariff_codes: Optional[str] = Field(None, description="Tariff Codes"),
    u_terminating_llc_partner_name: Optional[str] = Field(None, description="Terminating LLC Partner Name"),
    u_terminating_llc_partner_reference: Optional[str] = Field(None, description="Terminating LLC Partner reference"),
    u_terminating_pegasus_np_service_number: Optional[str] = Field(None, description="Terminating Pegasus NP Service Number"),
    u_terminating_work_order_number: Optional[str] = Field(None, description="Terminating Work Order Number"),
    u_vpi_vci: Optional[str] = Field(None, description="VPI/VCI"),
    u_vrf: Optional[str] = Field(None, description="VRF"),
    # --- custom fields (Reference) ---
    u_access_port_interface: Optional[str] = Field(None, description="Access Port Interface (sys_id or display value)"),
    u_activation_logs: Optional[str] = Field(None, description="Activation Logs (sys_id or display value)"),
    u_activation_process: Optional[str] = Field(None, description="Activation Process (sys_id or display value)"),
    u_activation_tree: Optional[str] = Field(None, description="Activation Tree (sys_id or display value)"),
    u_bgp_neighbors: Optional[str] = Field(None, description="BGP Neighbors (sys_id or display value)"),
    u_ce_loopbacks: Optional[str] = Field(None, description="CE Loopbacks (sys_id or display value)"),
    u_cfs_instance: Optional[str] = Field(None, description="CFS Instance (sys_id or display value)"),
    u_check_script: Optional[str] = Field(None, description="Check Script (sys_id or display value)"),
    u_classes_of_service: Optional[str] = Field(None, description="Classes Of Service (sys_id or display value)"),
    u_combined_scripts: Optional[str] = Field(None, description="Combined Scripts (sys_id or display value)"),
    u_component_instance: Optional[str] = Field(None, description="Component Instance (sys_id or display value)"),
    u_component_specification: Optional[str] = Field(None, description="Component Specification (sys_id or display value)"),
    u_cross_connect_egress_port_interface: Optional[str] = Field(None, description="Cross-Connect Egress Port Interface (sys_id or display value)"),
    u_cross_connect_egress_port_subinterface: Optional[str] = Field(None, description="Cross-Connect Egress Port SubInterface (sys_id or display value)"),
    u_cross_connect_ingress_evc_instance: Optional[str] = Field(None, description="Cross-Connect Ingress EVC Instance (sys_id or display value)"),
    u_cross_connect_ingress_port_interface: Optional[str] = Field(None, description="Cross-Connect Ingress Port Interface (sys_id or display value)"),
    u_cross_connect_ingress_port_subinterface: Optional[str] = Field(None, description="Cross-Connect Ingress Port SubInterface (sys_id or display value)"),
    u_customer_account: Optional[str] = Field(None, description="Customer Account (sys_id or display value)"),
    u_customer_location_a: Optional[str] = Field(None, description="Customer Location A (sys_id or display value)"),
    u_customer_wan_ipv4_address: Optional[str] = Field(None, description="Customer WAN IPv4 Address (sys_id or display value)"),
    u_customer_wan_ipv4_address_gateway: Optional[str] = Field(None, description="Customer WAN IPv4 Address Gateway (sys_id or display value)"),
    u_customer_wan_ipv6_address: Optional[str] = Field(None, description="Customer WAN IPv6 Address (sys_id or display value)"),
    u_dependent_instances: Optional[str] = Field(None, description="Dependent Instances (sys_id or display value)"),
    u_e_access_ingress_egress_cross_connect: Optional[str] = Field(None, description="E-Access Ingress - Egress Cross-connect (sys_id or display value)"),
    u_ethernet_link_router_port_interface: Optional[str] = Field(None, description="Ethernet Link Router Port Interface (sys_id or display value)"),
    u_ethernet_link_switch_port_interface: Optional[str] = Field(None, description="Ethernet Link Switch Port Interface (sys_id or display value)"),
    u_evpl_evc: Optional[str] = Field(None, description="EVPL EVC (sys_id or display value)"),
    u_final_scripts: Optional[str] = Field(None, description="Final Scripts (sys_id or display value)"),
    u_first_circuit_aendpoint: Optional[str] = Field(None, description="First circuit AEndPoint (sys_id or display value)"),
    u_inner_vlan: Optional[str] = Field(None, description="Inner VLAN (sys_id or display value)"),
    u_interface_set: Optional[str] = Field(None, description="Interface Set (sys_id or display value)"),
    u_internet_gateway_vrf: Optional[str] = Field(None, description="Internet Gateway VRF (sys_id or display value)"),
    u_ipsec: Optional[str] = Field(None, description="IPSec (sys_id or display value)"),
    u_ipv4_lan_ip_address: Optional[str] = Field(None, description="IPv4 LAN IP Address (sys_id or display value)"),
    u_ipv6_lan_ip_address: Optional[str] = Field(None, description="IPv6 LAN IP Address (sys_id or display value)"),
    u_loopback_ipv4_address: Optional[str] = Field(None, description="Loopback IPv4 Address (sys_id or display value)"),
    u_loopback_ipv6_address: Optional[str] = Field(None, description="Loopback IPv6 Address (sys_id or display value)"),
    u_mac_addresses: Optional[str] = Field(None, description="MAC Addresses (sys_id or display value)"),
    u_mlppp_bundle_interfaces: Optional[str] = Field(None, description="MLPPP Bundle Interfaces (sys_id or display value)"),
    u_multicasts: Optional[str] = Field(None, description="Multicasts (sys_id or display value)"),
    u_nat: Optional[str] = Field(None, description="NAT (sys_id or display value)"),
    u_network_element: Optional[str] = Field(None, description="Network Element (sys_id or display value)"),
    u_network_product: Optional[str] = Field(None, description="Network Product (sys_id or display value)"),
    u_orders: Optional[str] = Field(None, description="Orders (sys_id or display value)"),
    u_originating_location: Optional[str] = Field(None, description="Originating Location (sys_id or display value)"),
    u_outer_vlan: Optional[str] = Field(None, description="Outer VLAN (sys_id or display value)"),
    u_output_policy: Optional[str] = Field(None, description="Output Policy (sys_id or display value)"),
    u_outside_service_port_interface: Optional[str] = Field(None, description="Outside Service Port Interface (sys_id or display value)"),
    u_outside_service_port_interface_ipv4_address: Optional[str] = Field(None, description="Outside Service Port Interface IPv4 Address (sys_id or display value)"),
    u_parent_network_element: Optional[str] = Field(None, description="Parent Network Element (sys_id or display value)"),
    u_parent_ri_object: Optional[str] = Field(None, description="Parent RI Object (sys_id or display value)"),
    u_passive_access_port_interface: Optional[str] = Field(None, description="Passive Access Port Interface (sys_id or display value)"),
    u_passive_service_port_interface: Optional[str] = Field(None, description="Passive Service Port Interface (sys_id or display value)"),
    u_pre_patching_details: Optional[str] = Field(None, description="Pre-patching details (sys_id or display value)"),
    u_previous_snapshot: Optional[str] = Field(None, description="Previous Snapshot (sys_id or display value)"),
    u_previous_snapshot_version: Optional[str] = Field(None, description="Previous Snapshot Version (sys_id or display value)"),
    u_resource_inventory_configuration: Optional[str] = Field(None, description="Resource Inventory Configuration (sys_id or display value)"),
    u_rfs_instances: Optional[str] = Field(None, description="RFS Instances (sys_id or display value)"),
    u_rfs_specification: Optional[str] = Field(None, description="RFS Specification (sys_id or display value)"),
    u_router_backup_port: Optional[str] = Field(None, description="Router Backup Port (sys_id or display value)"),
    u_router_interface_active: Optional[str] = Field(None, description="Router Interface Active (sys_id or display value)"),
    u_router_main_port: Optional[str] = Field(None, description="Router Main Port (sys_id or display value)"),
    u_router_slot: Optional[str] = Field(None, description="Router Slot (sys_id or display value)"),
    u_router_sub_interface: Optional[str] = Field(None, description="Router Sub Interface (sys_id or display value)"),
    u_search_profile_id: Optional[str] = Field(None, description="Search Profile ID (sys_id or display value)"),
    u_service_order_no: Optional[str] = Field(None, description="Service Order No (sys_id or display value)"),
    u_service_port_interface: Optional[str] = Field(None, description="Service Port Interface (sys_id or display value)"),
    u_singtel_virtual_ipv4_address: Optional[str] = Field(None, description="SingTel Virtual IPv4 Address (sys_id or display value)"),
    u_singtel_virtual_ipv4_address_gateway: Optional[str] = Field(None, description="SingTel Virtual IPv4 Address Gateway (sys_id or display value)"),
    u_singtel_wan_ipv4_address: Optional[str] = Field(None, description="SingTel WAN IPv4 Address (sys_id or display value)"),
    u_singtel_wan_ipv4_address_gateway: Optional[str] = Field(None, description="SingTel WAN IPv4 Address Gateway (sys_id or display value)"),
    u_singtel_wan_ipv6_address: Optional[str] = Field(None, description="SingTel WAN IPv6 Address (sys_id or display value)"),
    u_specification: Optional[str] = Field(None, description="CFS Specification (sys_id or display value)"),
    u_static_lan_ip_address: Optional[str] = Field(None, description="Static LAN IP Address (sys_id or display value)"),
    u_static_routes: Optional[str] = Field(None, description="Static Routes (sys_id or display value)"),
    u_static_rp: Optional[str] = Field(None, description="Static RP (sys_id or display value)"),
    u_tasks: Optional[str] = Field(None, description="Tasks (sys_id or display value)"),
    u_terminating_location: Optional[str] = Field(None, description="Terminating Location (sys_id or display value)"),
    u_terminating_pop_location: Optional[str] = Field(None, description="Terminating POP Location (sys_id or display value)"),
    u_tina_cfs_order: Optional[str] = Field(None, description="TINA CFS Order (sys_id or display value)"),
    u_tina_rfs_order: Optional[str] = Field(None, description="TINA RFS Order (sys_id or display value)"),
    u_top_ip_range: Optional[str] = Field(None, description="Top IP Range (sys_id or display value)"),
    u_trunk_port_interface: Optional[str] = Field(None, description="Trunk Port Interface (sys_id or display value)"),
    u_use_ike_proposal: Optional[str] = Field(None, description="Use IKE Proposal (sys_id or display value)"),
    u_use_ipsec_policy: Optional[str] = Field(None, description="Use IPSEC Policy (sys_id or display value)"),
    u_vlanid: Optional[str] = Field(None, description="VLAN ID (sys_id or display value)"),
    u_vrfs: Optional[str] = Field(None, description="VRFs (sys_id or display value)"),
    u_vsis: Optional[str] = Field(None, description="VSIs (sys_id or display value)"),
    u_wip_of: Optional[str] = Field(None, description="WIP Of (sys_id or display value)"),
    u_wip_ref: Optional[str] = Field(None, description="WIP Ref (sys_id or display value)"),
    # --- custom fields (Date) ---
    u_activated_when: Optional[str] = Field(None, description="Activated When (date, YYYY-MM-DD)"),
    u_construction_completion_date: Optional[str] = Field(None, description="Construction Completion Date (YYYY-MM-DD)"),
    u_date_service_ordered: Optional[str] = Field(None, description="Date service ordered (YYYY-MM-DD)"),
    u_date_service_provided: Optional[str] = Field(None, description="Date service provided (YYYY-MM-DD)"),
    u_date_service_requested: Optional[str] = Field(None, description="Date service requested (YYYY-MM-DD)"),
    u_disconnected_when: Optional[str] = Field(None, description="Disconnected When (YYYY-MM-DD)"),
    # --- custom fields (List) ---
    u_related_cfs_instances: Optional[str] = Field(None, description="Related CFS Instances (comma-separated sys_ids)"),
    u_related_cfs_orders: Optional[str] = Field(None, description="Related CFS Orders (comma-separated sys_ids)"),
    u_related_rfs_instances: Optional[str] = Field(None, description="Related RFS Instances (comma-separated sys_ids)"),
    u_related_rfs_orders: Optional[str] = Field(None, description="Related RFS Orders (comma-separated sys_ids)"),
    u_used_by: Optional[str] = Field(None, description="Used By (comma-separated sys_ids)"),
    # --- custom fields (Integer) ---
    u_downlink_speed_kbps: Optional[int] = Field(None, description="Downlink Speed (kbps)"),
    u_install_charges: Optional[int] = Field(None, description="Install Charges, $"),
    u_original: Optional[int] = Field(None, description="Original"),
    u_uplink_speed_kbps: Optional[int] = Field(None, description="Uplink Speed (kbps)"),
    u_vlan_id: Optional[int] = Field(None, description="VLAN_ID (Do not use)"),
    # --- custom fields (Boolean) ---
    u_is_preconfigured_object: Optional[bool] = Field(None, description="Is PreConfigured Object?"),
    u_wip_object: Optional[bool] = Field(None, description="WIP Object"),
) -> str:
    """Update an existing PE Router RFS Instance CI record in ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    # Resolve to sys_id if a name was provided
    sys_id_to_update = instance_id
    if not is_sys_id(instance_id):
        search_url = f"{config.api_url}/table/{PE_ROUTER_RFS_INSTANCE_TABLE}"
        search_params = {
            "sysparm_query": f"name={instance_id}",
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
                return f"PE Router RFS Instance not found: {instance_id}"
            sys_id_to_update = s_res[0]["sys_id"]
        except Exception as e:
            return f"Error resolving PE Router RFS Instance ID: {str(e)}"

    url = f"{config.api_url}/table/{PE_ROUTER_RFS_INSTANCE_TABLE}/{sys_id_to_update}"

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
        "assigned_to": assigned_to,
        "assignment_group": assignment_group,
        "install_status": install_status,
        "operational_status": operational_status,
        "environment": environment,
        "company": company,
        "location": location,
        "discovery_source": discovery_source,
        "justification": justification,
        # custom fields (Choice/String)
        "u_activation_status": u_activation_status,
        "u_circuit_scheme": u_circuit_scheme,
        "u_customer_location_b": u_customer_location_b,
        "u_discovery_status": u_discovery_status,
        "u_display_message": u_display_message,
        "u_externalid": u_externalid,
        "u_flow_status": u_flow_status,
        "u_go_to_metamodel": u_go_to_metamodel,
        "u_last_circuit_zendpoint": u_last_circuit_zendpoint,
        "u_legend": u_legend,
        "u_length_of_term": u_length_of_term,
        "u_naming_trigger": u_naming_trigger,
        "u_new_service_instance_name": u_new_service_instance_name,
        "u_nni_link_type": u_nni_link_type,
        "u_originating_llc_partner_name": u_originating_llc_partner_name,
        "u_originating_llc_partner_reference": u_originating_llc_partner_reference,
        "u_originating_pegasus_service_number": u_originating_pegasus_service_number,
        "u_originating_pop_location": u_originating_pop_location,
        "u_originating_work_order_number": u_originating_work_order_number,
        "u_part_of_bundle": u_part_of_bundle,
        "u_previous_value_stored": u_previous_value_stored,
        "u_product_code": u_product_code,
        "u_project_code": u_project_code,
        "u_record_source": u_record_source,
        "u_router_interface_standby": u_router_interface_standby,
        "u_service_number": u_service_number,
        "u_service_type": u_service_type,
        "u_set_value_flow_status": u_set_value_flow_status,
        "u_snapshot_state": u_snapshot_state,
        "u_status": u_status,
        "u_tariff_codes": u_tariff_codes,
        "u_terminating_llc_partner_name": u_terminating_llc_partner_name,
        "u_terminating_llc_partner_reference": u_terminating_llc_partner_reference,
        "u_terminating_pegasus_np_service_number": u_terminating_pegasus_np_service_number,
        "u_terminating_work_order_number": u_terminating_work_order_number,
        "u_vpi_vci": u_vpi_vci,
        "u_vrf": u_vrf,
        # custom fields (Reference)
        "u_access_port_interface": u_access_port_interface,
        "u_activation_logs": u_activation_logs,
        "u_activation_process": u_activation_process,
        "u_activation_tree": u_activation_tree,
        "u_bgp_neighbors": u_bgp_neighbors,
        "u_ce_loopbacks": u_ce_loopbacks,
        "u_cfs_instance": u_cfs_instance,
        "u_check_script": u_check_script,
        "u_classes_of_service": u_classes_of_service,
        "u_combined_scripts": u_combined_scripts,
        "u_component_instance": u_component_instance,
        "u_component_specification": u_component_specification,
        "u_cross_connect_egress_port_interface": u_cross_connect_egress_port_interface,
        "u_cross_connect_egress_port_subinterface": u_cross_connect_egress_port_subinterface,
        "u_cross_connect_ingress_evc_instance": u_cross_connect_ingress_evc_instance,
        "u_cross_connect_ingress_port_interface": u_cross_connect_ingress_port_interface,
        "u_cross_connect_ingress_port_subinterface": u_cross_connect_ingress_port_subinterface,
        "u_customer_account": u_customer_account,
        "u_customer_location_a": u_customer_location_a,
        "u_customer_wan_ipv4_address": u_customer_wan_ipv4_address,
        "u_customer_wan_ipv4_address_gateway": u_customer_wan_ipv4_address_gateway,
        "u_customer_wan_ipv6_address": u_customer_wan_ipv6_address,
        "u_dependent_instances": u_dependent_instances,
        "u_e_access_ingress_egress_cross_connect": u_e_access_ingress_egress_cross_connect,
        "u_ethernet_link_router_port_interface": u_ethernet_link_router_port_interface,
        "u_ethernet_link_switch_port_interface": u_ethernet_link_switch_port_interface,
        "u_evpl_evc": u_evpl_evc,
        "u_final_scripts": u_final_scripts,
        "u_first_circuit_aendpoint": u_first_circuit_aendpoint,
        "u_inner_vlan": u_inner_vlan,
        "u_interface_set": u_interface_set,
        "u_internet_gateway_vrf": u_internet_gateway_vrf,
        "u_ipsec": u_ipsec,
        "u_ipv4_lan_ip_address": u_ipv4_lan_ip_address,
        "u_ipv6_lan_ip_address": u_ipv6_lan_ip_address,
        "u_loopback_ipv4_address": u_loopback_ipv4_address,
        "u_loopback_ipv6_address": u_loopback_ipv6_address,
        "u_mac_addresses": u_mac_addresses,
        "u_mlppp_bundle_interfaces": u_mlppp_bundle_interfaces,
        "u_multicasts": u_multicasts,
        "u_nat": u_nat,
        "u_network_element": u_network_element,
        "u_network_product": u_network_product,
        "u_orders": u_orders,
        "u_originating_location": u_originating_location,
        "u_outer_vlan": u_outer_vlan,
        "u_output_policy": u_output_policy,
        "u_outside_service_port_interface": u_outside_service_port_interface,
        "u_outside_service_port_interface_ipv4_address": u_outside_service_port_interface_ipv4_address,
        "u_parent_network_element": u_parent_network_element,
        "u_parent_ri_object": u_parent_ri_object,
        "u_passive_access_port_interface": u_passive_access_port_interface,
        "u_passive_service_port_interface": u_passive_service_port_interface,
        "u_pre_patching_details": u_pre_patching_details,
        "u_previous_snapshot": u_previous_snapshot,
        "u_previous_snapshot_version": u_previous_snapshot_version,
        "u_resource_inventory_configuration": u_resource_inventory_configuration,
        "u_rfs_instances": u_rfs_instances,
        "u_rfs_specification": u_rfs_specification,
        "u_router_backup_port": u_router_backup_port,
        "u_router_interface_active": u_router_interface_active,
        "u_router_main_port": u_router_main_port,
        "u_router_slot": u_router_slot,
        "u_router_sub_interface": u_router_sub_interface,
        "u_search_profile_id": u_search_profile_id,
        "u_service_order_no": u_service_order_no,
        "u_service_port_interface": u_service_port_interface,
        "u_singtel_virtual_ipv4_address": u_singtel_virtual_ipv4_address,
        "u_singtel_virtual_ipv4_address_gateway": u_singtel_virtual_ipv4_address_gateway,
        "u_singtel_wan_ipv4_address": u_singtel_wan_ipv4_address,
        "u_singtel_wan_ipv4_address_gateway": u_singtel_wan_ipv4_address_gateway,
        "u_singtel_wan_ipv6_address": u_singtel_wan_ipv6_address,
        "u_specification": u_specification,
        "u_static_lan_ip_address": u_static_lan_ip_address,
        "u_static_routes": u_static_routes,
        "u_static_rp": u_static_rp,
        "u_tasks": u_tasks,
        "u_terminating_location": u_terminating_location,
        "u_terminating_pop_location": u_terminating_pop_location,
        "u_tina_cfs_order": u_tina_cfs_order,
        "u_tina_rfs_order": u_tina_rfs_order,
        "u_top_ip_range": u_top_ip_range,
        "u_trunk_port_interface": u_trunk_port_interface,
        "u_use_ike_proposal": u_use_ike_proposal,
        "u_use_ipsec_policy": u_use_ipsec_policy,
        "u_vlanid": u_vlanid,
        "u_vrfs": u_vrfs,
        "u_vsis": u_vsis,
        "u_wip_of": u_wip_of,
        "u_wip_ref": u_wip_ref,
        # custom fields (Date)
        "u_activated_when": u_activated_when,
        "u_construction_completion_date": u_construction_completion_date,
        "u_date_service_ordered": u_date_service_ordered,
        "u_date_service_provided": u_date_service_provided,
        "u_date_service_requested": u_date_service_requested,
        "u_disconnected_when": u_disconnected_when,
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
    if u_is_preconfigured_object is not None:
        body["u_is_preconfigured_object"] = str(u_is_preconfigured_object).lower()
    if u_wip_object is not None:
        body["u_wip_object"] = str(u_wip_object).lower()

    # Handle integer fields
    if u_downlink_speed_kbps is not None:
        body["u_downlink_speed_kbps"] = str(u_downlink_speed_kbps)
    if u_install_charges is not None:
        body["u_install_charges"] = str(u_install_charges)
    if u_original is not None:
        body["u_original"] = str(u_original)
    if u_uplink_speed_kbps is not None:
        body["u_uplink_speed_kbps"] = str(u_uplink_speed_kbps)
    if u_vlan_id is not None:
        body["u_vlan_id"] = str(u_vlan_id)

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
            return "Failed to update PE Router RFS Instance"

        result = data["result"]
        return format_success_response(
            f"PE Router RFS Instance updated successfully: {result.get('name')}",
            sys_id=result.get("sys_id"),
            name=result.get("name"),
        )

    except Exception as e:
        logger.error(f"Error updating PE Router RFS Instance: {e}")
        return format_error_response("update PE Router RFS Instance", e)
