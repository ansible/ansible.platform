#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/group.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: group
author: Red Hat (@RedHatOfficial)
short_description: Create, update, or destroy Automation Platform Controller groups
description:
  - Create, update, or destroy Automation Platform Controller inventory groups.
version_added: "3.0.0"

options:
  name:
    description:
      - The name to use for the group.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field).
    type: str

  description:
    description:
      - The description to use for the group.
    type: str

  inventory:
    description:
      - Inventory name, ID, or named URL that the group should be made a member of.
    required: true
    type: str

  variables:
    description:
      - Variables to use for the group.
    type: dict

  hosts:
    description:
      - List of host names, IDs, or named URLs that should be put in this group.
    type: list
    elements: str

  children:
    description:
      - List of group names, IDs, or named URLs that should be nested inside this group.
    type: list
    elements: str
    aliases:
      - groups

  preserve_existing_hosts:
    description:
      - Preserve existing hosts in an existing group instead of overwriting them with C(hosts).
    default: false
    type: bool

  preserve_existing_children:
    description:
      - Preserve existing children in an existing group instead of overwriting them with C(children).
    default: false
    type: bool
    aliases:
      - preserve_existing_groups

  state:
    description:
      - Desired state of the group.
      - C(present) ensures the group exists (create or update); idempotent.
      - C(absent) removes the group; idempotent if already absent.
      - C(exists) reads and returns the current group (no change).
    type: str
    choices: ['present', 'absent', 'exists', 'enforced']
    default: 'present'

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth

notes:
  - Unlike the legacy module, C(hosts)/C(children) name lookups are not scoped
    by C(inventory) — host and group names are assumed unique. Use the
    numeric ID if this is a concern.

seealso:
  - module: ansible.controller.group
  - module: awx.awx.group
"""

EXAMPLES = """
- name: Add group
  ansible.platform.group:
    name: localhost
    description: "Local Host Group"
    inventory: "Local Inventory"
    state: present

- name: Add group with hosts and children
  ansible.platform.group:
    name: Cities
    description: "Local Host Group"
    inventory: Default Inventory
    hosts:
      - fda
    children:
      - NewYork
    preserve_existing_hosts: true
    preserve_existing_children: true

- name: Delete a group
  ansible.platform.group:
    name: Cities
    inventory: Default Inventory
    state: absent
...
"""

RETURN = """
changed:
  description: Whether the group was created, updated, or deleted.
  returned: always
  type: bool

group:
  description: >
    The group resource as it exists after the operation.
    Contains only the fields accepted as module input (argspec fields) plus C(id).
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the group.
      type: int
    name:
      description: Name of the group.
      type: str
    inventory:
      description: ID of the inventory the group belongs to.
      type: int
...
"""
