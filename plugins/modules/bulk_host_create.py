#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/bulk_host_create.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: bulk_host_create
author: Red Hat (@RedHatOfficial)
short_description: Bulk host create in Automation Platform Controller
description:
  - Single-request bulk host creation in Automation Platform Controller.
  - Provides a way to add many hosts at once to an inventory.
  - This module uses the persistent connection manager for improved performance.
version_added: "1.0.0"

options:
  hosts:
    description:
      - List of hosts to add to inventory.
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
          - If the host should be enabled.
        type: bool
      variables:
        description:
          - Variables to use for the host.
        type: dict
      instance_id:
        description:
          - Instance ID to use for the host.
        type: str

  inventory:
    description:
      - Inventory name, ID, or named URL the hosts should be made a member of.
    required: true
    type: str

extends_documentation_fragment:
  - ansible.platform.auth
"""

EXAMPLES = """
- name: Bulk host create
  ansible.platform.bulk_host_create:
    inventory: "My Inventory"
    hosts:
      - name: foobar.org
      - name: 127.0.0.1

- name: Bulk host create with variables
  ansible.platform.bulk_host_create:
    inventory: "My Inventory"
    hosts:
      - name: host1.example.com
        variables:
          ansible_host: 10.0.0.1
      - name: host2.example.com
        enabled: false
"""

RETURN = """
changed:
  description: Whether any hosts were created.
  returned: always
  type: bool
"""
