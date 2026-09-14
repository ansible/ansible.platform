#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/inventory.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: inventory
author: Red Hat (@RedHatOfficial)
short_description: Create, update, or destroy Automation Platform Controller inventories
description:
  - Create, update, or destroy Automation Platform Controller inventories.
version_added: "3.0.0"

options:
  name:
    description:
      - The name to use for the inventory.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field).
    type: str

  copy_from:
    description:
      - Name or ID to copy the inventory from.
      - This will copy an existing inventory and change any parameters supplied.
      - The new inventory name will be the one provided in the C(name) parameter.
      - The organization parameter is not used in this, to facilitate copy from one organization to another.
    type: str

  description:
    description:
      - The description to use for the inventory.
    type: str

  organization:
    description:
      - Organization name, ID, or named URL the inventory belongs to.
    required: true
    type: str

  variables:
    description:
      - Inventory variables.
    type: dict

  kind:
    description:
      - The kind field. Cannot be modified after created.
    choices: ["", "smart", "constructed"]
    type: str

  host_filter:
    description:
      - The host_filter field. Only useful when C(kind=smart).
    type: str

  opa_query_path:
    description:
      - The Open Policy Agent query path used to evaluate this inventory's policy.
    type: str

  instance_groups:
    description:
      - List of Instance Group names, IDs, or named URLs for this inventory to run on.
    type: list
    elements: str

  input_inventories:
    description:
      - List of Inventory names, IDs, or named URLs to use as input for a Constructed Inventory.
      - Only used when C(kind=constructed).
    type: list
    elements: str

  prevent_instance_group_fallback:
    description:
      - Prevent falling back to instance groups set on the organization.
    type: bool

  state:
    description:
      - Desired state of the inventory.
      - C(present) ensures the inventory exists (create or update); idempotent.
      - C(absent) removes the inventory; idempotent if already absent.
      - C(exists) reads and returns the current inventory (no change).
    type: str
    choices: ['present', 'absent', 'exists', 'enforced']
    default: 'present'

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth

seealso:
  - module: ansible.controller.inventory
  - module: awx.awx.inventory
"""

EXAMPLES = """
- name: Add inventory
  ansible.platform.inventory:
    name: "Foo Inventory"
    description: "Our Foo Cloud Servers"
    organization: "Bar Org"
    state: present

- name: Copy inventory
  ansible.platform.inventory:
    name: Copy Foo Inventory
    copy_from: Default Inventory
    description: "Our Foo Cloud Servers"
    organization: Foo
    state: present

- name: Add inventory with instance groups
  ansible.platform.inventory:
    name: Foo Inventory
    organization: Bar Org
    instance_groups:
      - group-a
      - group-b

# You can create and modify constructed inventories by creating an inventory
# of kind "constructed" and then editing the automatically generated inventory
# source for that inventory.
- name: Add constructed inventory with two existing input inventories
  ansible.platform.inventory:
    name: My Constructed Inventory
    organization: Default
    kind: constructed
    input_inventories:
      - "West Datacenter"
      - "East Datacenter"

- name: Check whether an inventory exists (no change)
  ansible.platform.inventory:
    name: Foo Inventory
    organization: Bar Org
    state: exists

- name: Delete an inventory
  ansible.platform.inventory:
    name: Foo Inventory
    organization: Bar Org
    state: absent
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
    Contains only the fields accepted as module input (argspec fields) plus C(id).
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the inventory.
      type: int
    name:
      description: Name of the inventory.
      type: str
    organization:
      description: ID of the organization the inventory belongs to.
      type: int
    kind:
      description: The kind of inventory.
      type: str
    variables:
      description: Inventory variables.
      type: dict
...
"""
