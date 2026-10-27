#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2020, Shane McDonald <shanemcd@redhat.com>
# Copyright: (c) 2024, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/execution_environment.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: execution_environment
author: Red Hat (@RedHatOfficial)
short_description: Manage Controller execution environments
description:
  - Create, update, or delete execution environments on Ansible Automation Platform Controller.
  - Execution environments are container images used to run jobs.
version_added: "2.8.0"

options:
  name:
    description:
      - Name of the execution environment.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field).
    type: str

  image:
    description:
      - The fully qualified URL of the container image.
    type: str

  description:
    description:
      - Description of the execution environment.
    type: str

  organization:
    description:
      - Organization name or ID the execution environment belongs to.
    type: str

  credential:
    description:
      - Credential name or ID to use for the execution environment.
    type: str

  pull:
    description:
      - Determine image pull behavior.
    choices: ['always', 'missing', 'never']
    default: 'missing'
    type: str

seealso:
  - module: ansible.controller.execution_environment
  - module: awx.awx.execution_environment

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Add an execution environment
  ansible.platform.execution_environment:
    name: "My Custom EE"
    image: quay.io/ansible/awx-ee:latest
    description: "Custom execution environment"
    organization: "Default"
    pull: missing
    state: present

- name: Rename an execution environment
  ansible.platform.execution_environment:
    name: "My Custom EE"
    new_name: "Production EE"

- name: Delete an execution environment
  ansible.platform.execution_environment:
    name: "Production EE"
    state: absent

- name: Check whether an execution environment exists
  ansible.platform.execution_environment:
    name: "My Custom EE"
    state: exists
  register: ee_check
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
      description: Container image URL.
      type: str
    description:
      description: Description of the execution environment.
      type: str
    organization:
      description: Organization the execution environment belongs to (ID).
      type: int
    credential:
      description: Credential used for the execution environment (ID).
      type: int
    pull:
      description: Image pull behavior.
      type: str
...
"""
