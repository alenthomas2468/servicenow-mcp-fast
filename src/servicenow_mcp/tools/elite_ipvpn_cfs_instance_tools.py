"""
eLite IPVPN CFS Instance tools for the ServiceNow MCP server.

This module provides tools for managing eLite IPVPN CFS Instance
(u_cmdb_elite_ipvpn_cfs_instance) CI records in ServiceNow.
The table extends cmdb_ci via TINA CFS Instance.

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
ELITE_IPVPN_CFS_INSTANCE_TABLE = "u_cmdb_elite_ipvpn_cfs_instance"

# Common fields to retrieve in list/get operations
ELITE_IPVPN_CFS_INSTANCE_FIELDS = ",".join([
    # --- inherited cmdb_ci fields ---
    "sys_id",
    "name",
    "number",
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
    "schedule",
    "maintenance_schedule",
    "lease_id",
    "po_number",
    "gl_account",
    "invoice_number",
    "install_date",
    "purchase_date",
    "warranty_expiration",
    "first_discovered",
    "last_discovered",
    "discovery_source",
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
    "u_activation_assignee",
    "u_activation_process",
    "u_cfs_instance",
    "u_component_instance",
    "u_component_specification",
    "u_configuration_assignee",
    "u_contact_details",
    "u_coordination_assignee",
    "u_customer_account",
    "u_customer_location_a",
    "u_dependent_instances",
    "u_email_messages",
    "u_engineering_assignee",
    "u_first_circuit_aendpoint",
    "u_inner_vlan",
    "u_l3_vpn",
    "u_main_circuit_cfs_instance",
    "u_main_circuit_cfs_order",
    "u_managed_service_cfs_instance",
    "u_managed_service_cfs_order",
    "u_network_product",
    "u_order_notes",
    "u_orders",
    "u_originating_city",
    "u_originating_country",
    "u_originating_location",
    "u_outer_vlan",
    "u_parent_network_element",
    "u_parent_ri_object",
    "u_previous_snapshot",
    "u_previous_snapshot_version",
    "u_reserved_lan_ip_ranges",
    "u_rfs_instances",
    "u_service_no",
    "u_service_view_diagram_template",
    "u_specification",
    "u_tasks",
    "u_terminating_location",
    "u_terminating_pop_location",
    "u_tina_cfs_order",
    "u_tina_rfs_order",
    "u_vpn_sites",
    "u_wip_of",
    "u_wip_ref",
    "u_work_activity_user_for_pre_check",
    # --- custom fields (Choice/String) ---
    "u_activated_when",
    "u_activation_status",
    "u_as_override",
    "u_authorized_installer",
    "u_backup_port_speed_duplex",
    "u_backup_type",
    "u_bandwidth",
    "u_bgp_autonomous_system_number",
    "u_bgp_md5_ipv4_password",
    "u_bgp_md5_ipv6_password",
    "u_bgp_md5_password",
    "u_bgp_number_of_prefixes",
    "u_bpj_evc_router_id",
    "u_circuit_scheme",
    "u_circuit_tie",
    "u_circuit_type",
    "u_component_id",
    "u_component_name",
    "u_construction_completion_date",
    "u_cos_type",
    "u_cpe_model",
    "u_crd_date",
    "u_customer_location_b",
    "u_customer_name",
    "u_customer_wan_ipv4_address",
    "u_customer_wan_ipv6_address",
    "u_customized_circuit",
    "u_date_service_ordered",
    "u_date_service_provided",
    "u_date_service_requested",
    "u_disconnected_when",
    "u_discovery_status",
    "u_display_message",
    "u_email_address",
    "u_encapsulation",
    "u_enet_code",
    "u_externalid",
    "u_fiber_cable_1",
    "u_fiber_no_1",
    "u_fiber_system_name",
    "u_fibre_code",
    "u_fibre_no",
    "u_flow_status",
    "u_go_to_metamodel",
    "u_hold_down_timer",
    "u_hub_spoke",
    "u_incorrectness_reason",
    "u_internet_framing_bytes",
    "u_internet_protocol",
    "u_ipp_dscp",
    "u_ipv4_lan_address",
    "u_ipv6_lan_address",
    "u_last_circuit_zendpoint",
    "u_legend",
    "u_length_of_term",
    "u_main_circuit_reference",
    "u_main_reference_no",
    "u_megapop2_indicator",
    "u_naming_trigger",
    "u_network_product_code",
    "u_network_product_description",
    "u_new_service_instance_name",
    "u_node_name",
    "u_order_from",
    "u_originating_city_code",
    "u_originating_llc_partner_name",
    "u_originating_llc_partner_reference",
    "u_originating_pegasus_service_number",
    "u_originating_pop_location",
    "u_originating_state",
    "u_originating_work_order_number",
    "u_other_authorized_installer",
    "u_part_of_bundle",
    "u_port",
    "u_port_mode",
    "u_port_no",
    "u_port_speed_duplex",
    "u_previous_value_stored",
    "u_proactive_monitoring",
    "u_product_code",
    "u_project_code",
    "u_project_end_date",
    "u_project_no",
    "u_project_start_date",
    "u_ptn_3900_multiplexer_port",
    "u_record_source",
    "u_rejection_reason",
    "u_related_cfs_instances",
    "u_related_cfs_orders",
    "u_related_rfs_instances",
    "u_related_rfs_orders",
    "u_router_interface",
    "u_router_name",
    "u_router_slot",
    "u_router_sub_interface",
    "u_routing_protocol",
    "u_service_data_correctness",
    "u_service_domain",
    "u_service_group",
    "u_service_instance_id",
    "u_service_number",
    "u_service_type",
    "u_set_value_flow_status",
    "u_singnet_indicator",
    "u_singtel_wan_ipv4_address",
    "u_singtel_wan_ipv6_address",
    "u_slot",
    "u_snapshot_state",
    "u_standard_class_dscp_value",
    "u_standard_class_ipp_value",
    "u_static_lan_ip_addresses",
    "u_status",
    "u_svlan_inner_vlan_id",
    "u_tariff_codes",
    "u_terminating_llc_partner_name",
    "u_terminating_llc_partner_reference",
    "u_terminating_pegasus_np_service_number",
    "u_terminating_work_order_number",
    "u_test_results",
    "u_tina_cfs_order_number",
    "u_validation_result",
    "u_vlan_id",
    "u_vpn_group",
    "u_vpn_group_id",
    "u_vpn_short_name",
    "u_vrf_name",
    "u_wan_ipv4_subnet_mask",
    "u_wan_ipv6_subnet_mask",
    "u_wholesale",
    "u_originated_by",
    "u_used_by",
    # --- custom fields (Integer/Long) ---
    "u_additional_speed",
    "u_as_prepend",
    "u_bfd_minimal_interval",
    "u_bfd_multiplier",
    "u_dummy_speed",
    "u_install_charges",
    "u_local_preference",
    "u_network_product_instance_id",
    "u_original",
    "u_original_speed",
    "u_speed_bps",
    # --- custom fields (Boolean) ---
    "u_is_preconfigured_object",
    "u_wip_object",
])


def _parse_elite_ipvpn_cfs_instance(item: dict) -> dict:
    """Parse a raw ServiceNow eLite IPVPN CFS Instance record into a clean dictionary."""
    return {
        # --- inherited cmdb_ci fields ---
        "sys_id": item.get("sys_id"),
        "name": item.get("name"),
        "number": item.get("number"),
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
        "u_activation_assignee": extract_display_value(item.get("u_activation_assignee")),
        "u_activation_process": extract_display_value(item.get("u_activation_process")),
        "u_cfs_instance": extract_display_value(item.get("u_cfs_instance")),
        "u_component_instance": extract_display_value(item.get("u_component_instance")),
        "u_component_specification": extract_display_value(item.get("u_component_specification")),
        "u_configuration_assignee": extract_display_value(item.get("u_configuration_assignee")),
        "u_contact_details": extract_display_value(item.get("u_contact_details")),
        "u_coordination_assignee": extract_display_value(item.get("u_coordination_assignee")),
        "u_customer_account": extract_display_value(item.get("u_customer_account")),
        "u_customer_location_a": extract_display_value(item.get("u_customer_location_a")),
        "u_dependent_instances": extract_display_value(item.get("u_dependent_instances")),
        "u_email_messages": extract_display_value(item.get("u_email_messages")),
        "u_engineering_assignee": extract_display_value(item.get("u_engineering_assignee")),
        "u_first_circuit_aendpoint": extract_display_value(item.get("u_first_circuit_aendpoint")),
        "u_inner_vlan": extract_display_value(item.get("u_inner_vlan")),
        "u_l3_vpn": extract_display_value(item.get("u_l3_vpn")),
        "u_main_circuit_cfs_instance": extract_display_value(item.get("u_main_circuit_cfs_instance")),
        "u_main_circuit_cfs_order": extract_display_value(item.get("u_main_circuit_cfs_order")),
        "u_managed_service_cfs_instance": extract_display_value(item.get("u_managed_service_cfs_instance")),
        "u_managed_service_cfs_order": extract_display_value(item.get("u_managed_service_cfs_order")),
        "u_network_product": extract_display_value(item.get("u_network_product")),
        "u_order_notes": extract_display_value(item.get("u_order_notes")),
        "u_orders": extract_display_value(item.get("u_orders")),
        "u_originating_city": extract_display_value(item.get("u_originating_city")),
        "u_originating_country": extract_display_value(item.get("u_originating_country")),
        "u_originating_location": extract_display_value(item.get("u_originating_location")),
        "u_outer_vlan": extract_display_value(item.get("u_outer_vlan")),
        "u_parent_network_element": extract_display_value(item.get("u_parent_network_element")),
        "u_parent_ri_object": extract_display_value(item.get("u_parent_ri_object")),
        "u_previous_snapshot": extract_display_value(item.get("u_previous_snapshot")),
        "u_previous_snapshot_version": extract_display_value(item.get("u_previous_snapshot_version")),
        "u_reserved_lan_ip_ranges": extract_display_value(item.get("u_reserved_lan_ip_ranges")),
        "u_rfs_instances": extract_display_value(item.get("u_rfs_instances")),
        "u_service_no": extract_display_value(item.get("u_service_no")),
        "u_service_view_diagram_template": extract_display_value(item.get("u_service_view_diagram_template")),
        "u_specification": extract_display_value(item.get("u_specification")),
        "u_tasks": extract_display_value(item.get("u_tasks")),
        "u_terminating_location": extract_display_value(item.get("u_terminating_location")),
        "u_terminating_pop_location": extract_display_value(item.get("u_terminating_pop_location")),
        "u_tina_cfs_order": extract_display_value(item.get("u_tina_cfs_order")),
        "u_tina_rfs_order": extract_display_value(item.get("u_tina_rfs_order")),
        "u_vpn_sites": extract_display_value(item.get("u_vpn_sites")),
        "u_wip_of": extract_display_value(item.get("u_wip_of")),
        "u_wip_ref": extract_display_value(item.get("u_wip_ref")),
        "u_work_activity_user_for_pre_check": extract_display_value(item.get("u_work_activity_user_for_pre_check")),
        # --- custom fields (Choice/String) ---
        "u_activated_when": item.get("u_activated_when"),
        "u_activation_status": item.get("u_activation_status"),
        "u_as_override": item.get("u_as_override"),
        "u_authorized_installer": item.get("u_authorized_installer"),
        "u_backup_port_speed_duplex": item.get("u_backup_port_speed_duplex"),
        "u_backup_type": item.get("u_backup_type"),
        "u_bandwidth": item.get("u_bandwidth"),
        "u_bgp_autonomous_system_number": item.get("u_bgp_autonomous_system_number"),
        "u_bgp_md5_ipv4_password": item.get("u_bgp_md5_ipv4_password"),
        "u_bgp_md5_ipv6_password": item.get("u_bgp_md5_ipv6_password"),
        "u_bgp_md5_password": item.get("u_bgp_md5_password"),
        "u_bgp_number_of_prefixes": item.get("u_bgp_number_of_prefixes"),
        "u_bpj_evc_router_id": item.get("u_bpj_evc_router_id"),
        "u_circuit_scheme": item.get("u_circuit_scheme"),
        "u_circuit_tie": item.get("u_circuit_tie"),
        "u_circuit_type": item.get("u_circuit_type"),
        "u_component_id": item.get("u_component_id"),
        "u_component_name": item.get("u_component_name"),
        "u_construction_completion_date": item.get("u_construction_completion_date"),
        "u_cos_type": item.get("u_cos_type"),
        "u_cpe_model": item.get("u_cpe_model"),
        "u_crd_date": item.get("u_crd_date"),
        "u_customer_location_b": item.get("u_customer_location_b"),
        "u_customer_name": item.get("u_customer_name"),
        "u_customer_wan_ipv4_address": item.get("u_customer_wan_ipv4_address"),
        "u_customer_wan_ipv6_address": item.get("u_customer_wan_ipv6_address"),
        "u_customized_circuit": item.get("u_customized_circuit"),
        "u_date_service_ordered": item.get("u_date_service_ordered"),
        "u_date_service_provided": item.get("u_date_service_provided"),
        "u_date_service_requested": item.get("u_date_service_requested"),
        "u_disconnected_when": item.get("u_disconnected_when"),
        "u_discovery_status": item.get("u_discovery_status"),
        "u_display_message": item.get("u_display_message"),
        "u_email_address": item.get("u_email_address"),
        "u_encapsulation": item.get("u_encapsulation"),
        "u_enet_code": item.get("u_enet_code"),
        "u_externalid": item.get("u_externalid"),
        "u_fiber_cable_1": item.get("u_fiber_cable_1"),
        "u_fiber_no_1": item.get("u_fiber_no_1"),
        "u_fiber_system_name": item.get("u_fiber_system_name"),
        "u_fibre_code": item.get("u_fibre_code"),
        "u_fibre_no": item.get("u_fibre_no"),
        "u_flow_status": item.get("u_flow_status"),
        "u_go_to_metamodel": item.get("u_go_to_metamodel"),
        "u_hold_down_timer": item.get("u_hold_down_timer"),
        "u_hub_spoke": item.get("u_hub_spoke"),
        "u_incorrectness_reason": item.get("u_incorrectness_reason"),
        "u_internet_framing_bytes": item.get("u_internet_framing_bytes"),
        "u_internet_protocol": item.get("u_internet_protocol"),
        "u_ipp_dscp": item.get("u_ipp_dscp"),
        "u_ipv4_lan_address": item.get("u_ipv4_lan_address"),
        "u_ipv6_lan_address": item.get("u_ipv6_lan_address"),
        "u_last_circuit_zendpoint": item.get("u_last_circuit_zendpoint"),
        "u_legend": item.get("u_legend"),
        "u_length_of_term": item.get("u_length_of_term"),
        "u_main_circuit_reference": item.get("u_main_circuit_reference"),
        "u_main_reference_no": item.get("u_main_reference_no"),
        "u_megapop2_indicator": item.get("u_megapop2_indicator"),
        "u_naming_trigger": item.get("u_naming_trigger"),
        "u_network_product_code": item.get("u_network_product_code"),
        "u_network_product_description": item.get("u_network_product_description"),
        "u_new_service_instance_name": item.get("u_new_service_instance_name"),
        "u_node_name": item.get("u_node_name"),
        "u_order_from": item.get("u_order_from"),
        "u_originating_city_code": item.get("u_originating_city_code"),
        "u_originating_llc_partner_name": item.get("u_originating_llc_partner_name"),
        "u_originating_llc_partner_reference": item.get("u_originating_llc_partner_reference"),
        "u_originating_pegasus_service_number": item.get("u_originating_pegasus_service_number"),
        "u_originating_pop_location": item.get("u_originating_pop_location"),
        "u_originating_state": item.get("u_originating_state"),
        "u_originating_work_order_number": item.get("u_originating_work_order_number"),
        "u_other_authorized_installer": item.get("u_other_authorized_installer"),
        "u_part_of_bundle": item.get("u_part_of_bundle"),
        "u_port": item.get("u_port"),
        "u_port_mode": item.get("u_port_mode"),
        "u_port_no": item.get("u_port_no"),
        "u_port_speed_duplex": item.get("u_port_speed_duplex"),
        "u_previous_value_stored": item.get("u_previous_value_stored"),
        "u_proactive_monitoring": item.get("u_proactive_monitoring"),
        "u_product_code": item.get("u_product_code"),
        "u_project_code": item.get("u_project_code"),
        "u_project_end_date": item.get("u_project_end_date"),
        "u_project_no": item.get("u_project_no"),
        "u_project_start_date": item.get("u_project_start_date"),
        "u_ptn_3900_multiplexer_port": item.get("u_ptn_3900_multiplexer_port"),
        "u_record_source": item.get("u_record_source"),
        "u_rejection_reason": item.get("u_rejection_reason"),
        "u_related_cfs_instances": item.get("u_related_cfs_instances"),
        "u_related_cfs_orders": item.get("u_related_cfs_orders"),
        "u_related_rfs_instances": item.get("u_related_rfs_instances"),
        "u_related_rfs_orders": item.get("u_related_rfs_orders"),
        "u_router_interface": item.get("u_router_interface"),
        "u_router_name": item.get("u_router_name"),
        "u_router_slot": item.get("u_router_slot"),
        "u_router_sub_interface": item.get("u_router_sub_interface"),
        "u_routing_protocol": item.get("u_routing_protocol"),
        "u_service_data_correctness": item.get("u_service_data_correctness"),
        "u_service_domain": item.get("u_service_domain"),
        "u_service_group": item.get("u_service_group"),
        "u_service_instance_id": item.get("u_service_instance_id"),
        "u_service_number": item.get("u_service_number"),
        "u_service_type": item.get("u_service_type"),
        "u_set_value_flow_status": item.get("u_set_value_flow_status"),
        "u_singnet_indicator": item.get("u_singnet_indicator"),
        "u_singtel_wan_ipv4_address": item.get("u_singtel_wan_ipv4_address"),
        "u_singtel_wan_ipv6_address": item.get("u_singtel_wan_ipv6_address"),
        "u_slot": item.get("u_slot"),
        "u_snapshot_state": item.get("u_snapshot_state"),
        "u_standard_class_dscp_value": item.get("u_standard_class_dscp_value"),
        "u_standard_class_ipp_value": item.get("u_standard_class_ipp_value"),
        "u_static_lan_ip_addresses": item.get("u_static_lan_ip_addresses"),
        "u_status": item.get("u_status"),
        "u_svlan_inner_vlan_id": item.get("u_svlan_inner_vlan_id"),
        "u_tariff_codes": item.get("u_tariff_codes"),
        "u_terminating_llc_partner_name": item.get("u_terminating_llc_partner_name"),
        "u_terminating_llc_partner_reference": item.get("u_terminating_llc_partner_reference"),
        "u_terminating_pegasus_np_service_number": item.get("u_terminating_pegasus_np_service_number"),
        "u_terminating_work_order_number": item.get("u_terminating_work_order_number"),
        "u_test_results": item.get("u_test_results"),
        "u_tina_cfs_order_number": item.get("u_tina_cfs_order_number"),
        "u_validation_result": item.get("u_validation_result"),
        "u_vlan_id": item.get("u_vlan_id"),
        "u_vpn_group": item.get("u_vpn_group"),
        "u_vpn_group_id": item.get("u_vpn_group_id"),
        "u_vpn_short_name": item.get("u_vpn_short_name"),
        "u_vrf_name": item.get("u_vrf_name"),
        "u_wan_ipv4_subnet_mask": item.get("u_wan_ipv4_subnet_mask"),
        "u_wan_ipv6_subnet_mask": item.get("u_wan_ipv6_subnet_mask"),
        "u_wholesale": item.get("u_wholesale"),
        "u_originated_by": item.get("u_originated_by"),
        "u_used_by": item.get("u_used_by"),
        # --- custom fields (Integer/Long) ---
        "u_additional_speed": item.get("u_additional_speed"),
        "u_as_prepend": item.get("u_as_prepend"),
        "u_bfd_minimal_interval": item.get("u_bfd_minimal_interval"),
        "u_bfd_multiplier": item.get("u_bfd_multiplier"),
        "u_dummy_speed": item.get("u_dummy_speed"),
        "u_install_charges": item.get("u_install_charges"),
        "u_local_preference": item.get("u_local_preference"),
        "u_network_product_instance_id": item.get("u_network_product_instance_id"),
        "u_original": item.get("u_original"),
        "u_original_speed": item.get("u_original_speed"),
        "u_speed_bps": item.get("u_speed_bps"),
        # --- custom fields (Boolean) ---
        "u_is_preconfigured_object": item.get("u_is_preconfigured_object"),
        "u_wip_object": item.get("u_wip_object"),
    }


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------
@mcp.tool()
def list_elite_ipvpn_cfs_instances(
    limit: int = Field(10, description="Maximum number of eLite IPVPN CFS Instances to return"),
    offset: int = Field(0, description="Offset for pagination"),
    name: Optional[str] = Field(None, description="Filter by name (contains). The record name includes the service number, e.g. 'eLite IPVPN CFS Instance #00199566SNG'. Pass the service number here to find the matching instance."),
    number: Optional[str] = Field(None, description="Filter by number"),
    u_service_number: Optional[str] = Field(None, description="Filter by Service Number (e.g. 00199566SNG). Use this to find a CFS instance by its service number."),
    u_customer_name: Optional[str] = Field(None, description="Filter by Customer Name (contains)"),
    u_status: Optional[str] = Field(None, description="Filter by Status"),
    u_activation_status: Optional[str] = Field(None, description="Filter by Activation Status"),
    u_flow_status: Optional[str] = Field(None, description="Filter by Flow Status"),
    u_service_type: Optional[str] = Field(None, description="Filter by Service Type"),
    u_circuit_type: Optional[str] = Field(None, description="Filter by Circuit Type"),
    u_routing_protocol: Optional[str] = Field(None, description="Filter by Routing Protocol"),
    u_order_from: Optional[str] = Field(None, description="Filter by Order From"),
    assigned_to: Optional[str] = Field(None, description="Filter by assigned user"),
    assignment_group: Optional[str] = Field(None, description="Filter by assignment group"),
    company: Optional[str] = Field(None, description="Filter by company"),
    install_status: Optional[str] = Field(None, description="Filter by install status"),
    operational_status: Optional[str] = Field(None, description="Filter by operational status"),
    query: Optional[str] = Field(None, description="Encoded query string for advanced filtering"),
) -> str:
    """List eLite IPVPN CFS Instance records from ServiceNow.

    Use this tool to search for eLite IPVPN CFS service instances. You can filter by:
    - Service number (u_service_number, e.g. 00199566SNG) — use this when a user provides a service number
    - Name (contains the service number in the format 'eLite IPVPN CFS Instance #<service_number>')
    - Customer name, routing protocol, activation status, service type, etc.

    Use get_elite_ipvpn_cfs_instance to retrieve full details including service correctness
    (u_service_data_correctness), VPN group, RFS links, IP addresses, and all service parameters.
    """
    config = get_config()
    auth_manager = get_auth_manager()

    try:
        url = f"{config.api_url}/table/{ELITE_IPVPN_CFS_INSTANCE_TABLE}"

        query_params = {
            "sysparm_limit": str(limit),
            "sysparm_offset": str(offset),
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
            "sysparm_fields": ELITE_IPVPN_CFS_INSTANCE_FIELDS,
        }

        query_parts: list[str] = []
        if name:
            query_parts.append(f"nameLIKE{name}")
        if number:
            query_parts.append(f"number={number}")
        if u_service_number:
            query_parts.append(f"u_service_number={u_service_number}")
        if u_customer_name:
            query_parts.append(f"u_customer_nameLIKE{u_customer_name}")
        if u_status:
            query_parts.append(f"u_status={u_status}")
        if u_activation_status:
            query_parts.append(f"u_activation_status={u_activation_status}")
        if u_flow_status:
            query_parts.append(f"u_flow_status={u_flow_status}")
        if u_service_type:
            query_parts.append(f"u_service_type={u_service_type}")
        if u_circuit_type:
            query_parts.append(f"u_circuit_type={u_circuit_type}")
        if u_routing_protocol:
            query_parts.append(f"u_routing_protocol={u_routing_protocol}")
        if u_order_from:
            query_parts.append(f"u_order_from={u_order_from}")
        if assigned_to:
            query_parts.append(f"assigned_to={assigned_to}")
        if assignment_group:
            query_parts.append(f"assignment_group={assignment_group}")
        if company:
            query_parts.append(f"company={company}")
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
        instances = [_parse_elite_ipvpn_cfs_instance(item) for item in data.get("result", [])]

        return format_list_response(instances, "elite_ipvpn_cfs_instances", limit, offset)

    except Exception as e:
        logger.error(f"Error listing eLite IPVPN CFS Instances: {e}")
        return format_error_response("list eLite IPVPN CFS Instances", e)


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------
@mcp.tool()
def get_elite_ipvpn_cfs_instance(
    instance_id: str = Field(
        ..., description="eLite IPVPN CFS Instance sys_id, name, or service number (e.g. 00199566SNG)"
    ),
) -> str:
    """Get a specific eLite IPVPN CFS Instance record from ServiceNow by sys_id, name, or service number.

    Use this tool to:
    - Look up a service instance by its service number (e.g. 00199566SNG)
    - Check service correctness (u_service_data_correctness)
    - View activation status, flow status, routing protocol, VPN group, VRF name
    - Check linked RFS instances, IP addresses (WAN/LAN), bandwidth, hub/spoke role
    - Review incorrectness reason (u_incorrectness_reason) and validation result

    The instance_id can be a sys_id, the full record name, or just the service number.
    """
    config = get_config()
    auth_manager = get_auth_manager()

    try:
        query_params = {
            "sysparm_display_value": "true",
            "sysparm_exclude_reference_link": "true",
            "sysparm_fields": ELITE_IPVPN_CFS_INSTANCE_FIELDS,
        }

        if is_sys_id(instance_id):
            url = f"{config.api_url}/table/{ELITE_IPVPN_CFS_INSTANCE_TABLE}/{instance_id}"
        else:
            url = f"{config.api_url}/table/{ELITE_IPVPN_CFS_INSTANCE_TABLE}"
            # Resolve by exact name, number, service number, or name containing the value
            query_params["sysparm_query"] = (
                f"name={instance_id}"
                f"^ORnumber={instance_id}"
                f"^ORu_service_number={instance_id}"
                f"^ORnameLIKE{instance_id}"
            )
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
            return f"eLite IPVPN CFS Instance not found: {instance_id}"

        result = data["result"]
        if isinstance(result, list):
            if not result:
                return f"eLite IPVPN CFS Instance not found: {instance_id}"
            item = result[0]
        else:
            item = result

        instance = _parse_elite_ipvpn_cfs_instance(item)

        return format_success_response(
            f"Found eLite IPVPN CFS Instance: {item.get('name')}",
            elite_ipvpn_cfs_instance=instance,
        )

    except Exception as e:
        logger.error(f"Error getting eLite IPVPN CFS Instance: {e}")
        return format_error_response("get eLite IPVPN CFS Instance", e)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
@mcp.tool()
def update_elite_ipvpn_cfs_instance(
    instance_id: str = Field(..., description="eLite IPVPN CFS Instance sys_id, name, or number"),
    # --- inherited cmdb_ci fields ---
    name: Optional[str] = Field(None, description="Name"),
    short_description: Optional[str] = Field(None, description="Short description"),
    comments: Optional[str] = Field(None, description="Additional comments"),
    category: Optional[str] = Field(None, description="Category"),
    subcategory: Optional[str] = Field(None, description="Subcategory"),
    ip_address: Optional[str] = Field(None, description="IP address"),
    assigned_to: Optional[str] = Field(None, description="Assigned to (sys_id or display value)"),
    assignment_group: Optional[str] = Field(None, description="Assignment group (sys_id or display value)"),
    install_status: Optional[str] = Field(None, description="Install status"),
    operational_status: Optional[str] = Field(None, description="Operational status"),
    environment: Optional[str] = Field(None, description="Environment"),
    company: Optional[str] = Field(None, description="Company (sys_id or display value)"),
    location: Optional[str] = Field(None, description="Location (sys_id or display value)"),
    # --- custom fields (String/Choice) ---
    u_activation_status: Optional[str] = Field(None, description="Activation Status"),
    u_as_override: Optional[str] = Field(None, description="AS Override"),
    u_authorized_installer: Optional[str] = Field(None, description="Authorized Installer"),
    u_backup_port_speed_duplex: Optional[str] = Field(None, description="Backup Port Speed/Duplex"),
    u_backup_type: Optional[str] = Field(None, description="Backup Type"),
    u_bandwidth: Optional[str] = Field(None, description="Bandwidth"),
    u_bgp_autonomous_system_number: Optional[str] = Field(None, description="BGP Autonomous System Number"),
    u_bgp_md5_ipv4_password: Optional[str] = Field(None, description="BGP MD5 IPv4 Password"),
    u_bgp_md5_ipv6_password: Optional[str] = Field(None, description="BGP MD5 IPv6 Password"),
    u_bgp_md5_password: Optional[str] = Field(None, description="BGP - MD5 Password"),
    u_bgp_number_of_prefixes: Optional[str] = Field(None, description="BGP Number of Prefixes"),
    u_bpj_evc_router_id: Optional[str] = Field(None, description="BPJ EVC Router ID"),
    u_circuit_scheme: Optional[str] = Field(None, description="Circuit Scheme"),
    u_circuit_tie: Optional[str] = Field(None, description="Circuit Tie"),
    u_circuit_type: Optional[str] = Field(None, description="Circuit Type"),
    u_component_id: Optional[str] = Field(None, description="Component ID"),
    u_component_name: Optional[str] = Field(None, description="Component Name"),
    u_cos_type: Optional[str] = Field(None, description="CoS Type"),
    u_cpe_model: Optional[str] = Field(None, description="CPE Model"),
    u_customer_location_b: Optional[str] = Field(None, description="Customer Location B"),
    u_customer_name: Optional[str] = Field(None, description="Customer Name"),
    u_customer_wan_ipv4_address: Optional[str] = Field(None, description="Customer WAN IPv4 Address"),
    u_customer_wan_ipv6_address: Optional[str] = Field(None, description="Customer WAN IPv6 Address"),
    u_customized_circuit: Optional[str] = Field(None, description="Customized Circuit"),
    u_discovery_status: Optional[str] = Field(None, description="Discovery Status"),
    u_display_message: Optional[str] = Field(None, description="Display Message"),
    u_email_address: Optional[str] = Field(None, description="Email Address"),
    u_encapsulation: Optional[str] = Field(None, description="Encapsulation"),
    u_enet_code: Optional[str] = Field(None, description="eNet Code"),
    u_externalid: Optional[str] = Field(None, description="ExternalID"),
    u_fiber_cable_1: Optional[str] = Field(None, description="Fiber Cable 1"),
    u_fiber_no_1: Optional[str] = Field(None, description="Fiber No 1"),
    u_fiber_system_name: Optional[str] = Field(None, description="Fiber System Name"),
    u_fibre_code: Optional[str] = Field(None, description="Fibre Code"),
    u_fibre_no: Optional[str] = Field(None, description="Fibre No"),
    u_flow_status: Optional[str] = Field(None, description="Flow Status"),
    u_hold_down_timer: Optional[str] = Field(None, description="Hold Down Timer"),
    u_hub_spoke: Optional[str] = Field(None, description="Hub/Spoke"),
    u_incorrectness_reason: Optional[str] = Field(None, description="Incorrectness Reason"),
    u_internet_framing_bytes: Optional[str] = Field(None, description="Internet Framing (Bytes)"),
    u_internet_protocol: Optional[str] = Field(None, description="Internet Protocol"),
    u_ipp_dscp: Optional[str] = Field(None, description="IPP/DSCP"),
    u_ipv4_lan_address: Optional[str] = Field(None, description="IPv4 LAN Address"),
    u_ipv6_lan_address: Optional[str] = Field(None, description="IPv6 LAN Address"),
    u_last_circuit_zendpoint: Optional[str] = Field(None, description="Last circuit ZEndPoint"),
    u_length_of_term: Optional[str] = Field(None, description="Length Of Term"),
    u_main_circuit_reference: Optional[str] = Field(None, description="Main Circuit Reference"),
    u_main_reference_no: Optional[str] = Field(None, description="Main Reference No"),
    u_megapop2_indicator: Optional[str] = Field(None, description="MegaPOP2 Indicator"),
    u_network_product_code: Optional[str] = Field(None, description="Network Product Code"),
    u_network_product_description: Optional[str] = Field(None, description="Network Product Description"),
    u_new_service_instance_name: Optional[str] = Field(None, description="New service instance name"),
    u_node_name: Optional[str] = Field(None, description="Node Name"),
    u_order_from: Optional[str] = Field(None, description="Order From"),
    u_originating_city_code: Optional[str] = Field(None, description="Originating City Code"),
    u_originating_llc_partner_name: Optional[str] = Field(None, description="Originating LLC Partner Name"),
    u_originating_llc_partner_reference: Optional[str] = Field(None, description="Originating LLC Partner Reference"),
    u_originating_pegasus_service_number: Optional[str] = Field(None, description="Originating Pegasus Service Number"),
    u_originating_pop_location: Optional[str] = Field(None, description="Originating POP Location"),
    u_originating_state: Optional[str] = Field(None, description="Originating State"),
    u_originating_work_order_number: Optional[str] = Field(None, description="Originating Work Order Number"),
    u_other_authorized_installer: Optional[str] = Field(None, description="Other Authorized Installer"),
    u_part_of_bundle: Optional[str] = Field(None, description="Part of Bundle"),
    u_port: Optional[str] = Field(None, description="Port"),
    u_port_mode: Optional[str] = Field(None, description="Port Mode"),
    u_port_no: Optional[str] = Field(None, description="Port No"),
    u_port_speed_duplex: Optional[str] = Field(None, description="Port Speed/Duplex"),
    u_proactive_monitoring: Optional[str] = Field(None, description="Proactive Monitoring"),
    u_product_code: Optional[str] = Field(None, description="Product Code"),
    u_project_code: Optional[str] = Field(None, description="Project Code"),
    u_project_no: Optional[str] = Field(None, description="Project No"),
    u_ptn_3900_multiplexer_port: Optional[str] = Field(None, description="PTN 3900 Multiplexer Port"),
    u_record_source: Optional[str] = Field(None, description="Record Source"),
    u_rejection_reason: Optional[str] = Field(None, description="Rejection Reason"),
    u_router_interface: Optional[str] = Field(None, description="Router Interface"),
    u_router_name: Optional[str] = Field(None, description="Router Name"),
    u_router_slot: Optional[str] = Field(None, description="Router - Slot"),
    u_router_sub_interface: Optional[str] = Field(None, description="Router Sub Interface"),
    u_routing_protocol: Optional[str] = Field(None, description="Routing Protocol"),
    u_service_data_correctness: Optional[str] = Field(None, description="Service Data Correctness"),
    u_service_domain: Optional[str] = Field(None, description="Service Domain"),
    u_service_group: Optional[str] = Field(None, description="Service Group"),
    u_service_instance_id: Optional[str] = Field(None, description="Service Instance ID"),
    u_service_number: Optional[str] = Field(None, description="Service Number"),
    u_service_type: Optional[str] = Field(None, description="Service Type"),
    u_set_value_flow_status: Optional[str] = Field(None, description="Set value flow status"),
    u_singnet_indicator: Optional[str] = Field(None, description="SingNet Indicator"),
    u_singtel_wan_ipv4_address: Optional[str] = Field(None, description="SingTel WAN IPv4 Address"),
    u_singtel_wan_ipv6_address: Optional[str] = Field(None, description="SingTel WAN IPv6 Address"),
    u_slot: Optional[str] = Field(None, description="Slot"),
    u_snapshot_state: Optional[str] = Field(None, description="Snapshot State"),
    u_standard_class_dscp_value: Optional[str] = Field(None, description="Standard Class DSCP Value"),
    u_standard_class_ipp_value: Optional[str] = Field(None, description="Standard Class IPP Value"),
    u_static_lan_ip_addresses: Optional[str] = Field(None, description="Static LAN IP Addresses"),
    u_status: Optional[str] = Field(None, description="Status"),
    u_svlan_inner_vlan_id: Optional[str] = Field(None, description="SVLAN/Inner VLAN ID"),
    u_tariff_codes: Optional[str] = Field(None, description="Tariff Codes"),
    u_terminating_llc_partner_name: Optional[str] = Field(None, description="Terminating LLC Partner Name"),
    u_terminating_llc_partner_reference: Optional[str] = Field(None, description="Terminating LLC Partner reference"),
    u_terminating_pegasus_np_service_number: Optional[str] = Field(None, description="Terminating Pegasus NP Service Number"),
    u_terminating_work_order_number: Optional[str] = Field(None, description="Terminating Work Order Number"),
    u_test_results: Optional[str] = Field(None, description="Test Results"),
    u_tina_cfs_order_number: Optional[str] = Field(None, description="TINA CFS Order Number"),
    u_validation_result: Optional[str] = Field(None, description="Validation Result"),
    u_vlan_id: Optional[str] = Field(None, description="VLAN ID"),
    u_vpn_group: Optional[str] = Field(None, description="VPN Group"),
    u_vpn_group_id: Optional[str] = Field(None, description="VPN Group ID"),
    u_vpn_short_name: Optional[str] = Field(None, description="VPN Short Name"),
    u_vrf_name: Optional[str] = Field(None, description="VRF Name"),
    u_wan_ipv4_subnet_mask: Optional[str] = Field(None, description="WAN IPv4 Subnet Mask"),
    u_wan_ipv6_subnet_mask: Optional[str] = Field(None, description="WAN IPv6 Subnet Mask"),
    u_wholesale: Optional[str] = Field(None, description="Wholesale"),
    # --- custom fields (Reference) ---
    u_activation_assignee: Optional[str] = Field(None, description="Activation Assignee (sys_id or display value)"),
    u_activation_process: Optional[str] = Field(None, description="Activation Process (sys_id or display value)"),
    u_cfs_instance: Optional[str] = Field(None, description="CFS Instance (sys_id or display value)"),
    u_component_instance: Optional[str] = Field(None, description="Component Instance (sys_id or display value)"),
    u_component_specification: Optional[str] = Field(None, description="Component Specification (sys_id or display value)"),
    u_configuration_assignee: Optional[str] = Field(None, description="Configuration Assignee (sys_id or display value)"),
    u_contact_details: Optional[str] = Field(None, description="Contact Details (sys_id or display value)"),
    u_coordination_assignee: Optional[str] = Field(None, description="Coordination Assignee (sys_id or display value)"),
    u_customer_account: Optional[str] = Field(None, description="Customer Account (sys_id or display value)"),
    u_customer_location_a: Optional[str] = Field(None, description="Customer Location A (sys_id or display value)"),
    u_inner_vlan: Optional[str] = Field(None, description="Inner VLAN (sys_id or display value)"),
    u_l3_vpn: Optional[str] = Field(None, description="L3 VPN (sys_id or display value)"),
    u_main_circuit_cfs_instance: Optional[str] = Field(None, description="Main Circuit CFS Instance (sys_id or display value)"),
    u_main_circuit_cfs_order: Optional[str] = Field(None, description="Main Circuit CFS Order (sys_id or display value)"),
    u_managed_service_cfs_instance: Optional[str] = Field(None, description="Managed Service CFS Instance (sys_id or display value)"),
    u_managed_service_cfs_order: Optional[str] = Field(None, description="Managed Service CFS Order (sys_id or display value)"),
    u_network_product: Optional[str] = Field(None, description="Network Product (sys_id or display value)"),
    u_originating_city: Optional[str] = Field(None, description="Originating City (sys_id or display value)"),
    u_originating_country: Optional[str] = Field(None, description="Originating Country (sys_id or display value)"),
    u_originating_location: Optional[str] = Field(None, description="Originating Location (sys_id or display value)"),
    u_outer_vlan: Optional[str] = Field(None, description="Outer VLAN (sys_id or display value)"),
    u_parent_network_element: Optional[str] = Field(None, description="Parent Network Element (sys_id or display value)"),
    u_parent_ri_object: Optional[str] = Field(None, description="Parent RI Object (sys_id or display value)"),
    u_specification: Optional[str] = Field(None, description="CFS Specification (sys_id or display value)"),
    u_terminating_location: Optional[str] = Field(None, description="Terminating Location (sys_id or display value)"),
    u_terminating_pop_location: Optional[str] = Field(None, description="Terminating POP Location (sys_id or display value)"),
    u_tina_cfs_order: Optional[str] = Field(None, description="TINA CFS Order (sys_id or display value)"),
    u_tina_rfs_order: Optional[str] = Field(None, description="TINA RFS Order (sys_id or display value)"),
    u_vpn_sites: Optional[str] = Field(None, description="VPN Sites (sys_id or display value)"),
    u_wip_of: Optional[str] = Field(None, description="WIP Of (sys_id or display value)"),
    u_wip_ref: Optional[str] = Field(None, description="WIP Ref (sys_id or display value)"),
    # --- custom fields (Integer) ---
    u_additional_speed: Optional[int] = Field(None, description="Additional Speed"),
    u_as_prepend: Optional[int] = Field(None, description="AS Prepend"),
    u_bfd_minimal_interval: Optional[int] = Field(None, description="BFD Minimal Interval"),
    u_bfd_multiplier: Optional[int] = Field(None, description="BFD Multiplier"),
    u_dummy_speed: Optional[int] = Field(None, description="Dummy Speed"),
    u_install_charges: Optional[int] = Field(None, description="Install Charges, $"),
    u_local_preference: Optional[int] = Field(None, description="Local Preference"),
    u_network_product_instance_id: Optional[int] = Field(None, description="Network Product Instance ID"),
    u_original: Optional[int] = Field(None, description="Original"),
    u_original_speed: Optional[int] = Field(None, description="Original Speed"),
    u_speed_bps: Optional[int] = Field(None, description="Speed (bps)"),
    # --- custom fields (Boolean) ---
    u_is_preconfigured_object: Optional[bool] = Field(None, description="Is Preconfigured Object"),    u_wip_object: Optional[bool] = Field(None, description="WIP Object"),
) -> str:
    """Update an existing eLite IPVPN CFS Instance record in ServiceNow.

    Use this tool to update fields on an eLite IPVPN CFS service instance, including:
    - Service correctness: u_service_data_correctness, u_incorrectness_reason, u_validation_result
    - Status fields: u_activation_status, u_flow_status, u_status, operational_status
    - Service parameters: routing protocol, VPN group, VRF name, bandwidth, IP addresses
    - The instance_id can be a sys_id, full name, or service number (e.g. 00199566SNG)
    """
    config = get_config()
    auth_manager = get_auth_manager()    # Resolve to sys_id if a name or number was provided
    sys_id_to_update = instance_id
    if not is_sys_id(instance_id):
        search_url = f"{config.api_url}/table/{ELITE_IPVPN_CFS_INSTANCE_TABLE}"
        search_params = {
            "sysparm_query": (
                f"name={instance_id}"
                f"^ORnumber={instance_id}"
                f"^ORu_service_number={instance_id}"
                f"^ORnameLIKE{instance_id}"
            ),
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
                return f"eLite IPVPN CFS Instance not found: {instance_id}"
            sys_id_to_update = s_res[0]["sys_id"]
        except Exception as e:
            return f"Error resolving eLite IPVPN CFS Instance ID: {str(e)}"

    url = f"{config.api_url}/table/{ELITE_IPVPN_CFS_INSTANCE_TABLE}/{sys_id_to_update}"

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
        # custom fields (String/Choice)
        "u_activation_status": u_activation_status,
        "u_as_override": u_as_override,
        "u_authorized_installer": u_authorized_installer,
        "u_backup_port_speed_duplex": u_backup_port_speed_duplex,
        "u_backup_type": u_backup_type,
        "u_bandwidth": u_bandwidth,
        "u_bgp_autonomous_system_number": u_bgp_autonomous_system_number,
        "u_bgp_md5_ipv4_password": u_bgp_md5_ipv4_password,
        "u_bgp_md5_ipv6_password": u_bgp_md5_ipv6_password,
        "u_bgp_md5_password": u_bgp_md5_password,
        "u_bgp_number_of_prefixes": u_bgp_number_of_prefixes,
        "u_bpj_evc_router_id": u_bpj_evc_router_id,
        "u_circuit_scheme": u_circuit_scheme,
        "u_circuit_tie": u_circuit_tie,
        "u_circuit_type": u_circuit_type,
        "u_component_id": u_component_id,
        "u_component_name": u_component_name,
        "u_cos_type": u_cos_type,
        "u_cpe_model": u_cpe_model,
        "u_customer_location_b": u_customer_location_b,
        "u_customer_name": u_customer_name,
        "u_customer_wan_ipv4_address": u_customer_wan_ipv4_address,
        "u_customer_wan_ipv6_address": u_customer_wan_ipv6_address,
        "u_customized_circuit": u_customized_circuit,
        "u_discovery_status": u_discovery_status,
        "u_display_message": u_display_message,
        "u_email_address": u_email_address,
        "u_encapsulation": u_encapsulation,
        "u_enet_code": u_enet_code,
        "u_externalid": u_externalid,
        "u_fiber_cable_1": u_fiber_cable_1,
        "u_fiber_no_1": u_fiber_no_1,
        "u_fiber_system_name": u_fiber_system_name,
        "u_fibre_code": u_fibre_code,
        "u_fibre_no": u_fibre_no,
        "u_flow_status": u_flow_status,
        "u_hold_down_timer": u_hold_down_timer,
        "u_hub_spoke": u_hub_spoke,
        "u_incorrectness_reason": u_incorrectness_reason,
        "u_internet_framing_bytes": u_internet_framing_bytes,
        "u_internet_protocol": u_internet_protocol,
        "u_ipp_dscp": u_ipp_dscp,
        "u_ipv4_lan_address": u_ipv4_lan_address,
        "u_ipv6_lan_address": u_ipv6_lan_address,
        "u_last_circuit_zendpoint": u_last_circuit_zendpoint,
        "u_length_of_term": u_length_of_term,
        "u_main_circuit_reference": u_main_circuit_reference,
        "u_main_reference_no": u_main_reference_no,
        "u_megapop2_indicator": u_megapop2_indicator,
        "u_network_product_code": u_network_product_code,
        "u_network_product_description": u_network_product_description,
        "u_new_service_instance_name": u_new_service_instance_name,
        "u_node_name": u_node_name,
        "u_order_from": u_order_from,
        "u_originating_city_code": u_originating_city_code,
        "u_originating_llc_partner_name": u_originating_llc_partner_name,
        "u_originating_llc_partner_reference": u_originating_llc_partner_reference,
        "u_originating_pegasus_service_number": u_originating_pegasus_service_number,
        "u_originating_pop_location": u_originating_pop_location,
        "u_originating_state": u_originating_state,
        "u_originating_work_order_number": u_originating_work_order_number,
        "u_other_authorized_installer": u_other_authorized_installer,
        "u_part_of_bundle": u_part_of_bundle,
        "u_port": u_port,
        "u_port_mode": u_port_mode,
        "u_port_no": u_port_no,
        "u_port_speed_duplex": u_port_speed_duplex,
        "u_proactive_monitoring": u_proactive_monitoring,
        "u_product_code": u_product_code,
        "u_project_code": u_project_code,
        "u_project_no": u_project_no,
        "u_ptn_3900_multiplexer_port": u_ptn_3900_multiplexer_port,
        "u_record_source": u_record_source,
        "u_rejection_reason": u_rejection_reason,
        "u_router_interface": u_router_interface,
        "u_router_name": u_router_name,
        "u_router_slot": u_router_slot,
        "u_router_sub_interface": u_router_sub_interface,
        "u_routing_protocol": u_routing_protocol,
        "u_service_data_correctness": u_service_data_correctness,
        "u_service_domain": u_service_domain,
        "u_service_group": u_service_group,
        "u_service_instance_id": u_service_instance_id,
        "u_service_number": u_service_number,
        "u_service_type": u_service_type,
        "u_set_value_flow_status": u_set_value_flow_status,
        "u_singnet_indicator": u_singnet_indicator,
        "u_singtel_wan_ipv4_address": u_singtel_wan_ipv4_address,
        "u_singtel_wan_ipv6_address": u_singtel_wan_ipv6_address,
        "u_slot": u_slot,
        "u_snapshot_state": u_snapshot_state,
        "u_standard_class_dscp_value": u_standard_class_dscp_value,
        "u_standard_class_ipp_value": u_standard_class_ipp_value,
        "u_static_lan_ip_addresses": u_static_lan_ip_addresses,
        "u_status": u_status,
        "u_svlan_inner_vlan_id": u_svlan_inner_vlan_id,
        "u_tariff_codes": u_tariff_codes,
        "u_terminating_llc_partner_name": u_terminating_llc_partner_name,
        "u_terminating_llc_partner_reference": u_terminating_llc_partner_reference,
        "u_terminating_pegasus_np_service_number": u_terminating_pegasus_np_service_number,
        "u_terminating_work_order_number": u_terminating_work_order_number,
        "u_test_results": u_test_results,
        "u_tina_cfs_order_number": u_tina_cfs_order_number,
        "u_validation_result": u_validation_result,
        "u_vlan_id": u_vlan_id,
        "u_vpn_group": u_vpn_group,
        "u_vpn_group_id": u_vpn_group_id,
        "u_vpn_short_name": u_vpn_short_name,
        "u_vrf_name": u_vrf_name,
        "u_wan_ipv4_subnet_mask": u_wan_ipv4_subnet_mask,
        "u_wan_ipv6_subnet_mask": u_wan_ipv6_subnet_mask,
        "u_wholesale": u_wholesale,
        # custom fields (Reference)
        "u_activation_assignee": u_activation_assignee,
        "u_activation_process": u_activation_process,
        "u_cfs_instance": u_cfs_instance,
        "u_component_instance": u_component_instance,
        "u_component_specification": u_component_specification,
        "u_configuration_assignee": u_configuration_assignee,
        "u_contact_details": u_contact_details,
        "u_coordination_assignee": u_coordination_assignee,
        "u_customer_account": u_customer_account,
        "u_customer_location_a": u_customer_location_a,
        "u_inner_vlan": u_inner_vlan,
        "u_l3_vpn": u_l3_vpn,
        "u_main_circuit_cfs_instance": u_main_circuit_cfs_instance,
        "u_main_circuit_cfs_order": u_main_circuit_cfs_order,
        "u_managed_service_cfs_instance": u_managed_service_cfs_instance,
        "u_managed_service_cfs_order": u_managed_service_cfs_order,
        "u_network_product": u_network_product,
        "u_originating_city": u_originating_city,
        "u_originating_country": u_originating_country,
        "u_originating_location": u_originating_location,
        "u_outer_vlan": u_outer_vlan,
        "u_parent_network_element": u_parent_network_element,
        "u_parent_ri_object": u_parent_ri_object,
        "u_specification": u_specification,
        "u_terminating_location": u_terminating_location,
        "u_terminating_pop_location": u_terminating_pop_location,
        "u_tina_cfs_order": u_tina_cfs_order,
        "u_tina_rfs_order": u_tina_rfs_order,
        "u_vpn_sites": u_vpn_sites,
        "u_wip_of": u_wip_of,
        "u_wip_ref": u_wip_ref,
    }

    for key, value in field_map.items():
        if value is not None:
            body[key] = value

    # Handle integer fields
    int_fields = {
        "u_additional_speed": u_additional_speed,
        "u_as_prepend": u_as_prepend,
        "u_bfd_minimal_interval": u_bfd_minimal_interval,
        "u_bfd_multiplier": u_bfd_multiplier,
        "u_dummy_speed": u_dummy_speed,
        "u_install_charges": u_install_charges,
        "u_local_preference": u_local_preference,
        "u_network_product_instance_id": u_network_product_instance_id,
        "u_original": u_original,
        "u_original_speed": u_original_speed,
        "u_speed_bps": u_speed_bps,
    }
    for key, value in int_fields.items():
        if value is not None:
            body[key] = str(value)

    # Handle boolean fields
    if u_is_preconfigured_object is not None:
        body["u_is_preconfigured_object"] = str(u_is_preconfigured_object).lower()
    if u_wip_object is not None:
        body["u_wip_object"] = str(u_wip_object).lower()

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
            return "Failed to update eLite IPVPN CFS Instance"

        result = data["result"]
        return format_success_response(
            f"eLite IPVPN CFS Instance updated successfully: {result.get('name')}",
            sys_id=result.get("sys_id"),
            name=result.get("name"),
        )

    except Exception as e:
        logger.error(f"Error updating eLite IPVPN CFS Instance: {e}")
        return format_error_response("update eLite IPVPN CFS Instance", e)
