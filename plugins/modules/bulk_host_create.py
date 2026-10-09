#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2025, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/bulk_host_create.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: bulk_host_create
author: Red Hat (@RedHatOfficial)
short_description: Bulk create hosts in Automation Controller
description:
  - Create many hosts at once in an Automation Controller inventory via a single API request.
  - This is a non-idempotent operation — every invocation creates hosts (or overwrites
    existing hosts with the same name in the target inventory).
  - Migrated from the C(awx.awx.bulk_host_create) / C(ansible.controller.bulk_host_create) module.
version_added: "2.8.0"

options:
  inventory:
    description:
      - Inventory name, ID, or named URL to add hosts to.
    required: true
    type: str
  hosts:
    description:
      - List of hosts to create in the inventory.
    required: true
    type: list
    elements: dict
    suboptions:
      name:
        description:
          - The name to use for the host.
        type: str
        required: true
      description:
        description:
          - The description to use for the host.
        type: str
      enabled:
        description:
          - Whether the host should be enabled.
        type: bool
      variables:
        description:
          - Variables to use for the host.
        type: dict
      instance_id:
        description:
          - Instance ID to use for the host.
        type: str

seealso:
  - module: ansible.controller.bulk_host_create
  - module: awx.awx.bulk_host_create

extends_documentation_fragment:
  - ansible.platform.auth
"""

EXAMPLES = """
- name: Bulk create hosts in an inventory
  ansible.platform.bulk_host_create:
    inventory: "My Inventory"
    hosts:
      - name: host1.example.com
        description: "First host"
        enabled: true
        variables:
          ansible_host: 192.168.1.1
      - name: host2.example.com
        variables:
          ansible_host: 192.168.1.2

- name: Bulk create hosts by inventory ID
  ansible.platform.bulk_host_create:
    inventory: "42"
    hosts:
      - name: web1.example.com
      - name: web2.example.com
"""

RETURN = """
changed:
  description: Whether hosts were created.
  returned: always
  type: bool

response:
  description: The raw API response from the bulk host create endpoint.
  returned: success
  type: dict

hosts:
  description: The list of hosts that were submitted for creation.
  returned: always
  type: list
  elements: dict
"""
