#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2020, Bianca Henderson <bianca@redhat.com>
# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/inventory_source_update.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: inventory_source_update
author: Red Hat (@RedHatOfficial)
short_description: Trigger an inventory source sync
description:
  - Trigger a sync for an inventory source on Ansible Automation Platform Controller.
  - Every invocation triggers a new sync; this module is not idempotent.
  - Optionally waits for the sync to complete.
version_added: "2.8.0"

options:
  name:
    description:
      - Name or ID of the inventory source to update.
    required: true
    type: str
    aliases:
      - inventory_source

  inventory:
    description:
      - Name or ID of the inventory that contains the inventory source.
    required: true
    type: str

  organization:
    description:
      - Organization name or ID to scope the inventory lookup.
      - Used when multiple inventories share the same name.
    type: str

  wait:
    description:
      - Wait for the sync to complete.
    default: false
    type: bool

  interval:
    description:
      - Polling interval in seconds when waiting.
    default: 2.0
    type: float

  timeout:
    description:
      - Maximum seconds to wait before aborting (client-side).
      - Only used when C(wait=true).
    type: int

seealso:
  - module: ansible.controller.inventory_source_update
  - module: awx.awx.inventory_source_update
  - module: ansible.platform.inventory_source

extends_documentation_fragment:
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Update an inventory source and wait
  ansible.platform.inventory_source_update:
    name: "Cloud Source"
    inventory: "Production Inventory"
    wait: true
    timeout: 120

- name: Trigger a sync without waiting
  ansible.platform.inventory_source_update:
    name: "Cloud Source"
    inventory: "Production Inventory"

- name: Update with organization scoping
  ansible.platform.inventory_source_update:
    name: "Cloud Source"
    inventory: "Shared Inventory"
    organization: "Engineering"
    wait: true
...
"""

RETURN = """
id:
  description: ID of the inventory update job.
  returned: success
  type: int
  sample: 86

status:
  description: Status of the inventory update.
  returned: success
  type: str
  sample: pending
...
"""
