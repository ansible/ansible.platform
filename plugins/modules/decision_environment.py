#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: Contributors to the Ansible project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/decision_environment.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: decision_environment
author: Red Hat (@RedHatOfficial)
short_description: Manage decision environments in EDA controller
description:
  - Create, update, or delete decision environments in Event-Driven Ansible (EDA) controller.
  - Decision environments are container images used by EDA to run rulebook activations.
  - This module uses the persistent connection manager for improved performance.
version_added: "2.6.0"

options:
  name:
    description:
      - The name of the decision environment.
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field).
    type: str

  description:
    description:
      - The description of the decision environment.
    type: str

  image_url:
    description:
      - Image URL of the decision environment.
      - Required when O(state=present).
    type: str

  credential:
    description:
      - Name or ID of the EDA credential to associate with the decision environment.
    type: str

  pull_policy:
    description:
      - Image pull policy for the decision environment container.
      - C(always) pulls the image before starting the container.
      - C(never) prevents pulling and uses local image.
      - C(missing) only pulls if image is not available locally.
    type: str
    choices: ['always', 'never', 'missing']
    default: 'always'

  organization_name:
    description:
      - The name or ID of the organization the decision environment belongs to.
    type: str
    aliases:
      - organization

  state:
    description:
      - Desired state of the resource.
    type: str
    choices: ["present", "absent", "exists", "enforced"]
    default: "present"

seealso:
  - module: ansible.eda.decision_environment

extends_documentation_fragment:
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Create an EDA decision environment
  ansible.platform.decision_environment:
    name: "Example Decision Environment"
    description: "Example Decision Environment description"
    image_url: "quay.io/test/image:latest"
    credential: "Example Credential"
    pull_policy: "missing"
    organization_name: Default
    state: present

- name: Update the name of a decision environment
  ansible.platform.decision_environment:
    name: "Example Decision Environment"
    new_name: "Latest Decision Environment"
    state: present

- name: Delete a decision environment
  ansible.platform.decision_environment:
    name: "Example Decision Environment"
    state: absent

- name: Check if a decision environment exists
  ansible.platform.decision_environment:
    name: "Example Decision Environment"
    state: exists
  register: de_check
...
"""

RETURN = """
changed:
  description: Whether the decision environment was created, updated, or deleted.
  returned: always
  type: bool

decision_environment:
  description: >
    The decision environment resource as it exists after the operation.
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the decision environment.
      type: int
    name:
      description: Name of the decision environment.
      type: str
    description:
      description: Description of the decision environment.
      type: str
    image_url:
      description: Image URL of the decision environment.
      type: str
    credential:
      description: EDA credential associated with the decision environment (ID).
      type: int
    pull_policy:
      description: Image pull policy.
      type: str
    organization_name:
      description: Organization the decision environment belongs to (ID).
      type: str
...
"""
