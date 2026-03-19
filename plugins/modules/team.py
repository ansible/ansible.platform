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
- name: Create Team
  ansible.platform.team:
    name: Gateway Developers
    description: AAP Gateway Developers Team
    organization: Ansible Product Development

- name: Update Team
  ansible.platform.team:
    name: Gateway Developers
    organization: Ansible Product Development
    new_name: Gateway Dev Team

- name: Delete Team
  ansible.platform.team:
    name: Gateway Developers
    organization: Ansible Product Development
    state: absent
"""
