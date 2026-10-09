#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: bulk_host_create
author: "Seth Foster (@fosterseth)"
short_description: Bulk host create in Automation Platform Controller
description:
    - Single-request bulk host creation in Automation Platform Controller.
    - Provides a way to add many hosts at once to an inventory in Controller.
    - This module is not idempotent. Each call will create new hosts.
options:
    hosts:
      description:
        - List of hosts to add to the inventory.
      required: True
      type: list
      elements: dict
      suboptions:
        name:
          description:
            - The name to use for the host.
          type: str
          required: True
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
            - instance_id to use for the host.
          type: str
    inventory:
      description:
        - Inventory name, ID, or named URL the hosts should be made a member of.
      required: True
      type: str

extends_documentation_fragment: ansible.platform.auth
"""

EXAMPLES = """
- name: Bulk create hosts in an inventory
  ansible.platform.bulk_host_create:
    inventory: "My Inventory"
    hosts:
      - name: "host1.example.com"
        description: "First host"
        variables:
          ansible_host: "192.168.1.1"
      - name: "host2.example.com"
        enabled: false

- name: Bulk create hosts by inventory ID
  ansible.platform.bulk_host_create:
    inventory: 42
    hosts:
      - name: "10.0.0.1"
      - name: "10.0.0.2"
        instance_id: "i-abc123"
"""

RETURN = """
hosts:
  description: The list of hosts that were created.
  type: list
  returned: on success
"""
