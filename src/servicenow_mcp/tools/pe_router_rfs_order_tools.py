"""
PE Router RFS Order tools for the ServiceNow MCP server.

This module provides tools for managing PE Router RFS Order
(u_task_pe_router_rfs_order) records in ServiceNow.
The table extends task via TINA RFS Order.

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
PE_ROUTER_RFS_ORDER_TABLE = "u_task_pe_router_rfs_order"

# Common fields to retrieve in list/get operations
PE_ROUTER_RFS_ORDER_FIELDS = ",".join([
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
    # --- custom fields (Reference) ---
    "u_access_port_interface",
    "u_access_port_interface_planning",
    "u_activation_logs",
    "u_activation_tree",
    "u_activation_trees",
    "u_auto_assignment_log",
    "u_bgp_neighbors",
    "u_ce_loopbacks",
    "u_check_script",
    "u_check_script_tab",
    "u_classes_of_service",
    "u_combined_scripts",
    "u_configuration_checks",
    "u_copy",
    "u_cos_component",
    "u_cross_connect_egress_port_interface",
    "u_cross_connect_egress_port_interface_wip",
    "u_cross_connect_egress_port_subinterface",
    "u_cross_connect_egress_port_subinterface_planning",
    "u_cross_connect_ingress_evc_instance",
    "u_cross_connect_ingress_evc_instance_planning",
    "u_cross_connect_ingress_port_interface",
    "u_cross_connect_ingress_port_interface_wip",
    "u_cross_connect_ingress_port_subinterface",
    "u_cross_connect_ingress_port_subinterfaceplanning",
    "u_customer_wan_ipv4_address",
    "u_customer_wan_ipv4_address_gateway",
    "u_customer_wan_ipv6_address",
    "u_customized_scripts",
    "u_customized_tree",
    "u_deactivation_logs",
    "u_dectivation_tree",
    "u_e_access_ingress_egress_cross_connect",
    "u_e_access_ingress_egress_cross_connect_planning",
    "u_evpl_evc",
    "u_evpl_evc_planning",
    "u_final_scripts",
    "u_inner_vlan",
    "u_interface_set",
    "u_internet_gateway_vrf",
    "u_ipsec",
    "u_ipv4_lan_ip_address",
    "u_ipv6_lan_ip_address",
    "u_load_balance_deactivation_scripts",
    "u_load_balance_dectivation_tree",
    "u_load_balance_scripts",
    "u_load_balance_tree",
    "u_load_balances",
    "u_logical_system",
    "u_loopback_ipv4_address",
    "u_loopback_ipv6_address",
    "u_mlppp_bundle_interfaces",
    "u_multicasts",
    "u_nat",
    "u_nat_pool_ip_address",
    "u_nat_recource_component",
    "u_network_element",
    "u_outer_vlan",
    "u_output_policy",
    "u_outside_service_port_interface",
    "u_outside_service_port_interface_ipv4_address",
    "u_outside_service_port_interface_planning",
    "u_passive_access_port_interface",
    "u_passive_access_port_interface_planning",
    "u_passive_service_port_interface",
    "u_passive_service_port_interface_planning",
    "u_pre_patching_details",
    "u_records_checks",
    "u_resource_inventory_configuration",
    "u_rollback_script",
    "u_router_backup_port",
    "u_router_interface_active",
    "u_router_main_port",
    "u_router_slot",
    "u_router_sub_interface",
    "u_running_configuration",
    "u_search_profile_id",
    "u_service_port_interface",
    "u_service_port_interface_planning",
    "u_singtel_virtual_ipv4_address",
    "u_singtel_virtual_ipv4_address_gateway",
    "u_singtel_virtual_ipv6_address",
    "u_singtel_wan_ipv4_address",
    "u_singtel_wan_ipv4_address_gateway",
    "u_singtel_wan_ipv6_address",
    "u_static_lan_ip_address",
    "u_static_routes",
    "u_static_rp",
    "u_top_ip_range",
    "u_trunk_port_interface",
    "u_trunkportserviceattr",
    "u_use_ike_proposal",
    "u_use_ipsec_policy",
    "u_vlan_id",
    "u_vrfs",
    "u_vsis",
    # --- custom fields (Choice) ---
    "u_as_number_uniqueness_for_customer_check",
    "u_cease_and_provide",
    "u_class_of_service_check",
    "u_configure_main_interface",
    "u_customer_port_ip_check",
    "u_duplicate_lan_ip_address_static_in_vrf_check",
    "u_duplicate_wan_ip_address_check",
    "u_evcid_uniqueness_in_evc_check",
    "u_interface_clean_check",
    "u_is_access_switch_rfs_needed",
    "u_load_balancing_source_role",
    "u_nni_link_type",
    "u_nni_port_type_check",
    "u_port_interface_details_check",
    "u_port_speed_downstream_upstream_check",
    "u_pre_check_result",
    "u_routing_protocol_cust_nni_max_prefix_check",
    "u_rt_uniqueness_in_evpn_check",
    "u_singtel_port_ip_check",
    "u_skip_review_activation_script_task",
    "u_static_check",
    "u_vpn_reference_check",
    "u_vrf_name_check",
    "u_router_name_check",
    # --- custom fields (String) ---
    "u_as_number_uniqueness_for_customer_comments",
    "u_authentication_key_for_md5_enbale_flag",
    "u_bfd",
    "u_bgp_time_neighboring",
    "u_class_of_service_comments",
    "u_customer_port_ip_comments",
    "u_dummy",
    "u_duplicate_lan_ip_address_comments",
    "u_duplicate_wan_ip_address_comments",
    "u_evcid_uniqueness_in_evc_comments",
    "u_interface_clean_check_comments",
    "u_mac_addresses",
    "u_ne_time_stamp",
    "u_new_customized_scripts",
    "u_nni_port_type_comments",
    "u_port_interface_description",
    "u_port_interface_details_comments",
    "u_port_speed_comments",
    "u_regenerate_activation_tree",
    "u_router_interface_standby",
    "u_router_name_comments",
    "u_routing_protocol_cust_nni_max_prefix_comments",
    "u_rt_uniqueness_in_evpn_comments",
    "u_singtel_port_ip_comments",
    "u_static_check_comments",
    "u_vpi_vci",
    "u_vpn_reference_comments",
    "u_vrf",
    "u_vrf_name_comments",
    # --- custom fields (Integer) ---
    "u_timeslot_from",
])


def _parse_pe_router_rfs_order(item: dict) -> dict:
    """Parse a raw ServiceNow PE Router RFS Order record into a clean dictionary."""
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
        # --- custom fields (Reference) ---
        "u_access_port_interface": extract_display_value(item.get("u_access_port_interface")),
        "u_access_port_interface_planning": extract_display_value(item.get("u_access_port_interface_planning")),
        "u_activation_logs": extract_display_value(item.get("u_activation_logs")),
        "u_activation_tree": extract_display_value(item.get("u_activation_tree")),
        "u_activation_trees": extract_display_value(item.get("u_activation_trees")),
        "u_auto_assignment_log": extract_display_value(item.get("u_auto_assignment_log")),
        "u_bgp_neighbors": extract_display_value(item.get("u_bgp_neighbors")),
        "u_ce_loopbacks": extract_display_value(item.get("u_ce_loopbacks")),
        "u_check_script": extract_display_value(item.get("u_check_script")),
        "u_check_script_tab": extract_display_value(item.get("u_check_script_tab")),
        "u_classes_of_service": extract_display_value(item.get("u_classes_of_service")),
        "u_combined_scripts": extract_display_value(item.get("u_combined_scripts")),
        "u_configuration_checks": extract_display_value(item.get("u_configuration_checks")),
        "u_copy": extract_display_value(item.get("u_copy")),
        "u_cos_component": extract_display_value(item.get("u_cos_component")),
        "u_cross_connect_egress_port_interface": extract_display_value(item.get("u_cross_connect_egress_port_interface")),
        "u_cross_connect_egress_port_interface_wip": extract_display_value(item.get("u_cross_connect_egress_port_interface_wip")),
        "u_cross_connect_egress_port_subinterface": extract_display_value(item.get("u_cross_connect_egress_port_subinterface")),
        "u_cross_connect_egress_port_subinterface_planning": extract_display_value(item.get("u_cross_connect_egress_port_subinterface_planning")),
        "u_cross_connect_ingress_evc_instance": extract_display_value(item.get("u_cross_connect_ingress_evc_instance")),
        "u_cross_connect_ingress_evc_instance_planning": extract_display_value(item.get("u_cross_connect_ingress_evc_instance_planning")),
        "u_cross_connect_ingress_port_interface": extract_display_value(item.get("u_cross_connect_ingress_port_interface")),
        "u_cross_connect_ingress_port_interface_wip": extract_display_value(item.get("u_cross_connect_ingress_port_interface_wip")),
        "u_cross_connect_ingress_port_subinterface": extract_display_value(item.get("u_cross_connect_ingress_port_subinterface")),
        "u_cross_connect_ingress_port_subinterfaceplanning": extract_display_value(item.get("u_cross_connect_ingress_port_subinterfaceplanning")),
        "u_customer_wan_ipv4_address": extract_display_value(item.get("u_customer_wan_ipv4_address")),
        "u_customer_wan_ipv4_address_gateway": extract_display_value(item.get("u_customer_wan_ipv4_address_gateway")),
        "u_customer_wan_ipv6_address": extract_display_value(item.get("u_customer_wan_ipv6_address")),
        "u_customized_scripts": extract_display_value(item.get("u_customized_scripts")),
        "u_customized_tree": extract_display_value(item.get("u_customized_tree")),
        "u_deactivation_logs": extract_display_value(item.get("u_deactivation_logs")),
        "u_dectivation_tree": extract_display_value(item.get("u_dectivation_tree")),
        "u_e_access_ingress_egress_cross_connect": extract_display_value(item.get("u_e_access_ingress_egress_cross_connect")),
        "u_e_access_ingress_egress_cross_connect_planning": extract_display_value(item.get("u_e_access_ingress_egress_cross_connect_planning")),
        "u_evpl_evc": extract_display_value(item.get("u_evpl_evc")),
        "u_evpl_evc_planning": extract_display_value(item.get("u_evpl_evc_planning")),
        "u_final_scripts": extract_display_value(item.get("u_final_scripts")),
        "u_inner_vlan": extract_display_value(item.get("u_inner_vlan")),
        "u_interface_set": extract_display_value(item.get("u_interface_set")),
        "u_internet_gateway_vrf": extract_display_value(item.get("u_internet_gateway_vrf")),
        "u_ipsec": extract_display_value(item.get("u_ipsec")),
        "u_ipv4_lan_ip_address": extract_display_value(item.get("u_ipv4_lan_ip_address")),
        "u_ipv6_lan_ip_address": extract_display_value(item.get("u_ipv6_lan_ip_address")),
        "u_load_balance_deactivation_scripts": extract_display_value(item.get("u_load_balance_deactivation_scripts")),
        "u_load_balance_dectivation_tree": extract_display_value(item.get("u_load_balance_dectivation_tree")),
        "u_load_balance_scripts": extract_display_value(item.get("u_load_balance_scripts")),
        "u_load_balance_tree": extract_display_value(item.get("u_load_balance_tree")),
        "u_load_balances": extract_display_value(item.get("u_load_balances")),
        "u_logical_system": extract_display_value(item.get("u_logical_system")),
        "u_loopback_ipv4_address": extract_display_value(item.get("u_loopback_ipv4_address")),
        "u_loopback_ipv6_address": extract_display_value(item.get("u_loopback_ipv6_address")),
        "u_mlppp_bundle_interfaces": extract_display_value(item.get("u_mlppp_bundle_interfaces")),
        "u_multicasts": extract_display_value(item.get("u_multicasts")),
        "u_nat": extract_display_value(item.get("u_nat")),
        "u_nat_pool_ip_address": extract_display_value(item.get("u_nat_pool_ip_address")),
        "u_nat_recource_component": extract_display_value(item.get("u_nat_recource_component")),
        "u_network_element": extract_display_value(item.get("u_network_element")),
        "u_outer_vlan": extract_display_value(item.get("u_outer_vlan")),
        "u_output_policy": extract_display_value(item.get("u_output_policy")),
        "u_outside_service_port_interface": extract_display_value(item.get("u_outside_service_port_interface")),
        "u_outside_service_port_interface_ipv4_address": extract_display_value(item.get("u_outside_service_port_interface_ipv4_address")),
        "u_outside_service_port_interface_planning": extract_display_value(item.get("u_outside_service_port_interface_planning")),
        "u_passive_access_port_interface": extract_display_value(item.get("u_passive_access_port_interface")),
        "u_passive_access_port_interface_planning": extract_display_value(item.get("u_passive_access_port_interface_planning")),
        "u_passive_service_port_interface": extract_display_value(item.get("u_passive_service_port_interface")),
        "u_passive_service_port_interface_planning": extract_display_value(item.get("u_passive_service_port_interface_planning")),
        "u_pre_patching_details": extract_display_value(item.get("u_pre_patching_details")),
        "u_records_checks": extract_display_value(item.get("u_records_checks")),
        "u_resource_inventory_configuration": extract_display_value(item.get("u_resource_inventory_configuration")),
        "u_rollback_script": extract_display_value(item.get("u_rollback_script")),
        "u_router_backup_port": extract_display_value(item.get("u_router_backup_port")),
        "u_router_interface_active": extract_display_value(item.get("u_router_interface_active")),
        "u_router_main_port": extract_display_value(item.get("u_router_main_port")),
        "u_router_slot": extract_display_value(item.get("u_router_slot")),
        "u_router_sub_interface": extract_display_value(item.get("u_router_sub_interface")),
        "u_running_configuration": extract_display_value(item.get("u_running_configuration")),
        "u_search_profile_id": extract_display_value(item.get("u_search_profile_id")),
        "u_service_port_interface": extract_display_value(item.get("u_service_port_interface")),
        "u_service_port_interface_planning": extract_display_value(item.get("u_service_port_interface_planning")),
        "u_singtel_virtual_ipv4_address": extract_display_value(item.get("u_singtel_virtual_ipv4_address")),
        "u_singtel_virtual_ipv4_address_gateway": extract_display_value(item.get("u_singtel_virtual_ipv4_address_gateway")),
        "u_singtel_virtual_ipv6_address": extract_display_value(item.get("u_singtel_virtual_ipv6_address")),
        "u_singtel_wan_ipv4_address": extract_display_value(item.get("u_singtel_wan_ipv4_address")),
        "u_singtel_wan_ipv4_address_gateway": extract_display_value(item.get("u_singtel_wan_ipv4_address_gateway")),
        "u_singtel_wan_ipv6_address": extract_display_value(item.get("u_singtel_wan_ipv6_address")),
        "u_static_lan_ip_address": extract_display_value(item.get("u_static_lan_ip_address")),
        "u_static_routes": extract_display_value(item.get("u_static_routes")),
        "u_static_rp": extract_display_value(item.get("u_static_rp")),
        "u_top_ip_range": extract_display_value(item.get("u_top_ip_range")),
        "u_trunk_port_interface": extract_display_value(item.get("u_trunk_port_interface")),
        "u_trunkportserviceattr": extract_display_value(item.get("u_trunkportserviceattr")),
        "u_use_ike_proposal": extract_display_value(item.get("u_use_ike_proposal")),
        "u_use_ipsec_policy": extract_display_value(item.get("u_use_ipsec_policy")),
        "u_vlan_id": extract_display_value(item.get("u_vlan_id")),
        "u_vrfs": extract_display_value(item.get("u_vrfs")),
        "u_vsis": extract_display_value(item.get("u_vsis")),
        # --- custom fields (Choice) ---
        "u_as_number_uniqueness_for_customer_check": item.get("u_as_number_uniqueness_for_customer_check"),
        "u_cease_and_provide": item.get("u_cease_and_provide"),
        "u_class_of_service_check": item.get("u_class_of_service_check"),
        "u_configure_main_interface": item.get("u_configure_main_interface"),
        "u_customer_port_ip_check": item.get("u_customer_port_ip_check"),
        "u_duplicate_lan_ip_address_static_in_vrf_check": item.get("u_duplicate_lan_ip_address_static_in_vrf_check"),
        "u_duplicate_wan_ip_address_check": item.get("u_duplicate_wan_ip_address_check"),
        "u_evcid_uniqueness_in_evc_check": item.get("u_evcid_uniqueness_in_evc_check"),
        "u_interface_clean_check": item.get("u_interface_clean_check"),
        "u_is_access_switch_rfs_needed": item.get("u_is_access_switch_rfs_needed"),
        "u_load_balancing_source_role": item.get("u_load_balancing_source_role"),
        "u_nni_link_type": item.get("u_nni_link_type"),
        "u_nni_port_type_check": item.get("u_nni_port_type_check"),
        "u_port_interface_details_check": item.get("u_port_interface_details_check"),
        "u_port_speed_downstream_upstream_check": item.get("u_port_speed_downstream_upstream_check"),
        "u_pre_check_result": item.get("u_pre_check_result"),
        "u_routing_protocol_cust_nni_max_prefix_check": item.get("u_routing_protocol_cust_nni_max_prefix_check"),
        "u_rt_uniqueness_in_evpn_check": item.get("u_rt_uniqueness_in_evpn_check"),
        "u_singtel_port_ip_check": item.get("u_singtel_port_ip_check"),
        "u_skip_review_activation_script_task": item.get("u_skip_review_activation_script_task"),
        "u_static_check": item.get("u_static_check"),
        "u_vpn_reference_check": item.get("u_vpn_reference_check"),
        "u_vrf_name_check": item.get("u_vrf_name_check"),
        "u_router_name_check": item.get("u_router_name_check"),
        # --- custom fields (String) ---
        "u_as_number_uniqueness_for_customer_comments": item.get("u_as_number_uniqueness_for_customer_comments"),
        "u_authentication_key_for_md5_enbale_flag": item.get("u_authentication_key_for_md5_enbale_flag"),
        "u_bfd": item.get("u_bfd"),
        "u_bgp_time_neighboring": item.get("u_bgp_time_neighboring"),
        "u_class_of_service_comments": item.get("u_class_of_service_comments"),
        "u_customer_port_ip_comments": item.get("u_customer_port_ip_comments"),
        "u_dummy": item.get("u_dummy"),
        "u_duplicate_lan_ip_address_comments": item.get("u_duplicate_lan_ip_address_comments"),
        "u_duplicate_wan_ip_address_comments": item.get("u_duplicate_wan_ip_address_comments"),
        "u_evcid_uniqueness_in_evc_comments": item.get("u_evcid_uniqueness_in_evc_comments"),
        "u_interface_clean_check_comments": item.get("u_interface_clean_check_comments"),
        "u_mac_addresses": item.get("u_mac_addresses"),
        "u_ne_time_stamp": item.get("u_ne_time_stamp"),
        "u_new_customized_scripts": item.get("u_new_customized_scripts"),
        "u_nni_port_type_comments": item.get("u_nni_port_type_comments"),
        "u_port_interface_description": item.get("u_port_interface_description"),
        "u_port_interface_details_comments": item.get("u_port_interface_details_comments"),
        "u_port_speed_comments": item.get("u_port_speed_comments"),
        "u_regenerate_activation_tree": item.get("u_regenerate_activation_tree"),
        "u_router_interface_standby": item.get("u_router_interface_standby"),
        "u_router_name_comments": item.get("u_router_name_comments"),
        "u_routing_protocol_cust_nni_max_prefix_comments": item.get("u_routing_protocol_cust_nni_max_prefix_comments"),
        "u_rt_uniqueness_in_evpn_comments": item.get("u_rt_uniqueness_in_evpn_comments"),
        "u_singtel_port_ip_comments": item.get("u_singtel_port_ip_comments"),
        "u_static_check_comments": item.get("u_static_check_comments"),
        "u_vpi_vci": item.get("u_vpi_vci"),
        "u_vpn_reference_comments": item.get("u_vpn_reference_comments"),
        "u_vrf": item.get("u_vrf"),
        "u_vrf_name_comments": item.get("u_vrf_name_comments"),
        # --- custom fields (Integer) ---
        "u_timeslot_from": item.get("u_timeslot_from"),
    }


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
@mcp.tool()
def list_pe_router_rfs_orders(
    limit: int = Field(10, description="Maximum number of PE Router RFS Orders to return"),
    offset: int = Field(0, description="Offset for pagination"),
    number: Optional[str] = Field(None, description="Filter by order number"),
    state: Optional[str] = Field(None, description="Filter by state"),
    assigned_to: Optional[str] = Field(None, description="Filter by assigned user"),
    assignment_group: Optional[str] = Field(None, description="Filter by assignment group"),
    u_network_element: Optional[str] = Field(None, description="Filter by Network Element (sys_id or display value)"),
    u_nni_link_type: Optional[str] = Field(None, description="Filter by NNI Link Type"),
    u_pre_check_result: Optional[str] = Field(None, description="Filter by Pre-Check Result"),
    u_cease_and_provide: Optional[str] = Field(None, description="Filter by Cease and Provide"),
    u_load_balancing_source_role: Optional[str] = Field(None, description="Filter by Load Balancing Source Role"),
    active: Optional[str] = Field(None, description="Filter by active status (true/false)"),
    priority: Optional[str] = Field(None, description="Filter by priority"),
    query: Optional[str] = Field(None, description="Encoded query string for advanced filtering"),
) -> str:
    """List PE Router RFS Order records from ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    try:
        url = f"{config.api_url}/table/{PE_ROUTER_RFS_ORDER_TABLE}"

        query_params = {
            "sysparm_limit": str(limit),
            "sysparm_offset": str(offset),
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
            "sysparm_fields": PE_ROUTER_RFS_ORDER_FIELDS,
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
        if u_network_element:
            query_parts.append(f"u_network_element={u_network_element}")
        if u_nni_link_type:
            query_parts.append(f"u_nni_link_type={u_nni_link_type}")
        if u_pre_check_result:
            query_parts.append(f"u_pre_check_result={u_pre_check_result}")
        if u_cease_and_provide:
            query_parts.append(f"u_cease_and_provide={u_cease_and_provide}")
        if u_load_balancing_source_role:
            query_parts.append(f"u_load_balancing_source_role={u_load_balancing_source_role}")
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
        orders = [_parse_pe_router_rfs_order(item) for item in data.get("result", [])]

        return format_list_response(orders, "pe_router_rfs_orders", limit, offset)

    except Exception as e:
        logger.error(f"Error listing PE Router RFS Orders: {e}")
        return format_error_response("list PE Router RFS Orders", e)


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------
@mcp.tool()
def get_pe_router_rfs_order(
    order_id: str = Field(
        ..., description="PE Router RFS Order sys_id or number"
    ),
) -> str:
    """Get a specific PE Router RFS Order record from ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    try:
        query_params = {
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
            "sysparm_fields": PE_ROUTER_RFS_ORDER_FIELDS,
        }

        if is_sys_id(order_id):
            url = f"{config.api_url}/table/{PE_ROUTER_RFS_ORDER_TABLE}/{order_id}"
        else:
            url = f"{config.api_url}/table/{PE_ROUTER_RFS_ORDER_TABLE}"
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
            return f"PE Router RFS Order not found: {order_id}"

        result = data["result"]
        if isinstance(result, list):
            if not result:
                return f"PE Router RFS Order not found: {order_id}"
            item = result[0]
        else:
            item = result

        order = _parse_pe_router_rfs_order(item)

        return format_success_response(
            f"Found PE Router RFS Order: {item.get('number')}",
            pe_router_rfs_order=order,
        )

    except Exception as e:
        logger.error(f"Error getting PE Router RFS Order: {e}")
        return format_error_response("get PE Router RFS Order", e)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
@mcp.tool()
def update_pe_router_rfs_order(
    order_id: str = Field(..., description="PE Router RFS Order sys_id or number"),
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
    # --- custom fields (Choice) ---
    u_as_number_uniqueness_for_customer_check: Optional[str] = Field(None, description="AS Number Uniqueness For Customer Check"),
    u_cease_and_provide: Optional[str] = Field(None, description="Cease and Provide"),
    u_class_of_service_check: Optional[str] = Field(None, description="Class of Service Check"),
    u_configure_main_interface: Optional[str] = Field(None, description="Configure Main Interface"),
    u_customer_port_ip_check: Optional[str] = Field(None, description="Customer Port IP Check"),
    u_duplicate_lan_ip_address_static_in_vrf_check: Optional[str] = Field(None, description="Duplicate LAN IP Address Static in VRF Check"),
    u_duplicate_wan_ip_address_check: Optional[str] = Field(None, description="Duplicate WAN IP Address Check"),
    u_evcid_uniqueness_in_evc_check: Optional[str] = Field(None, description="EVCID Uniqueness in EVC Check"),
    u_interface_clean_check: Optional[str] = Field(None, description="Interface Clean Check"),
    u_is_access_switch_rfs_needed: Optional[str] = Field(None, description="Is Access Switch RFS Needed"),
    u_load_balancing_source_role: Optional[str] = Field(None, description="Load Balancing Source Role"),
    u_nni_link_type: Optional[str] = Field(None, description="NNI Link Type"),
    u_nni_port_type_check: Optional[str] = Field(None, description="NNI Port Type Check"),
    u_port_interface_details_check: Optional[str] = Field(None, description="Port Interface Details Check"),
    u_port_speed_downstream_upstream_check: Optional[str] = Field(None, description="Port Speed Downstream/Upstream Check"),
    u_pre_check_result: Optional[str] = Field(None, description="Pre-Check Result"),
    u_routing_protocol_cust_nni_max_prefix_check: Optional[str] = Field(None, description="Routing Protocol Cust NNI Max Prefix Check"),
    u_rt_uniqueness_in_evpn_check: Optional[str] = Field(None, description="RT Uniqueness in EVPN Check"),
    u_singtel_port_ip_check: Optional[str] = Field(None, description="SingTel Port IP Check"),
    u_skip_review_activation_script_task: Optional[str] = Field(None, description="Skip Review Activation Script Task"),
    u_static_check: Optional[str] = Field(None, description="Static Check"),
    u_vpn_reference_check: Optional[str] = Field(None, description="VPN Reference Check"),
    u_vrf_name_check: Optional[str] = Field(None, description="VRF Name Check"),
    u_router_name_check: Optional[str] = Field(None, description="Router Name Check"),
    # --- custom fields (String) ---
    u_as_number_uniqueness_for_customer_comments: Optional[str] = Field(None, description="AS Number Uniqueness For Customer Comments"),
    u_authentication_key_for_md5_enbale_flag: Optional[str] = Field(None, description="Authentication Key for MD5 Enable Flag"),
    u_bfd: Optional[str] = Field(None, description="BFD"),
    u_bgp_time_neighboring: Optional[str] = Field(None, description="BGP Time Neighboring"),
    u_class_of_service_comments: Optional[str] = Field(None, description="Class of Service Comments"),
    u_customer_port_ip_comments: Optional[str] = Field(None, description="Customer Port IP Comments"),
    u_dummy: Optional[str] = Field(None, description="Dummy"),
    u_duplicate_lan_ip_address_comments: Optional[str] = Field(None, description="Duplicate LAN IP Address Comments"),
    u_duplicate_wan_ip_address_comments: Optional[str] = Field(None, description="Duplicate WAN IP Address Comments"),
    u_evcid_uniqueness_in_evc_comments: Optional[str] = Field(None, description="EVCID Uniqueness in EVC Comments"),
    u_interface_clean_check_comments: Optional[str] = Field(None, description="Interface Clean Check Comments"),
    u_mac_addresses: Optional[str] = Field(None, description="MAC Addresses"),
    u_ne_time_stamp: Optional[str] = Field(None, description="NE Time Stamp"),
    u_new_customized_scripts: Optional[str] = Field(None, description="New Customized Scripts"),
    u_nni_port_type_comments: Optional[str] = Field(None, description="NNI Port Type Comments"),
    u_port_interface_description: Optional[str] = Field(None, description="Port Interface Description"),
    u_port_interface_details_comments: Optional[str] = Field(None, description="Port Interface Details Comments"),
    u_port_speed_comments: Optional[str] = Field(None, description="Port Speed Comments"),
    u_regenerate_activation_tree: Optional[str] = Field(None, description="Regenerate Activation Tree"),
    u_router_interface_standby: Optional[str] = Field(None, description="Router Interface (Standby)"),
    u_router_name_comments: Optional[str] = Field(None, description="Router Name Comments"),
    u_routing_protocol_cust_nni_max_prefix_comments: Optional[str] = Field(None, description="Routing Protocol Cust NNI Max Prefix Comments"),
    u_rt_uniqueness_in_evpn_comments: Optional[str] = Field(None, description="RT Uniqueness in EVPN Comments"),
    u_singtel_port_ip_comments: Optional[str] = Field(None, description="SingTel Port IP Comments"),
    u_static_check_comments: Optional[str] = Field(None, description="Static Check Comments"),
    u_vpi_vci: Optional[str] = Field(None, description="VPI/VCI"),
    u_vpn_reference_comments: Optional[str] = Field(None, description="VPN Reference Comments"),
    u_vrf: Optional[str] = Field(None, description="VRF"),
    u_vrf_name_comments: Optional[str] = Field(None, description="VRF Name Comments"),
    # --- custom fields (Reference) ---
    u_access_port_interface: Optional[str] = Field(None, description="Access Port Interface (sys_id or display value)"),
    u_access_port_interface_planning: Optional[str] = Field(None, description="Access Port Interface Planning (sys_id or display value)"),
    u_activation_logs: Optional[str] = Field(None, description="Activation Logs (sys_id or display value)"),
    u_activation_tree: Optional[str] = Field(None, description="Activation Tree (sys_id or display value)"),
    u_activation_trees: Optional[str] = Field(None, description="Activation Trees (sys_id or display value)"),
    u_auto_assignment_log: Optional[str] = Field(None, description="Auto Assignment Log (sys_id or display value)"),
    u_bgp_neighbors: Optional[str] = Field(None, description="BGP Neighbors (sys_id or display value)"),
    u_ce_loopbacks: Optional[str] = Field(None, description="CE Loopbacks (sys_id or display value)"),
    u_check_script: Optional[str] = Field(None, description="Check Script (sys_id or display value)"),
    u_check_script_tab: Optional[str] = Field(None, description="Check Script Tab (sys_id or display value)"),
    u_classes_of_service: Optional[str] = Field(None, description="Classes Of Service (sys_id or display value)"),
    u_combined_scripts: Optional[str] = Field(None, description="Combined Scripts (sys_id or display value)"),
    u_configuration_checks: Optional[str] = Field(None, description="Configuration Checks (sys_id or display value)"),
    u_copy: Optional[str] = Field(None, description="Copy (sys_id or display value)"),
    u_cos_component: Optional[str] = Field(None, description="CoS Component (sys_id or display value)"),
    u_cross_connect_egress_port_interface: Optional[str] = Field(None, description="Cross-Connect Egress Port Interface (sys_id or display value)"),
    u_cross_connect_egress_port_interface_wip: Optional[str] = Field(None, description="Cross-Connect Egress Port Interface WIP (sys_id or display value)"),
    u_cross_connect_egress_port_subinterface: Optional[str] = Field(None, description="Cross-Connect Egress Port SubInterface (sys_id or display value)"),
    u_cross_connect_egress_port_subinterface_planning: Optional[str] = Field(None, description="Cross-Connect Egress Port SubInterface Planning (sys_id or display value)"),
    u_cross_connect_ingress_evc_instance: Optional[str] = Field(None, description="Cross-Connect Ingress EVC Instance (sys_id or display value)"),
    u_cross_connect_ingress_evc_instance_planning: Optional[str] = Field(None, description="Cross-Connect Ingress EVC Instance Planning (sys_id or display value)"),
    u_cross_connect_ingress_port_interface: Optional[str] = Field(None, description="Cross-Connect Ingress Port Interface (sys_id or display value)"),
    u_cross_connect_ingress_port_interface_wip: Optional[str] = Field(None, description="Cross-Connect Ingress Port Interface WIP (sys_id or display value)"),
    u_cross_connect_ingress_port_subinterface: Optional[str] = Field(None, description="Cross-Connect Ingress Port SubInterface (sys_id or display value)"),
    u_cross_connect_ingress_port_subinterfaceplanning: Optional[str] = Field(None, description="Cross-Connect Ingress Port SubInterface Planning (sys_id or display value)"),
    u_customer_wan_ipv4_address: Optional[str] = Field(None, description="Customer WAN IPv4 Address (sys_id or display value)"),
    u_customer_wan_ipv4_address_gateway: Optional[str] = Field(None, description="Customer WAN IPv4 Address Gateway (sys_id or display value)"),
    u_customer_wan_ipv6_address: Optional[str] = Field(None, description="Customer WAN IPv6 Address (sys_id or display value)"),
    u_customized_scripts: Optional[str] = Field(None, description="Customized Scripts (sys_id or display value)"),
    u_customized_tree: Optional[str] = Field(None, description="Customized Tree (sys_id or display value)"),
    u_deactivation_logs: Optional[str] = Field(None, description="Deactivation Logs (sys_id or display value)"),
    u_dectivation_tree: Optional[str] = Field(None, description="Deactivation Tree (sys_id or display value)"),
    u_e_access_ingress_egress_cross_connect: Optional[str] = Field(None, description="E-Access Ingress - Egress Cross-connect (sys_id or display value)"),
    u_e_access_ingress_egress_cross_connect_planning: Optional[str] = Field(None, description="E-Access Ingress - Egress Cross-connect Planning (sys_id or display value)"),
    u_evpl_evc: Optional[str] = Field(None, description="EVPL EVC (sys_id or display value)"),
    u_evpl_evc_planning: Optional[str] = Field(None, description="EVPL EVC Planning (sys_id or display value)"),
    u_final_scripts: Optional[str] = Field(None, description="Final Scripts (sys_id or display value)"),
    u_inner_vlan: Optional[str] = Field(None, description="Inner VLAN (sys_id or display value)"),
    u_interface_set: Optional[str] = Field(None, description="Interface Set (sys_id or display value)"),
    u_internet_gateway_vrf: Optional[str] = Field(None, description="Internet Gateway VRF (sys_id or display value)"),
    u_ipsec: Optional[str] = Field(None, description="IPSec (sys_id or display value)"),
    u_ipv4_lan_ip_address: Optional[str] = Field(None, description="IPv4 LAN IP Address (sys_id or display value)"),
    u_ipv6_lan_ip_address: Optional[str] = Field(None, description="IPv6 LAN IP Address (sys_id or display value)"),
    u_load_balance_deactivation_scripts: Optional[str] = Field(None, description="Load Balance Deactivation Scripts (sys_id or display value)"),
    u_load_balance_dectivation_tree: Optional[str] = Field(None, description="Load Balance Deactivation Tree (sys_id or display value)"),
    u_load_balance_scripts: Optional[str] = Field(None, description="Load Balance Scripts (sys_id or display value)"),
    u_load_balance_tree: Optional[str] = Field(None, description="Load Balance Tree (sys_id or display value)"),
    u_load_balances: Optional[str] = Field(None, description="Load Balances (sys_id or display value)"),
    u_logical_system: Optional[str] = Field(None, description="Logical System (sys_id or display value)"),
    u_loopback_ipv4_address: Optional[str] = Field(None, description="Loopback IPv4 Address (sys_id or display value)"),
    u_loopback_ipv6_address: Optional[str] = Field(None, description="Loopback IPv6 Address (sys_id or display value)"),
    u_mlppp_bundle_interfaces: Optional[str] = Field(None, description="MLPPP Bundle Interfaces (sys_id or display value)"),
    u_multicasts: Optional[str] = Field(None, description="Multicasts (sys_id or display value)"),
    u_nat: Optional[str] = Field(None, description="NAT (sys_id or display value)"),
    u_nat_pool_ip_address: Optional[str] = Field(None, description="NAT Pool IP Address (sys_id or display value)"),
    u_nat_recource_component: Optional[str] = Field(None, description="NAT Resource Component (sys_id or display value)"),
    u_network_element: Optional[str] = Field(None, description="Network Element (sys_id or display value)"),
    u_outer_vlan: Optional[str] = Field(None, description="Outer VLAN (sys_id or display value)"),
    u_output_policy: Optional[str] = Field(None, description="Output Policy (sys_id or display value)"),
    u_outside_service_port_interface: Optional[str] = Field(None, description="Outside Service Port Interface (sys_id or display value)"),
    u_outside_service_port_interface_ipv4_address: Optional[str] = Field(None, description="Outside Service Port Interface IPv4 Address (sys_id or display value)"),
    u_outside_service_port_interface_planning: Optional[str] = Field(None, description="Outside Service Port Interface Planning (sys_id or display value)"),
    u_passive_access_port_interface: Optional[str] = Field(None, description="Passive Access Port Interface (sys_id or display value)"),
    u_passive_access_port_interface_planning: Optional[str] = Field(None, description="Passive Access Port Interface Planning (sys_id or display value)"),
    u_passive_service_port_interface: Optional[str] = Field(None, description="Passive Service Port Interface (sys_id or display value)"),
    u_passive_service_port_interface_planning: Optional[str] = Field(None, description="Passive Service Port Interface Planning (sys_id or display value)"),
    u_pre_patching_details: Optional[str] = Field(None, description="Pre-patching details (sys_id or display value)"),
    u_records_checks: Optional[str] = Field(None, description="Records Checks (sys_id or display value)"),
    u_resource_inventory_configuration: Optional[str] = Field(None, description="Resource Inventory Configuration (sys_id or display value)"),
    u_rollback_script: Optional[str] = Field(None, description="Rollback Script (sys_id or display value)"),
    u_router_backup_port: Optional[str] = Field(None, description="Router Backup Port (sys_id or display value)"),
    u_router_interface_active: Optional[str] = Field(None, description="Router Interface Active (sys_id or display value)"),
    u_router_main_port: Optional[str] = Field(None, description="Router Main Port (sys_id or display value)"),
    u_router_slot: Optional[str] = Field(None, description="Router Slot (sys_id or display value)"),
    u_router_sub_interface: Optional[str] = Field(None, description="Router Sub Interface (sys_id or display value)"),
    u_running_configuration: Optional[str] = Field(None, description="Running Configuration (sys_id or display value)"),
    u_search_profile_id: Optional[str] = Field(None, description="Search Profile ID (sys_id or display value)"),
    u_service_port_interface: Optional[str] = Field(None, description="Service Port Interface (sys_id or display value)"),
    u_service_port_interface_planning: Optional[str] = Field(None, description="Service Port Interface Planning (sys_id or display value)"),
    u_singtel_virtual_ipv4_address: Optional[str] = Field(None, description="SingTel Virtual IPv4 Address (sys_id or display value)"),
    u_singtel_virtual_ipv4_address_gateway: Optional[str] = Field(None, description="SingTel Virtual IPv4 Address Gateway (sys_id or display value)"),
    u_singtel_virtual_ipv6_address: Optional[str] = Field(None, description="SingTel Virtual IPv6 Address (sys_id or display value)"),
    u_singtel_wan_ipv4_address: Optional[str] = Field(None, description="SingTel WAN IPv4 Address (sys_id or display value)"),
    u_singtel_wan_ipv4_address_gateway: Optional[str] = Field(None, description="SingTel WAN IPv4 Address Gateway (sys_id or display value)"),
    u_singtel_wan_ipv6_address: Optional[str] = Field(None, description="SingTel WAN IPv6 Address (sys_id or display value)"),
    u_static_lan_ip_address: Optional[str] = Field(None, description="Static LAN IP Address (sys_id or display value)"),
    u_static_routes: Optional[str] = Field(None, description="Static Routes (sys_id or display value)"),
    u_static_rp: Optional[str] = Field(None, description="Static RP (sys_id or display value)"),
    u_top_ip_range: Optional[str] = Field(None, description="Top IP Range (sys_id or display value)"),
    u_trunk_port_interface: Optional[str] = Field(None, description="Trunk Port Interface (sys_id or display value)"),
    u_trunkportserviceattr: Optional[str] = Field(None, description="Trunk Port Service Attr (sys_id or display value)"),
    u_use_ike_proposal: Optional[str] = Field(None, description="Use IKE Proposal (sys_id or display value)"),
    u_use_ipsec_policy: Optional[str] = Field(None, description="Use IPSEC Policy (sys_id or display value)"),
    u_vlan_id: Optional[str] = Field(None, description="VLAN ID (sys_id or display value)"),
    u_vrfs: Optional[str] = Field(None, description="VRFs (sys_id or display value)"),
    u_vsis: Optional[str] = Field(None, description="VSIs (sys_id or display value)"),
    # --- custom fields (Integer) ---
    u_timeslot_from: Optional[int] = Field(None, description="Timeslot From"),
) -> str:
    """Update an existing PE Router RFS Order record in ServiceNow."""
    config = get_config()
    auth_manager = get_auth_manager()

    # Resolve to sys_id if a number was provided
    sys_id_to_update = order_id
    if not is_sys_id(order_id):
        search_url = f"{config.api_url}/table/{PE_ROUTER_RFS_ORDER_TABLE}"
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
                return f"PE Router RFS Order not found: {order_id}"
            sys_id_to_update = s_res[0]["sys_id"]
        except Exception as e:
            return f"Error resolving PE Router RFS Order ID: {str(e)}"

    url = f"{config.api_url}/table/{PE_ROUTER_RFS_ORDER_TABLE}/{sys_id_to_update}"

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
        # custom fields (Choice)
        "u_as_number_uniqueness_for_customer_check": u_as_number_uniqueness_for_customer_check,
        "u_cease_and_provide": u_cease_and_provide,
        "u_class_of_service_check": u_class_of_service_check,
        "u_configure_main_interface": u_configure_main_interface,
        "u_customer_port_ip_check": u_customer_port_ip_check,
        "u_duplicate_lan_ip_address_static_in_vrf_check": u_duplicate_lan_ip_address_static_in_vrf_check,
        "u_duplicate_wan_ip_address_check": u_duplicate_wan_ip_address_check,
        "u_evcid_uniqueness_in_evc_check": u_evcid_uniqueness_in_evc_check,
        "u_interface_clean_check": u_interface_clean_check,
        "u_is_access_switch_rfs_needed": u_is_access_switch_rfs_needed,
        "u_load_balancing_source_role": u_load_balancing_source_role,
        "u_nni_link_type": u_nni_link_type,
        "u_nni_port_type_check": u_nni_port_type_check,
        "u_port_interface_details_check": u_port_interface_details_check,
        "u_port_speed_downstream_upstream_check": u_port_speed_downstream_upstream_check,
        "u_pre_check_result": u_pre_check_result,
        "u_routing_protocol_cust_nni_max_prefix_check": u_routing_protocol_cust_nni_max_prefix_check,
        "u_rt_uniqueness_in_evpn_check": u_rt_uniqueness_in_evpn_check,
        "u_singtel_port_ip_check": u_singtel_port_ip_check,
        "u_skip_review_activation_script_task": u_skip_review_activation_script_task,
        "u_static_check": u_static_check,
        "u_vpn_reference_check": u_vpn_reference_check,
        "u_vrf_name_check": u_vrf_name_check,
        "u_router_name_check": u_router_name_check,
        # custom fields (String)
        "u_as_number_uniqueness_for_customer_comments": u_as_number_uniqueness_for_customer_comments,
        "u_authentication_key_for_md5_enbale_flag": u_authentication_key_for_md5_enbale_flag,
        "u_bfd": u_bfd,
        "u_bgp_time_neighboring": u_bgp_time_neighboring,
        "u_class_of_service_comments": u_class_of_service_comments,
        "u_customer_port_ip_comments": u_customer_port_ip_comments,
        "u_dummy": u_dummy,
        "u_duplicate_lan_ip_address_comments": u_duplicate_lan_ip_address_comments,
        "u_duplicate_wan_ip_address_comments": u_duplicate_wan_ip_address_comments,
        "u_evcid_uniqueness_in_evc_comments": u_evcid_uniqueness_in_evc_comments,
        "u_interface_clean_check_comments": u_interface_clean_check_comments,
        "u_mac_addresses": u_mac_addresses,
        "u_ne_time_stamp": u_ne_time_stamp,
        "u_new_customized_scripts": u_new_customized_scripts,
        "u_nni_port_type_comments": u_nni_port_type_comments,
        "u_port_interface_description": u_port_interface_description,
        "u_port_interface_details_comments": u_port_interface_details_comments,
        "u_port_speed_comments": u_port_speed_comments,
        "u_regenerate_activation_tree": u_regenerate_activation_tree,
        "u_router_interface_standby": u_router_interface_standby,
        "u_router_name_comments": u_router_name_comments,
        "u_routing_protocol_cust_nni_max_prefix_comments": u_routing_protocol_cust_nni_max_prefix_comments,
        "u_rt_uniqueness_in_evpn_comments": u_rt_uniqueness_in_evpn_comments,
        "u_singtel_port_ip_comments": u_singtel_port_ip_comments,
        "u_static_check_comments": u_static_check_comments,
        "u_vpi_vci": u_vpi_vci,
        "u_vpn_reference_comments": u_vpn_reference_comments,
        "u_vrf": u_vrf,
        "u_vrf_name_comments": u_vrf_name_comments,
        # custom fields (Reference)
        "u_access_port_interface": u_access_port_interface,
        "u_access_port_interface_planning": u_access_port_interface_planning,
        "u_activation_logs": u_activation_logs,
        "u_activation_tree": u_activation_tree,
        "u_activation_trees": u_activation_trees,
        "u_auto_assignment_log": u_auto_assignment_log,
        "u_bgp_neighbors": u_bgp_neighbors,
        "u_ce_loopbacks": u_ce_loopbacks,
        "u_check_script": u_check_script,
        "u_check_script_tab": u_check_script_tab,
        "u_classes_of_service": u_classes_of_service,
        "u_combined_scripts": u_combined_scripts,
        "u_configuration_checks": u_configuration_checks,
        "u_copy": u_copy,
        "u_cos_component": u_cos_component,
        "u_cross_connect_egress_port_interface": u_cross_connect_egress_port_interface,
        "u_cross_connect_egress_port_interface_wip": u_cross_connect_egress_port_interface_wip,
        "u_cross_connect_egress_port_subinterface": u_cross_connect_egress_port_subinterface,
        "u_cross_connect_egress_port_subinterface_planning": u_cross_connect_egress_port_subinterface_planning,
        "u_cross_connect_ingress_evc_instance": u_cross_connect_ingress_evc_instance,
        "u_cross_connect_ingress_evc_instance_planning": u_cross_connect_ingress_evc_instance_planning,
        "u_cross_connect_ingress_port_interface": u_cross_connect_ingress_port_interface,
        "u_cross_connect_ingress_port_interface_wip": u_cross_connect_ingress_port_interface_wip,
        "u_cross_connect_ingress_port_subinterface": u_cross_connect_ingress_port_subinterface,
        "u_cross_connect_ingress_port_subinterfaceplanning": u_cross_connect_ingress_port_subinterfaceplanning,
        "u_customer_wan_ipv4_address": u_customer_wan_ipv4_address,
        "u_customer_wan_ipv4_address_gateway": u_customer_wan_ipv4_address_gateway,
        "u_customer_wan_ipv6_address": u_customer_wan_ipv6_address,
        "u_customized_scripts": u_customized_scripts,
        "u_customized_tree": u_customized_tree,
        "u_deactivation_logs": u_deactivation_logs,
        "u_dectivation_tree": u_dectivation_tree,
        "u_e_access_ingress_egress_cross_connect": u_e_access_ingress_egress_cross_connect,
        "u_e_access_ingress_egress_cross_connect_planning": u_e_access_ingress_egress_cross_connect_planning,
        "u_evpl_evc": u_evpl_evc,
        "u_evpl_evc_planning": u_evpl_evc_planning,
        "u_final_scripts": u_final_scripts,
        "u_inner_vlan": u_inner_vlan,
        "u_interface_set": u_interface_set,
        "u_internet_gateway_vrf": u_internet_gateway_vrf,
        "u_ipsec": u_ipsec,
        "u_ipv4_lan_ip_address": u_ipv4_lan_ip_address,
        "u_ipv6_lan_ip_address": u_ipv6_lan_ip_address,
        "u_load_balance_deactivation_scripts": u_load_balance_deactivation_scripts,
        "u_load_balance_dectivation_tree": u_load_balance_dectivation_tree,
        "u_load_balance_scripts": u_load_balance_scripts,
        "u_load_balance_tree": u_load_balance_tree,
        "u_load_balances": u_load_balances,
        "u_logical_system": u_logical_system,
        "u_loopback_ipv4_address": u_loopback_ipv4_address,
        "u_loopback_ipv6_address": u_loopback_ipv6_address,
        "u_mlppp_bundle_interfaces": u_mlppp_bundle_interfaces,
        "u_multicasts": u_multicasts,
        "u_nat": u_nat,
        "u_nat_pool_ip_address": u_nat_pool_ip_address,
        "u_nat_recource_component": u_nat_recource_component,
        "u_network_element": u_network_element,
        "u_outer_vlan": u_outer_vlan,
        "u_output_policy": u_output_policy,
        "u_outside_service_port_interface": u_outside_service_port_interface,
        "u_outside_service_port_interface_ipv4_address": u_outside_service_port_interface_ipv4_address,
        "u_outside_service_port_interface_planning": u_outside_service_port_interface_planning,
        "u_passive_access_port_interface": u_passive_access_port_interface,
        "u_passive_access_port_interface_planning": u_passive_access_port_interface_planning,
        "u_passive_service_port_interface": u_passive_service_port_interface,
        "u_passive_service_port_interface_planning": u_passive_service_port_interface_planning,
        "u_pre_patching_details": u_pre_patching_details,
        "u_records_checks": u_records_checks,
        "u_resource_inventory_configuration": u_resource_inventory_configuration,
        "u_rollback_script": u_rollback_script,
        "u_router_backup_port": u_router_backup_port,
        "u_router_interface_active": u_router_interface_active,
        "u_router_main_port": u_router_main_port,
        "u_router_slot": u_router_slot,
        "u_router_sub_interface": u_router_sub_interface,
        "u_running_configuration": u_running_configuration,
        "u_search_profile_id": u_search_profile_id,
        "u_service_port_interface": u_service_port_interface,
        "u_service_port_interface_planning": u_service_port_interface_planning,
        "u_singtel_virtual_ipv4_address": u_singtel_virtual_ipv4_address,
        "u_singtel_virtual_ipv4_address_gateway": u_singtel_virtual_ipv4_address_gateway,
        "u_singtel_virtual_ipv6_address": u_singtel_virtual_ipv6_address,
        "u_singtel_wan_ipv4_address": u_singtel_wan_ipv4_address,
        "u_singtel_wan_ipv4_address_gateway": u_singtel_wan_ipv4_address_gateway,
        "u_singtel_wan_ipv6_address": u_singtel_wan_ipv6_address,
        "u_static_lan_ip_address": u_static_lan_ip_address,
        "u_static_routes": u_static_routes,
        "u_static_rp": u_static_rp,
        "u_top_ip_range": u_top_ip_range,
        "u_trunk_port_interface": u_trunk_port_interface,
        "u_trunkportserviceattr": u_trunkportserviceattr,
        "u_use_ike_proposal": u_use_ike_proposal,
        "u_use_ipsec_policy": u_use_ipsec_policy,
        "u_vlan_id": u_vlan_id,
        "u_vrfs": u_vrfs,
        "u_vsis": u_vsis,
    }

    for key, value in field_map.items():
        if value is not None:
            body[key] = value

    # Handle integer fields
    if u_timeslot_from is not None:
        body["u_timeslot_from"] = str(u_timeslot_from)

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
            return "Failed to update PE Router RFS Order"

        result = data["result"]
        return format_success_response(
            f"PE Router RFS Order updated successfully: {result.get('number')}",
            sys_id=result.get("sys_id"),
            number=result.get("number"),
        )

    except Exception as e:
        logger.error(f"Error updating PE Router RFS Order: {e}")
        return format_error_response("update PE Router RFS Order", e)
