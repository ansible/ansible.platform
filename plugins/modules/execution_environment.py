#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2020, Shane McDonald <shanemcd@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/execution_environment.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: execution_environment
author: Red Hat (@RedHatOfficial)
short_description: Create, update, or destroy Automation Platform Controller execution environments
description:
  - Create, update, or destroy Automation Platform Controller execution environments.
version_added: "3.0.0"

options:
  name:
    description:
      - The name to use for the execution environment.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field).
    type: str

  image:
    description:
      - The fully qualified url of the container image.
    required: true
    type: str

  description:
    description:
      - The description to use for the execution environment.
    type: str

  organization:
    description:
      - The organization name, ID, or named URL that the execution environment belongs to.
    type: str

  credential:
    description:
      - Name, ID, or named URL of the credential to use for the execution environment.
    type: str

  pull:
    description:
      - Image pull behavior.
    choices: ["always", "missing", "never"]
    default: "missing"
    type: str

  state:
    description:
      - Desired state of the execution environment.
      - C(present) ensures the execution environment exists (create or update); idempotent.
      - C(absent) removes the execution environment; idempotent if already absent.
      - C(exists) reads and returns the current execution environment (no change).
    type: str
    choices: ['present', 'absent', 'exists', 'enforced']
    default: 'present'

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth

seealso:
  - module: ansible.controller.execution_environment
  - module: awx.awx.execution_environment
"""

EXAMPLES = """
- name: Add EE
  ansible.platform.execution_environment:
    name: "My EE"
    image: quay.io/ansible/awx-ee
    state: present

- name: Delete EE
  ansible.platform.execution_environment:
    name: "My EE"
    state: absent
...
"""

RETURN = """
changed:
  description: Whether the execution environment was created, updated, or deleted.
  returned: always
  type: bool

execution_environment:
  description: >
    The execution environment resource as it exists after the operation.
    Contains only the fields accepted as module input (argspec fields) plus C(id).
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the execution environment.
      type: int
    name:
      description: Name of the execution environment.
      type: str
    image:
      description: The fully qualified url of the container image.
      type: str
    organization:
      description: ID of the organization the execution environment belongs to.
      type: int
...
"""
