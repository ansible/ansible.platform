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
    - Gateway no longer supports creating service keys through its API.
    - If C(present) or C(enforced) is used with a missing key, the module attempts to create it and Gateway returns an error.
    - Deprecated creation parameters are ignored when editing an existing key.
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
    service_cluster:
      description: The name or ID of the Service Cluster.
      type: str
      deprecated:
        version: 4.0.0
        why: Gateway no longer permits creating service keys through its API.
        alternative: Create service keys outside this module and use this module only to edit existing keys.
    algorithm:
      type: str
      description: Algorithm to use for this Service Key.
      choices: ["HS256", "HS384", "HS512"]
      deprecated:
        version: 4.0.0
        why: Gateway no longer permits creating service keys through its API.
        alternative: Create service keys outside this module and use this module only to edit existing keys.
    secret:
      type: str
      description: Secret to use for this Service Key.
      no_log: true
      deprecated:
        version: 4.0.0
        why: Gateway no longer permits creating service keys through its API.
        alternative: Create service keys outside this module and use this module only to edit existing keys.
    secret_length:
      type: int
      description: Number of random bytes in the secret.
      deprecated:
        version: 4.0.0
        why: Gateway no longer permits creating service keys through its API.
        alternative: Create service keys outside this module and use this module only to edit existing keys.
    mark_previous_inactive:
      type: bool
      description: If true, any other secret keys for this service become inactive.
      deprecated:
        version: 4.0.0
        why: Gateway no longer permits creating service keys through its API.
        alternative: Create service keys outside this module and use this module only to edit existing keys.
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

- name: Remove an existing service key
  ansible.platform.service_key:
    name: Some Old Automation Controller Service Key
    state: absent
...
"""

# This module is doc-only; the action plugin runs all logic via the manager.
