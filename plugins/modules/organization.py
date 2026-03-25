#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
# Copyright: (c) 2024, Martin Slemr <@slemrmartin>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/organization.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: organization
author: Red Hat (@RedHatOfficial)
short_description: Configure a gateway organization
description:
  - Configure an automation platform gateway organizations.
  - This module uses the persistent connection manager for improved performance.
version_added: "1.0.0"

options:
  name:
    description:
      - The name of the organization, must be unique
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field)
    type: str

  description:
    description:
      - The description of the Organization
    type: str

  state:
    description:
      - Desired state of the organization.
      - C(present) ensures the organization exists (create or update); idempotent.
      - C(absent) removes the organization; idempotent if already absent.
      - C(exists) reads and returns the current organization (no change).
      - C(enforced) ensures the organization exists and merges task keys into existing.
    type: str
    choices: ['present', 'absent', 'exists', 'enforced']
    default: 'present'

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth
"""

EXAMPLES = """
- name: Create an organization
  ansible.platform.organization:
    name: Ansible Product Development
    description: Organization for ansible developers
  register: created_org

- name: Idempotent re-run — no change expected
  ansible.platform.organization:
    name: Ansible Product Development
    description: Organization for ansible developers

- name: Round-trip update using registered result
  ansible.platform.organization: "{{ created_org.organization | combine({'description': 'Updated description'}) }}"

- name: Rename an organization
  ansible.platform.organization:
    name: Ansible Product Development
    new_name: Ansible Platform Development

- name: Check whether an organization exists (no change)
  ansible.platform.organization:
    name: Ansible Platform Development
    state: exists
  register: org_check

- name: Delete an organization
  ansible.platform.organization:
    name: Ansible Platform Development
    state: absent
...
"""

RETURN = """
changed:
  description: Whether the organization was created, updated, or deleted.
  returned: always
  type: bool

organization:
  description: >
    The organization resource as it exists after the operation.
    Contains only the fields accepted as module input (argspec fields) plus C(id).
    API-managed fields (C(created), C(modified), C(url)) and Ansible directives
    (C(state), C(new_name)) are excluded so that C(result.organization) can be
    fed back as module parameters unchanged (idempotent round-trip).
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the organization.
      type: int
    name:
      description: Name of the organization.
      type: str
    description:
      description: Description of the organization.
      type: str
...
"""
