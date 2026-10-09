#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2020, Tom Page <tpage@redhat.com>
# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/credential_input_source.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: credential_input_source
author: Red Hat (@RedHatOfficial)
short_description: Manage Controller credential input sources
description:
  - Create, update, or delete credential input sources on Ansible Automation Platform Controller.
  - Credential input sources link an external credential (e.g. HashiCorp Vault, CyberArk)
    to a specific input field of a target credential.
version_added: "2.8.0"

options:
  description:
    description:
      - The description of the credential input source.
    type: str

  input_field_name:
    description:
      - The input field on the target credential that this source will populate.
    required: true
    type: str

  target_credential:
    description:
      - The credential name or ID whose input field will be populated by this source.
    required: true
    type: str

  source_credential:
    description:
      - The credential name or ID that provides the external lookup (e.g. a HashiCorp Vault credential).
    type: str

  metadata:
    description:
      - Metadata for the credential input source lookup.
      - The contents depend on the source credential type (e.g. vault path, secret key).
    type: dict

seealso:
  - module: ansible.controller.credential_input_source
  - module: awx.awx.credential_input_source

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Use CyberArk lookup as password source
  ansible.platform.credential_input_source:
    input_field_name: password
    target_credential: my_machine_credential
    source_credential: cyberark_lookup
    metadata:
      object_query: "Safe=MY_SAFE;Object=awxuser"
      object_query_format: "Exact"
    state: present

- name: Remove a credential input source
  ansible.platform.credential_input_source:
    input_field_name: password
    target_credential: my_machine_credential
    state: absent

- name: Check if a credential input source exists
  ansible.platform.credential_input_source:
    input_field_name: password
    target_credential: my_machine_credential
    state: exists
  register: cis_check
...
"""

RETURN = """
changed:
  description: Whether the credential input source was created, updated, or deleted.
  returned: always
  type: bool

credential_input_source:
  description: >
    The credential input source resource as it exists after the operation.
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the credential input source.
      type: int
    description:
      description: Description of the credential input source.
      type: str
    input_field_name:
      description: The input field being populated.
      type: str
    target_credential:
      description: Target credential (ID).
      type: int
    source_credential:
      description: Source credential (ID).
      type: int
    metadata:
      description: Metadata for the lookup.
      type: dict
...
"""
