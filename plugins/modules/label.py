#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/label.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: label
author: Red Hat (@RedHatOfficial)
short_description: Manage Controller labels
description:
  - Create or update labels on Ansible Automation Platform Controller.
  - Labels cannot be deleted via the API. Once fully disassociated from all
    resources, the API cleans them up automatically.
version_added: "2.8.0"

options:
  name:
    description:
      - The name of the label.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field).
    type: str

  organization:
    description:
      - Organization name or ID this label belongs to.
    required: true
    type: str

  state:
    description:
      - Desired state of the resource.
      - C(present) ensures the label exists (create or update); idempotent.
      - C(exists) reads and returns the current label (no change).
      - Labels cannot be deleted via the API, so C(absent) is not supported.
    type: str
    default: present
    choices: ['present', 'exists']

seealso:
  - module: ansible.controller.label
  - module: awx.awx.label

extends_documentation_fragment:
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Create a label
  ansible.platform.label:
    name: Production
    organization: Default

- name: Rename a label
  ansible.platform.label:
    name: Production
    new_name: Prod
    organization: Default

- name: Check whether a label exists
  ansible.platform.label:
    name: Prod
    organization: Default
    state: exists
  register: label_check
...
"""

RETURN = """
changed:
  description: Whether the label was created or updated.
  returned: always
  type: bool

label:
  description: >
    The label resource as it exists after the operation.
  returned: when state is present or exists
  type: dict
  contains:
    id:
      description: Numeric database ID of the label.
      type: int
    name:
      description: Name of the label.
      type: str
    organization:
      description: Organization the label belongs to (ID).
      type: int
...
"""
