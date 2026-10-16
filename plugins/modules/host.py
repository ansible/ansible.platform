#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/host.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: host
author: Red Hat (@RedHatOfficial)
short_description: Manage Controller hosts
description:
  - Create, update, or delete hosts on Ansible Automation Platform Controller.
  - Hosts belong to an inventory and represent managed nodes.
version_added: "2.8.0"

options:
  name:
    description:
      - The name of the host.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field).
    type: str

  description:
    description:
      - The description of the host.
    type: str

  inventory:
    description:
      - Inventory name or ID the host belongs to.
    required: true
    type: str

  enabled:
    description:
      - If the host should be enabled.
    type: bool

  instance_id:
    description:
      - The value used by the remote inventory source to uniquely identify the host.
    type: str

  variables:
    description:
      - Variables to use for the host.
      - Accepts a YAML/JSON dictionary which will be serialized as a JSON string.
    type: dict

seealso:
  - module: ansible.controller.host
  - module: awx.awx.host

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Add a host to an inventory
  ansible.platform.host:
    name: webserver01
    description: "Web server node"
    inventory: "Production Inventory"
    enabled: true
    variables:
      ansible_host: 192.168.1.10
      http_port: 8080
    state: present

- name: Disable a host
  ansible.platform.host:
    name: webserver01
    inventory: "Production Inventory"
    enabled: false

- name: Rename a host
  ansible.platform.host:
    name: webserver01
    new_name: webserver01-prod
    inventory: "Production Inventory"

- name: Delete a host
  ansible.platform.host:
    name: webserver01-prod
    inventory: "Production Inventory"
    state: absent

- name: Check whether a host exists (no change)
  ansible.platform.host:
    name: webserver01
    inventory: "Production Inventory"
    state: exists
  register: host_check
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
    description:
      description: Description of the host.
      type: str
    inventory:
      description: Inventory the host belongs to (ID).
      type: int
    enabled:
      description: Whether the host is enabled.
      type: bool
    instance_id:
      description: Cloud provider instance identifier.
      type: str
    variables:
      description: Host variables as a JSON string.
      type: str
...
"""
