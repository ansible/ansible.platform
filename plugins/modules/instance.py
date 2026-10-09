#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2022, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/instance.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: instance
author: Red Hat (@RedHatOfficial)
short_description: Manage Controller instances
description:
  - Create, update, or deprovision instances on Ansible Automation Platform Controller.
  - Instances represent execution and hop nodes in the automation mesh.
  - When C(state=absent), this module sets C(node_state) to C(deprovisioning)
    rather than deleting the instance directly. Controller will stop routing
    work to the instance and clean up its receptor connections. The instance
    record is removed from the database after the cleanup process completes,
    not immediately.
version_added: "2.8.0"

options:
  hostname:
    description:
      - Hostname of this instance.
    required: true
    type: str

  capacity_adjustment:
    description:
      - Capacity adjustment (0 <= capacity_adjustment <= 1).
    type: float

  enabled:
    description:
      - If true, the instance will be enabled and used.
    type: bool

  managed_by_policy:
    description:
      - Whether this instance is managed by policy.
    type: bool

  node_type:
    description:
      - Role that this node plays in the mesh.
    choices: ['execution', 'hop']
    type: str

  node_state:
    description:
      - Indicates the current life cycle stage of this instance.
      - Setting to C(deprovisioning) is equivalent to C(state=absent).
    choices: ['deprovisioning', 'installed']
    type: str

  listener_port:
    description:
      - Port that Receptor will listen for incoming connections on.
    type: int

  peers_from_control_nodes:
    description:
      - If enabled, control plane nodes will automatically peer to this node.
    type: bool

seealso:
  - module: ansible.controller.instance
  - module: awx.awx.instance

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Create an execution instance
  ansible.platform.instance:
    hostname: my-instance.prod.example.com
    capacity_adjustment: 0.4
    node_type: execution
    state: present

- name: Disable an instance
  ansible.platform.instance:
    hostname: my-instance.prod.example.com
    enabled: false

- name: Deprovision an instance
  ansible.platform.instance:
    hostname: my-instance.prod.example.com
    state: absent

- name: Check if an instance exists
  ansible.platform.instance:
    hostname: my-instance.prod.example.com
    state: exists
  register: instance_check
...
"""

RETURN = """
changed:
  description: Whether the instance was created, updated, or deprovisioned.
  returned: always
  type: bool

instance:
  description: >
    The instance resource as it exists after the operation.
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the instance.
      type: int
    hostname:
      description: Hostname of the instance.
      type: str
    capacity_adjustment:
      description: Capacity adjustment factor.
      type: float
    enabled:
      description: Whether the instance is enabled.
      type: bool
    managed_by_policy:
      description: Whether managed by policy.
      type: bool
    node_type:
      description: Role in the mesh (execution or hop).
      type: str
    node_state:
      description: Current lifecycle stage.
      type: str
    listener_port:
      description: Receptor listener port.
      type: int
    peers_from_control_nodes:
      description: Whether control nodes auto-peer.
      type: bool
...
"""
