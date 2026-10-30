#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: Contributors to the Ansible project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/eda_credential_type.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: eda_credential_type
author: Red Hat (@RedHatOfficial)
short_description: Manage credential types in EDA controller
description:
  - Create, update, or delete custom credential types on EDA controller.
  - Custom credential types define the input fields and injector configurations
    used by EDA credentials.
  - The C(test) state validates a credential type's configuration by POSTing
    test inputs and metadata to the EDA credential type test endpoint.
  - This module uses the persistent connection manager for improved performance.
version_added: "2.6.0"

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

  inputs:
    description:
      - The input field definitions for the credential type.
      - Enter inputs using either JSON or YAML syntax.
      - Required when O(state=present).
    type: dict

  injectors:
    description:
      - The injector configuration for the credential type.
      - Enter injectors using either JSON or YAML syntax.
      - Required when O(state=present).
    type: dict

  test_inputs:
    description:
      - Test input values to validate the credential type configuration.
      - Only used when O(state=test).
    type: dict

  test_metadata:
    description:
      - Test metadata to validate the credential type configuration.
      - Only used when O(state=test).
    type: dict

  state:
    description:
      - Desired state of the resource.
      - C(present) creates or updates the credential type.
      - C(absent) removes the credential type if it exists.
      - C(test) validates the credential type configuration using the test endpoint.
    type: str
    choices: ["present", "absent", "test"]
    default: "present"

required_if:
  - ["state", "present", ["inputs", "injectors"]]

seealso:
  - module: ansible.eda.credential_type

extends_documentation_fragment:
  - ansible.platform.auth
"""

EXAMPLES = """
- name: Create an EDA credential type
  ansible.platform.eda_credential_type:
    name: "Test"
    state: present
    description: "A test credential type"
    inputs:
      fields:
        - id: "Field1"
          type: "string"
          label: "Label1"
    injectors:
      extra_vars:
        field1: "field1"

- name: Rename an EDA credential type
  ansible.platform.eda_credential_type:
    name: "Test"
    new_name: "Renamed Test"
    inputs:
      fields:
        - id: "Field1"
          type: "string"
          label: "Label1"
    injectors:
      extra_vars:
        field1: "field1"

- name: Test a HashiCorp Vault credential type configuration
  ansible.platform.eda_credential_type:
    name: "HashiCorp Vault Secret Lookup"
    state: test
    test_inputs:
      url: "https://vault.example.com:8200/"
      token: "dummy-token-for-testing"
      api_version: "v2"
    test_metadata:
      secret_path: "secret/myapp"
      secret_key: "password"

- name: Test credential type basic configuration
  ansible.platform.eda_credential_type:
    name: "AWS Secrets Manager lookup"
    state: test

- name: Delete an EDA credential type
  ansible.platform.eda_credential_type:
    name: "Test"
    state: absent
...
"""

RETURN = """
changed:
  description: Whether the credential type was created, updated, or deleted.
  returned: always
  type: bool

eda_credential_type:
  description: >
    The credential type resource as it exists after the operation.
    Contains only the fields accepted as module input (argspec fields) plus C(id).
  returned: when state is present or test
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
    inputs:
      description: Input field definitions.
      type: dict
    injectors:
      description: Injector configurations.
      type: dict

test_result:
  description: >
    Result of the credential type test operation.
  returned: when state is test
  type: dict
...
"""
