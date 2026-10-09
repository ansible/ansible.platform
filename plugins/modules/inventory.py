#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/inventory.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: inventory
author: Red Hat (@RedHatOfficial)
short_description: Manage Controller inventories
description:
  - Create, update, or delete inventories on Ansible Automation Platform Controller.
  - Supports regular, smart, and constructed inventory types.
  - Association endpoints (instance_groups, input_inventories) and copy_from
    are planned for a follow-up PR.
version_added: "2.8.0"

options:
  name:
    description:
      - The name of the inventory.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field).
    type: str

  description:
    description:
      - The description of the inventory.
    type: str

  organization:
    description:
      - Organization name or ID the inventory belongs to.
    required: true
    type: str

  kind:
    description:
      - The kind of inventory.
      - Cannot be modified after creation.
      - An empty string means a regular inventory.
    choices: ['', 'smart', 'constructed']
    type: str

  host_filter:
    description:
      - The host filter for smart inventories.
      - Only useful when C(kind=smart).
    type: str

  variables:
    description:
      - Inventory variables.
      - Accepts a YAML/JSON dictionary which will be serialized as a JSON string.
    type: dict

  prevent_instance_group_fallback:
    description:
      - Prevent falling back to instance groups set on the organization.
    type: bool

seealso:
  - module: ansible.controller.inventory
  - module: awx.awx.inventory

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Add a regular inventory
  ansible.platform.inventory:
    name: "Production Inventory"
    description: "Our production servers"
    organization: "Default"
    state: present

- name: Add a smart inventory
  ansible.platform.inventory:
    name: "Linux Hosts"
    organization: "Default"
    kind: smart
    host_filter: "ansible_os_family__icontains=RedHat"

- name: Add a constructed inventory
  ansible.platform.inventory:
    name: "My Constructed Inventory"
    organization: "Default"
    kind: constructed

- name: Rename an inventory
  ansible.platform.inventory:
    name: "Production Inventory"
    new_name: "Prod Inventory"
    organization: "Default"

- name: Delete an inventory
  ansible.platform.inventory:
    name: "Prod Inventory"
    organization: "Default"
    state: absent

- name: Check whether an inventory exists
  ansible.platform.inventory:
    name: "Production Inventory"
    organization: "Default"
    state: exists
  register: inv_check
...
"""

RETURN = """
changed:
  description: Whether the inventory was created, updated, or deleted.
  returned: always
  type: bool

inventory:
  description: >
    The inventory resource as it exists after the operation.
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the inventory.
      type: int
    name:
      description: Name of the inventory.
      type: str
    description:
      description: Description of the inventory.
      type: str
    organization:
      description: Organization the inventory belongs to (ID).
      type: int
    kind:
      description: The kind of inventory (empty string, smart, or constructed).
      type: str
    host_filter:
      description: Host filter for smart inventories.
      type: str
    variables:
      description: Inventory variables as a JSON string.
      type: str
    prevent_instance_group_fallback:
      description: Whether instance group fallback is prevented.
      type: bool
...
"""
