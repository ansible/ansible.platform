#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/host.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: host
author: Red Hat (@RedHatOfficial)
short_description: Create, update, or destroy Automation Platform Controller hosts
description:
  - Create, update, or destroy Automation Platform Controller hosts.
version_added: "3.0.0"

options:
  name:
    description:
      - The name to use for the host.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field).
    type: str

  description:
    description:
      - The description to use for the host.
    type: str

  inventory:
    description:
      - Inventory name, ID, or named URL the host should be made a member of.
    required: true
    type: str

  enabled:
    description:
      - If the host should be enabled.
    type: bool

  instance_id:
    description:
      - The instance ID for cloud-provided hosts.
    type: str

  variables:
    description:
      - Variables to use for the host.
    type: dict

  state:
    description:
      - Desired state of the host.
      - C(present) ensures the host exists (create or update); idempotent.
      - C(absent) removes the host; idempotent if already absent.
      - C(exists) reads and returns the current host (no change).
    type: str
    choices: ['present', 'absent', 'exists', 'enforced']
    default: 'present'

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth

seealso:
  - module: ansible.controller.host
  - module: awx.awx.host
"""

EXAMPLES = """
- name: Add host
  ansible.platform.host:
    name: localhost
    description: "Local Host"
    inventory: "Local Inventory"
    state: present
    variables:
      example_var: 123

- name: Check whether a host exists (no change)
  ansible.platform.host:
    name: localhost
    inventory: "Local Inventory"
    state: exists

- name: Delete a host
  ansible.platform.host:
    name: localhost
    inventory: "Local Inventory"
    state: absent
...
"""

RETURN = """
changed:
  description: Whether the host was created, updated, or deleted.
  returned: always
  type: bool

host:
  description: >
    The host resource as it exists after the operation.
    Contains only the fields accepted as module input (argspec fields) plus C(id).
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the host.
      type: int
    name:
      description: Name of the host.
      type: str
    inventory:
      description: ID of the inventory the host belongs to.
      type: int
    enabled:
      description: Whether the host is enabled.
      type: bool
    variables:
      description: Host variables.
      type: dict
...
"""
