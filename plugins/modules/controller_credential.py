#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/controller_credential.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: controller_credential
author: Red Hat (@RedHatOfficial)
short_description: Manage Controller credentials
description:
  - Create, update, or delete credentials on Ansible Automation Platform Controller.
version_added: "2.8.0"

options:
  name:
    description:
      - The name of the credential.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field).
    type: str

  description:
    description:
      - The description of the credential.
    type: str

  credential_type:
    description:
      - The credential type name or ID.
    required: true
    type: str

  organization:
    description:
      - Organization name or ID that should own the credential.
      - Mutually exclusive with C(user) and C(team).
    type: str

  user:
    description:
      - User name or ID that should own this credential.
      - Mutually exclusive with C(organization) and C(team).
    type: str

  team:
    description:
      - Team name or ID that should own this credential.
      - Mutually exclusive with C(organization) and C(user).
    type: str

  inputs:
    description:
      - Credential inputs where the keys are var names used in templating.
      - This is a write-only field; the API will not return secret values.
    type: dict

  update_secrets:
    description:
      - C(true) will always send encrypted values on update.
      - C(false) will only update encrypted values if a change is known to be needed.
    type: bool
    default: true

seealso:
  - module: ansible.controller.credential
  - module: awx.awx.credential

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Add a Machine credential
  ansible.platform.controller_credential:
    name: Team Credential
    description: Credential for team operations
    organization: Default
    credential_type: Machine
    inputs:
      username: admin
      password: secret123
    state: present

- name: Delete a credential
  ansible.platform.controller_credential:
    name: Team Credential
    credential_type: Machine
    organization: Default
    state: absent
...
"""

RETURN = """
changed:
  description: Whether the credential was created, updated, or deleted.
  returned: always
  type: bool

controller_credential:
  description: The credential resource as it exists after the operation.
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the credential.
      type: int
    name:
      description: Name of the credential.
      type: str
    description:
      description: Description of the credential.
      type: str
    credential_type:
      description: Credential type (ID).
      type: int
...
"""
