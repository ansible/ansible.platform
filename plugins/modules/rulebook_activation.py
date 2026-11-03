#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: Contributors to the Ansible project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/rulebook_activation.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: rulebook_activation
author: Red Hat (@RedHatOfficial)
short_description: Manage rulebook activations in EDA controller
description:
  - Create, update, delete, enable, disable, or restart rulebook activations
    in the EDA Controller.
  - This module uses the persistent connection manager for improved performance.
version_added: "2.6.0"

options:
  name:
    description:
      - The name of the rulebook activation.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via O(name)).
    type: str

  description:
    description:
      - The description of the rulebook activation.
    type: str

  project_name:
    description:
      - The name of the project associated with the rulebook activation.
      - Required when creating an activation.
    type: str
    aliases:
      - project

  rulebook_name:
    description:
      - The name of the rulebook associated with the rulebook activation.
      - Required when creating an activation.
    type: str
    aliases:
      - rulebook

  extra_vars:
    description:
      - The extra variables for the rulebook activation.
    type: str

  restart:
    description:
      - Performs a restart of the activation. This is a non-idempotent operation.
      - If enabled, other parameters will be ignored.
    type: bool
    default: false

  restart_policy:
    description:
      - The restart policy for the rulebook activation.
    default: "on-failure"
    choices: ["on-failure", "always", "never"]
    type: str

  decision_environment_name:
    description:
      - The name of the decision environment associated with the rulebook activation.
      - Required when creating an activation.
    type: str
    aliases:
      - decision_environment

  awx_token_name:
    description:
      - The name of the AWX token.
    type: str
    aliases:
      - awx_token
      - token

  organization_name:
    description:
      - The name of the organization.
      - Required when creating an activation.
    type: str
    aliases:
      - organization

  eda_credentials:
    description:
      - A list of EDA credential names used by the rulebook activation.
    type: list
    elements: str
    aliases:
      - credentials

  k8s_service_name:
    description:
      - The name of the Kubernetes service associated with this rulebook activation.
    type: str

  event_streams:
    description:
      - A list of event stream mappings for this rulebook activation.
    type: list
    elements: dict
    suboptions:
      event_stream:
        description:
          - The name of the event stream.
        type: str
      source_name:
        description:
          - The name of the source in the rulebook.
          - Mutually exclusive with O(event_streams[].source_index).
        type: str
      source_index:
        description:
          - The index of the source in the rulebook.
          - Mutually exclusive with O(event_streams[].source_name).
        type: int

  log_level:
    description:
      - The desired log level for the rulebook activation.
    type: str
    default: "error"
    choices: ["debug", "info", "error"]

  enable_persistence:
    description:
      - Enable event persistence for this activation.
    type: bool
    default: false

  rule_engine_credential_id:
    description:
      - The ID of the Event-Driven Ansible Rule Engine Credential.
    type: int

  restart_on_project_update:
    description:
      - Used to indicate if an activation should restart after a project update.
    type: bool
    default: false

  state:
    description:
      - Desired state of the resource.
      - C(present) creates or updates the activation in an enabled state.
      - C(absent) removes the activation if it exists.
      - C(enabled) enables an existing activation or creates one in enabled state.
      - C(disabled) disables an existing activation or creates one in disabled state.
    type: str
    choices: ["present", "absent", "enabled", "disabled"]
    default: "present"

seealso:
  - module: ansible.eda.rulebook_activation

extends_documentation_fragment:
  - ansible.platform.auth
"""

EXAMPLES = """
- name: Create a rulebook activation
  ansible.platform.rulebook_activation:
    name: "Example Rulebook Activation"
    description: "Example Rulebook Activation description"
    project_name: "Example Project"
    rulebook_name: "hello_controller.yml"
    decision_environment_name: "Example Decision Environment"
    organization_name: "Default"
    state: present
    restart_on_project_update: false

- name: Create a disabled rulebook activation
  ansible.platform.rulebook_activation:
    name: "Example Rulebook Activation"
    description: "Example Rulebook Activation description"
    project_name: "Example Project"
    rulebook_name: "hello_controller.yml"
    decision_environment_name: "Example Decision Environment"
    organization_name: "Default"
    state: disabled
    restart_on_project_update: false

- name: Create a rulebook activation with event_streams
  ansible.platform.rulebook_activation:
    name: "Example Rulebook Activation"
    description: "Example Activation description"
    project_name: "Example Project"
    rulebook_name: "hello_controller.yml"
    decision_environment_name: "Example Decision Environment"
    organization_name: "Default"
    state: disabled
    event_streams:
      - event_stream: "Example Event Stream"
        source_name: "Sample source"
    restart_on_project_update: false

- name: Enable a rulebook activation
  ansible.platform.rulebook_activation:
    name: "Example Rulebook Activation"
    state: enabled

- name: Disable a rulebook activation
  ansible.platform.rulebook_activation:
    name: "Example Rulebook Activation"
    state: disabled

- name: Restart a rulebook activation
  ansible.platform.rulebook_activation:
    name: "Example Rulebook Activation"
    restart: true

- name: Delete a rulebook activation
  ansible.platform.rulebook_activation:
    name: "Example Rulebook Activation"
    state: absent
...
"""

RETURN = """
id:
  description: ID of the rulebook activation.
  returned: when exists
  type: int
  sample: 37

changed:
  description: Whether the resource was changed.
  returned: always
  type: bool

rulebook_activation:
  description: The rulebook activation resource after the operation.
  returned: when state is present, enabled, or disabled and successful
  type: dict
  contains:
    id:
      description: Numeric database ID of the activation.
      type: int
    name:
      description: Name of the activation.
      type: str
...
"""
