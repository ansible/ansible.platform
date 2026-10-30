#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: Contributors to the Ansible project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/eda_controller_token.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: eda_controller_token
author: Red Hat (@RedHatOfficial)
short_description: Manage AWX tokens in EDA controller
description:
  - Create or delete AWX tokens used by EDA controller to communicate with Ansible Controller.
  - The EDA controller token API does not support PATCH. When a token already exists and
    C(state=present), the module deletes and re-creates the token. This means the module
    always reports C(changed=True) when the token already exists.
  - This module uses the persistent connection manager for improved performance.
version_added: "2.6.0"

options:
  name:
    description:
      - The name of the AWX token.
    required: true
    type: str

  description:
    description:
      - The description of the AWX token.
      - Required when O(state=present).
    type: str

  token:
    description:
      - The AWX token value.
      - Required when O(state=present).
      - This field is sensitive and will not be logged or returned in module output.
    type: str

  state:
    description:
      - Desired state of the resource.
      - C(present) creates the token if it does not exist, or deletes and re-creates it
        if it already exists (the EDA API does not support token updates).
      - C(absent) removes the token if it exists.
    type: str
    choices: ["present", "absent"]
    default: "present"

seealso:
  - module: ansible.eda.controller_token

extends_documentation_fragment:
  - ansible.platform.auth
"""

EXAMPLES = """
- name: Create an AWX token for EDA
  ansible.platform.eda_controller_token:
    name: "Example AWX token"
    description: "Token for EDA-Controller communication"
    token: "<TOKEN_VALUE>"
    state: present
  no_log: true

- name: Delete an AWX token
  ansible.platform.eda_controller_token:
    name: "Example AWX token"
    state: absent
...
"""

RETURN = """
changed:
  description: Whether the token was created, re-created, or deleted.
  returned: always
  type: bool

eda_controller_token:
  description: >
    The token resource as it exists after the operation.
    The token value is only returned on creation and is not retrievable afterwards.
  returned: when state is present and successful
  type: dict
  contains:
    id:
      description: Numeric database ID of the token.
      type: int
    name:
      description: Name of the token.
      type: str
    description:
      description: Description of the token.
      type: str
...
"""
