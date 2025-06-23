#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2025, Pratyush Bhandari <@prbhanda>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type


DOCUMENTATION = """
---
module: ui_plugin_route
author: Pratyush Bhandari (@prbhanda)
short_description: Configure a gateway UI plugin route.
description:
    - Configure an automation platform gateway UI plugin route.
    - Their gateway paths have prefix /plugin/{cluster_name}/{ui_plugin_path}/
    - Authentication is handled by the parent service, not the plugin route itself.
options:
    name:
      required: true
      type: str
      description: The name of the UI Plugin Route, must be unique
    new_name:
      type: str
      description: Setting this option will change the existing name (looked up via the name field)
    description:
      description: The description of the UI Plugin Route
      type: str
    ui_plugin_path:
      description:
      - The relative path to the UI plugin on the service cluster
      - Required when creating a new UI plugin route
      - Will be auto-prefixed with /plugin/{cluster_name}/ to create the gateway_path
      - Leading and trailing slashes will be automatically stripped
      type: str
    http_port:
      description:
      - Name or ID referencing the Http Port
      - Required when creating a new UI plugin route
      type: str
    service_cluster:
      description:
      - Name or ID referencing the Service Cluster
      - Required when creating a new UI plugin route
      - Cannot be a Gateway type service cluster
      type: str
    is_service_https:
      description: Flag whether or not the service cluster uses https
      default: false
      type: bool
    service_port:
      description:
      - Port on the service cluster to route traffic to
      - Required when creating a new UI plugin route
      type: int
    node_tags:
      description:
      - Comma separated string
      - Selects which (tagged) nodes receive traffic from this route
      type: str
    order:
      description:
      - The order to apply the routes in; lower numbers are first. Items with the same value have no guaranteed order
      - Defaults to 50 when created
      type: int
notes:
    - The gateway_path, service_path, enable_gateway_auth, and is_internal_route fields are read-only and auto-generated.
    - UI plugin routes always have enable_gateway_auth=False and is_internal_route=False.
    - The service_path is automatically set to match the ui_plugin_path.

extends_documentation_fragment:
- ansible.platform.state
- ansible.platform.auth
"""

EXAMPLES = """
- name: Create UI plugin route
  ansible.platform.ui_plugin_route:
    name: EDA Dashboard Plugin
    description: Route to EDA dashboard plugin
    ui_plugin_path: "dashboard"
    http_port: "Port 8080"
    service_cluster: "EDA Cluster"
    is_service_https: false
    service_port: 8080
    order: 50
    # gateway_path will be auto-generated as: /plugin/eda-cluster/dashboard/

- name: Create UI plugin route with node tags
  ansible.platform.ui_plugin_route:
    name: Hub Plugin Route
    ui_plugin_path: "my-plugin"
    service_cluster: "Automation Hub"
    service_port: 8000
    node_tags: "frontend,plugin"

- name: Update UI plugin route
  ansible.platform.ui_plugin_route:
    name: EDA Dashboard Plugin
    service_port: 8081

- name: Check UI plugin route exists
  ansible.platform.ui_plugin_route:
    name: EDA Dashboard Plugin
    state: exists

- name: Delete UI plugin route
  ansible.platform.ui_plugin_route:
    name: EDA Dashboard Plugin
    state: absent
...
"""

from ..module_utils.aap_module import AAPModule
from ..module_utils.aap_ui_plugin_route import AAPUIPluginRoute


def main():
    argument_spec = dict(
        name=dict(type="str", required=True),
        new_name=dict(type="str"),
        description=dict(type="str"),
        ui_plugin_path=dict(type="str"),
        http_port=dict(type="str"),
        service_cluster=dict(type="str"),
        is_service_https=dict(type="bool", default=False),
        service_port=dict(type="int"),
        node_tags=dict(type="str"),
        order=dict(type="int"),
        # NOTE: gateway_path, service_path, enable_gateway_auth, is_internal_route are read-only
        state=dict(choices=["present", "absent", "exists", "enforced"], default="present"),
    )

    # Create a module with spec
    module = AAPModule(argument_spec=argument_spec, supports_check_mode=True)

    AAPUIPluginRoute(module).manage()


if __name__ == '__main__':
    main() 