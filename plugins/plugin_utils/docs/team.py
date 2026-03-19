"""
Legacy: DOCUMENTATION for the team module now lives in plugins/modules/team.py.

The action plugin discovers it via _get_documentation() from the sibling module
(meraki_rm-style). This file is kept for reference only; do not import from here.
"""

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
