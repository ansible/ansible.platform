#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2020, Bianca Henderson <bianca@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/inventory_source_update.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: inventory_source_update
author: Red Hat (@RedHatOfficial)
short_description: Launch an inventory source update (sync)
description:
  - Launch an inventory source update (sync) on the Ansible Automation Platform controller.
  - This module always launches a new inventory source update; it is not idempotent.
version_added: "3.0.0"

options:
  name:
    description:
      - The name of the inventory source to update.
    required: true
    type: str
    aliases:
      - inventory_source

  inventory:
    description:
      - Name or ID of the inventory that contains the inventory source to update.
    required: true
    type: str

  wait:
    description:
      - Wait for the update to complete.
    default: false
    type: bool

  interval:
    description:
      - The interval in seconds to request an update from the controller.
    default: 2
    type: float

  timeout:
    description:
      - If waiting for the update to complete this will abort after this
        amount of seconds.
      - When C(wait=true) and this option is omitted, polling is capped at
        3600 seconds (1 hour). Set explicitly to use a different limit.
    type: int

extends_documentation_fragment:
  - ansible.platform.auth

notes:
  - The legacy C(organization) option (used only to disambiguate the C(inventory)
    name lookup when names collide across organizations) is not carried over —
    name lookups resolve globally. Use a unique name, or the numeric ID, if this
    is a concern.

seealso:
  - module: ansible.controller.inventory_source_update
  - module: awx.awx.inventory_source_update
"""

EXAMPLES = """
- name: Update a single inventory source, waiting for it to finish
  ansible.platform.inventory_source_update:
    name: "Example Inventory Source"
    inventory: "My Inventory"
    wait: true

- name: Launch an inventory source update without waiting
  ansible.platform.inventory_source_update:
    name: "Example Inventory Source"
    inventory: "My Inventory"
...
"""

RETURN = """
id:
  description: ID of the newly launched inventory update.
  returned: success
  type: int
  sample: 86
status:
  description:
    - Status of the launched inventory update.
    - With C(wait=false) this is always C(pending) — the update has only just
      been launched. With C(wait=true) this is the terminal status reported by
      Controller once the update finishes; the task fails (C(failed=true)) if
      that terminal status is C(error), C(failed), or C(canceled).
  returned: success
  type: str
  sample: pending
...
"""
