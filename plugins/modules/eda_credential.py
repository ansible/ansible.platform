#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: Contributors to the Ansible project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/eda_credential.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: eda_credential
author: Red Hat (@RedHatOfficial)
short_description: Manage credentials in EDA controller
description:
  - Create, update, delete, copy, or test credentials in EDA controller.
  - When using C(state=test), the module validates credential connectivity to
    external systems without making changes.
  - Testing is particularly useful for verifying external secret management
    system credentials.
  - This module uses the persistent connection manager for improved performance.
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

  copy_from:
    description:
      - Name of the existing credential to copy.
      - If set, copies the specified credential.
      - The new credential will be created with the name given in the C(name) parameter.
    type: str

  description:
    description:
      - Description of the credential.
    type: str

  credential_type:
    description:
      - The name or ID of the credential type.
      - Required when creating a credential (C(state=present) without C(copy_from)).
    type: str

  organization:
    description:
      - The name or ID of the organization that owns the credential.
      - Required when creating a credential (C(state=present) without C(copy_from)).
    type: str

  inputs:
    description:
      - Credential inputs where the keys are var names used in templating.
      - This is a write-only field; the API will not return secret values.
      - Required when creating a credential (C(state=present) without C(copy_from)).
    type: dict

  metadata:
    description:
      - Additional configuration for testing specific secrets or configurations.
      - Only used when C(state=test).
      - The structure depends on the credential type and external system.
      - For HashiCorp Vault, should include keys like C(secret_path) and C(secret_key).
    type: dict

  state:
    description:
      - Desired state of the resource.
      - C(present) creates or updates the credential.
      - C(absent) removes the credential.
      - C(exists) checks whether the credential exists without making changes.
      - C(test) validates credential connectivity without making changes.
    type: str
    choices: ["present", "absent", "exists", "test"]
    default: "present"

seealso:
  - module: ansible.eda.credential

extends_documentation_fragment:
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Create an EDA Credential
  ansible.platform.eda_credential:
    name: "Example Credential"
    description: "Example credential description"
    inputs:
      field1: "field1"
    credential_type: "GitLab Personal Access Token"
    organization: Default
    state: present

- name: Update an EDA Credential description
  ansible.platform.eda_credential:
    name: "Example Credential"
    description: "Updated description"
    credential_type: "GitLab Personal Access Token"
    organization: Default
    state: present

- name: Rename an EDA Credential
  ansible.platform.eda_credential:
    name: "Example Credential"
    new_name: "Renamed Credential"
    credential_type: "GitLab Personal Access Token"
    organization: Default
    state: present

- name: Copy an existing EDA Credential
  ansible.platform.eda_credential:
    name: "New Copied Credential"
    copy_from: "Example Credential"
    state: present

- name: Delete an EDA Credential
  ansible.platform.eda_credential:
    name: "Example Credential"
    state: absent

- name: Test a HashiCorp Vault credential connectivity
  ansible.platform.eda_credential:
    name: "vault_lookup_credential"
    state: test
    metadata:
      secret_path: "secret/myapp"
      secret_key: "password"

- name: Check if a credential exists
  ansible.platform.eda_credential:
    name: "Example Credential"
    state: exists
  register: result
...
"""

RETURN = """
changed:
  description: Whether the credential was created, updated, or deleted.
  returned: always
  type: bool

eda_credential:
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
      type: str
    organization:
      description: Organization (ID).
      type: str

test_result:
  description: Result of the credential test.
  returned: when state is test
  type: dict
  contains:
    success:
      description: Whether the credential test was successful.
      type: bool
    message:
      description: Human-readable message describing the test result.
      type: str
    details:
      description: Additional details about the test result or error information.
      type: dict
...
"""
