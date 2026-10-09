#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/group.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: group
author: Red Hat (@RedHatOfficial)
short_description: Manage Controller inventory groups
description:
  - Create, update, or delete inventory groups on Ansible Automation Platform Controller.
  - Groups belong to an inventory and can contain hosts and child groups.
  - Supports host and child group associations with optional preserve-existing behavior.
version_added: "2.8.0"

options:
  name:
    description:
      - The name of the group.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field).
    type: str

  description:
    description:
      - The description of the group.
    type: str

  inventory:
    description:
      - Inventory name or ID the group belongs to.
    required: true
    type: str

  variables:
    description:
      - Variables to use for the group.
      - Accepts a YAML/JSON dictionary which will be serialized as a JSON string.
    type: dict

  hosts:
    description:
      - List of host names or IDs that should be members of this group.
    type: list
    elements: str

  children:
    description:
      - List of group names or IDs that should be nested as children of this group.
    type: list
    elements: str
    aliases:
      - groups

  preserve_existing_hosts:
    description:
      - When true, only add new hosts without removing existing ones not in the list.
      - When false, sync to exactly the specified list (add missing, remove extra).
    type: bool
    default: false

  preserve_existing_children:
    description:
      - When true, only add new child groups without removing existing ones not in the list.
      - When false, sync to exactly the specified list (add missing, remove extra).
    type: bool
    default: false
    aliases:
      - preserve_existing_groups

seealso:
  - module: ansible.controller.group
  - module: awx.awx.group

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Add a group to an inventory
  ansible.platform.group:
    name: webservers
    description: "Web server group"
    inventory: "Production Inventory"
    variables:
      http_port: 80
      proxy_env: production
    state: present

- name: Rename a group
  ansible.platform.group:
    name: webservers
    new_name: web-servers
    inventory: "Production Inventory"

- name: Add group with hosts and children
  ansible.platform.group:
    name: webservers
    inventory: "Production Inventory"
    hosts:
      - web1.example.com
      - web2.example.com
    children:
      - east-web
      - west-web
    preserve_existing_hosts: true

- name: Delete a group
  ansible.platform.group:
    name: web-servers
    inventory: "Production Inventory"
    state: absent

- name: Check whether a group exists
  ansible.platform.group:
    name: webservers
    inventory: "Production Inventory"
    state: exists
  register: group_check
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
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the group.
      type: int
    name:
      description: Name of the group.
      type: str
    description:
      description: Description of the group.
      type: str
    inventory:
      description: Inventory the group belongs to (ID).
      type: int
    variables:
      description: Group variables as a JSON string.
      type: str
...
"""
