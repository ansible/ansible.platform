#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2024, Martin Slemr <@slemrmartin>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: service_key
author: Martin Slemr (@slemrmartin)
short_description: Edit an existing gateway service key.
description:
    - Edit an existing automation platform gateway service key.
    - The C(present) and C(enforced) states fail if the named key does not exist.
    - This module does not create service keys.
options:
    name:
      required: true
      type: str
      description: The name of the AAP Service Key, must be unique
    new_name:
      type: str
      description: Setting this option will change the existing name (looked up via the name field)
    is_active:
      type: bool
      description:
      - flag for setting the active state of the Service Key
      - defaults to true by API
extends_documentation_fragment:
- ansible.platform.state
- ansible.platform.auth
"""

EXAMPLES = """
- name: Update an existing service key
  ansible.platform.service_key:
    name: Automation Controller Service Key
    is_active: true

- name: Rename an existing service key
  ansible.platform.service_key:
    name: Automation Controller Service Key
    new_name: New Automation Controller Service Key
...
"""

# This module is doc-only; the action plugin runs all logic via the manager.
