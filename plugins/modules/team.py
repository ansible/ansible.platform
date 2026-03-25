#!/usr/bin/python
# coding: utf-8 -*-
# Copyright: (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
# Copyright: (c) 2024, Martin Slemr <@slemrmartin>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/team.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: team
author: Red Hat (@RedHatOfficial)
short_description: Configure a gateway team
description:
  - Configure an automation platform gateway team.
  - This module uses the persistent connection manager for improved performance.
version_added: "1.0.0"

options:
  name:
    description:
      - The name of the team, must be unique within the organization
    required: true
    type: str

  new_name:
    description:
      - Setting this option will change the existing name (looked up via the name field)
    type: str

  description:
    description:
      - The description of the team
    type: str

  organization:
    description:
      - The name or ID of the organization the team belongs to
    required: true
    type: str

  new_organization:
    description:
      - Setting this option will change the existing organization (looked up via the organization field)
    type: str

  state:
    description:
      - Desired state of the team.
      - C(present) ensures the team exists (create or update); idempotent.
      - C(absent) removes the team; idempotent if already absent.
      - C(exists) reads and returns the current team (no change).
      - C(enforced) ensures the team exists and merges task keys into existing.
    type: str
    choices: ['present', 'absent', 'exists', 'enforced']
    default: 'present'

extends_documentation_fragment:
  - ansible.platform.state
  - ansible.platform.auth
"""

EXAMPLES = """
- name: Create a team
  ansible.platform.team:
    name: Gateway Developers
    description: AAP Gateway Developers Team
    organization: Ansible Product Development
  register: created_team

- name: Idempotent re-run — no change expected
  ansible.platform.team:
    name: Gateway Developers
    organization: Ansible Product Development

- name: Round-trip update using registered result
  ansible.platform.team: "{{ created_team.team | combine({'description': 'Updated description'}) }}"

- name: Rename a team
  ansible.platform.team:
    name: Gateway Developers
    organization: Ansible Product Development
    new_name: Gateway Dev Team

- name: Move a team to a different organization
  ansible.platform.team:
    name: Gateway Dev Team
    organization: Ansible Product Development
    new_organization: Platform Engineering

- name: Reference a team by its numeric id
  ansible.platform.team:
    name: "{{ created_team.team.id }}"
    organization: Ansible Product Development
    description: Updated via id

- name: Check whether a team exists (no change)
  ansible.platform.team:
    name: Gateway Dev Team
    organization: Platform Engineering
    state: exists

- name: Delete a team
  ansible.platform.team:
    name: Gateway Dev Team
    organization: Platform Engineering
    state: absent
...
"""

RETURN = """
changed:
  description: Whether the team was created, updated, or deleted.
  returned: always
  type: bool

team:
  description: >
    The team resource as it exists after the operation.
    Contains only the fields accepted as module input (argspec fields) plus C(id).
    API-managed fields (C(created), C(modified), C(url)) and Ansible directives
    (C(state), C(new_name), C(new_organization)) are excluded so that
    C(result.team) can be fed back as module parameters unchanged (idempotent round-trip).
  returned: when state is present, exists, or enforced
  type: dict
  contains:
    id:
      description: Numeric database ID of the team.
      type: int
    name:
      description: Name of the team.
      type: str
    description:
      description: Description of the team.
      type: str
    organization:
      description: Name of the organization this team belongs to.
      type: str
...
"""
