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
- name: Create Organization
  ansible.platform.organization:
    name: Ansible Product Development
    description: Organization for ansible developers

- name: Update Organization
  ansible.platform.organization:
    name: Ansible Product Development
    description: Updated description

- name: Delete Organization
  ansible.platform.organization:
    name: Ansible Product Development
    state: absent
"""
