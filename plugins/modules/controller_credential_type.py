#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2018, Adrien Fleury <fleu42@gmail.com>
# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/controller_credential_type.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: controller_credential_type
author: Red Hat (@RedHatOfficial)
short_description: Manage Controller credential types
description:
  - Create, update, or delete custom credential types on Ansible Automation Platform Controller.
  - Custom credential types extend the built-in types with user-defined input
    fields and injector configurations.
version_added: "2.8.0"

options:
  name:
    description:
      - The name of the credential type.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field).
    type: str

  description:
    description:
      - The description of the credential type.
    type: str

  kind:
    description:
      - The type of credential type being added.
      - Only C(cloud) and C(net) can be used for creating custom credential types.
    choices: ['cloud', 'net']
    type: str

  inputs:
    description:
      - Enter inputs using either JSON or YAML syntax.
      - Refer to the Automation Platform Controller documentation for example syntax.
    type: dict

  injectors:
    description:
      - Enter injectors using either JSON or YAML syntax.
      - Refer to the Automation Platform Controller documentation for example syntax.
    type: dict

seealso:
  - module: ansible.controller.credential_type
  - module: awx.awx.credential_type

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth
"""

EXAMPLES = """
- name: Create a custom credential type
  ansible.platform.controller_credential_type:
    name: Nexus
    description: Credentials type for Nexus
    kind: cloud
    inputs:
      fields:
        - id: nexus_user
          type: string
          label: Nexus User
        - id: nexus_password
          type: string
          label: Nexus Password
          secret: true
    injectors:
      extra_vars:
        nexus_user: "{{ '{{' }} nexus_user {{ '}}' }}"
        nexus_password: "{{ '{{' }} nexus_password {{ '}}' }}"
    state: present

- name: Rename a credential type
  ansible.platform.controller_credential_type:
    name: Nexus
    new_name: Nexus Repository Manager

- name: Delete a credential type
  ansible.platform.controller_credential_type:
    name: Nexus Repository Manager
    state: absent

- name: Check whether a credential type exists (no change)
  ansible.platform.controller_credential_type:
    name: Nexus
    state: exists
  register: ct_check
...
"""

RETURN = """
changed:
  description: Whether the credential type was created, updated, or deleted.
  returned: always
  type: bool

controller_credential_type:
  description: >
    The credential type resource as it exists after the operation.
    Contains only the fields accepted as module input (argspec fields) plus C(id).
    API-managed fields (C(created), C(modified), C(url)) and Ansible directives
    (C(state), C(new_name)) are excluded so that C(result.controller_credential_type)
    can be fed back as module parameters unchanged (idempotent round-trip).
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the credential type.
      type: int
    name:
      description: Name of the credential type.
      type: str
    description:
      description: Description of the credential type.
      type: str
    kind:
      description: The kind of credential type (cloud or net).
      type: str
    inputs:
      description: Input field definitions.
      type: dict
    injectors:
      description: Injector configurations.
      type: dict
...
"""
