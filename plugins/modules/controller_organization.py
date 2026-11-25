#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: controller_organization
author: Red Hat (@RedHatOfficial)
short_description: Manage Controller-owned organization settings
description:
  - Update Controller-specific fields and associations for an existing logical organization.
options:
  name:
    description:
      - Controller organization name.
    required: true
    type: str
  description:
    description:
      - Controller organization description.
    type: str
  max_hosts:
    description:
      - Maximum number of hosts allowed in the organization.
    type: int
  default_environment:
    description:
      - Default execution environment name or ID.
    type: str
  galaxy_credentials:
    description:
      - Galaxy credential names or IDs associated with the organization.
    type: list
    elements: str
  instance_groups:
    description:
      - Instance-group names or IDs associated with the organization.
    type: list
    elements: str
  opa_query_path:
    description:
      - OPA policy query path evaluated before job execution.
    type: str
  new_name:
    description:
      - New Controller organization name.
    type: str
  state:
    description:
      - Desired state of the Controller organization overlay.
    type: str
    choices: [present, exists]
    default: present
extends_documentation_fragment:
  - ansible.platform.auth
  - ansible.platform.state
"""

EXAMPLES = """
- name: Apply Controller organization settings
  ansible.platform.controller_organization:
    name: Engineering
    max_hosts: 100
    default_environment: Default execution environment
    state: present

- name: Check Controller organization settings
  ansible.platform.controller_organization:
    name: Engineering
    state: exists
...
"""

RETURN = """
changed:
  description: Whether the Controller organization overlay was updated.
  returned: always
  type: bool

controller_organization:
  description: >
    The Controller organization resource after the operation.
  returned: when state is present or exists
  type: dict
  contains:
    id:
      description: Numeric database ID of the Controller organization.
      type: int
    name:
      description: Name of the Controller organization.
      type: str
...
"""
