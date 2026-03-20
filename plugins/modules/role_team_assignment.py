#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Doc-only stub for ansible.platform.role_team_assignment.

All execution logic lives in the corresponding action plugin
(plugins/action/role_team_assignment.py).  This module exists solely
so that ansible-doc, validate-modules, and argument-spec validation
can discover the DOCUMENTATION / EXAMPLES blocks.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = '''
---
module: role_team_assignment
author: Rohit Thakur (@rohitthakur2590)
short_description: Gives a team permission to a resource or an organization.
description:
    - Use this module to assign team or organization related roles to a team.
    - After creation, the assignment cannot be edited, but can be deleted to
      remove those permissions.
    - Not all role assignments are valid. See Limitations below.
notes:
  - This module is subject to limitations of the RBAC system in AAP 2.6.
  - Global roles (e.g. Platform Auditor) cannot be assigned to teams.
  - Team roles cannot be assigned to another team
    (Team Admin → Team is not supported).
  - Organization Member role cannot be assigned to teams.
  - Only resource-scoped organization roles (e.g. "Organization Inventory
    Admin", "Organization Credential Admin") can be meaningfully assigned
    to teams.
  - Attempting unsupported role assignments will result in errors.
options:
    role_definition:
        description:
          - The role definition which defines permissions conveyed by this
            assignment.
        required: true
        type: str
    team:
        description:
          - The name or id of the team to assign to the object.
          - Mutually exclusive with I(team_ansible_id).
        required: false
        type: str
    team_ansible_id:
        description:
          - Resource id of the team who will receive permissions from this
            assignment.  Alternative to I(team).
        required: false
        type: str
    assignment_objects:
        description:
            - List of objects to assign the role against.
            - Each item must specify exactly one of
              C(name)+C(type), C(object_id), or C(object_ansible_id).
        type: list
        elements: dict
        suboptions:
            name:
                description:
                  - The object name (e.g. organization or team name).
                  - Requires C(type) to be set.
                type: str
                required: false
            type:
                description:
                  - The object type used for name lookup.
                  - Supported values: C(organizations), C(teams).
                type: str
                required: false
            object_id:
                description:
                  - The primary key of the object this assignment applies to.
                  - A null value indicates a system-wide assignment.
                type: int
                required: false
            object_ansible_id:
                description:
                  - Resource id of the object this role applies to.
                    Alternative to I(object_id).
                type: str
                required: false
    object_id:
        description:
          - Primary key of a single object to assign against.
          - Use I(assignment_objects) when assigning to multiple objects.
        type: int
        required: false
    object_ids:
        description:
          - List of primary keys of objects to assign against.
        type: list
        elements: int
        required: false
    object_ansible_id:
        description:
          - Resource ansible_id of the object to assign against.
        type: str
        required: false
    state:
      description:
        - Desired state of the resource.
        - C(present) ensures the assignment exists (creates if missing).
        - C(absent) removes the assignment if it exists.
        - C(exists) asserts the assignment is already present and fails if
          it is not.
      choices: ["present", "absent", "exists"]
      default: "present"
      type: str
extends_documentation_fragment:
- ansible.platform.auth
'''

EXAMPLES = '''
- name: Assign role to a team against multiple organizations by name
  ansible.platform.role_team_assignment:
    role_definition: Organization Inventory Admin
    team: "APAC-BLR"
    assignment_objects:
      - name: "org-emea"
        type: "organizations"
      - name: "org-apac"
        type: "organizations"
    state: present
  register: result

- name: Assign role using object_ansible_id
  ansible.platform.role_team_assignment:
    role_definition: Organization Inventory Admin
    team: "APAC-BLR"
    assignment_objects:
      - object_ansible_id: "c891b9f7-cc08-4b62-9843-c9ebfda362a8"
    state: present
  register: result

- name: Assign role using direct object_id
  ansible.platform.role_team_assignment:
    role_definition: Organization Inventory Admin
    team: "APAC-BLR"
    object_id: 42
    state: present

- name: Check role team assignment exists
  ansible.platform.role_team_assignment:
    role_definition: Organization Inventory Admin
    team: "APAC-BLR"
    assignment_objects:
      - object_ansible_id: "c891b9f7-cc08-4b62-9843-c9ebfda362a8"
    state: exists
  register: result

- name: Remove role team assignment for multiple objects
  ansible.platform.role_team_assignment:
    role_definition: Organization Inventory Admin
    team: "APAC-BLR"
    assignment_objects:
      - name: "org-emea"
        type: "organizations"
      - name: "org-apac"
        type: "organizations"
    state: absent
  register: result
'''

RETURN = '''
id:
    description: Database id of the assignment (single-object operations).
    type: int
    returned: when state=present or state=exists and a single object is targeted
assignments:
    description: List of assignment results when multiple objects are targeted.
    type: list
    returned: always
role_team_assignment:
    description: The assignment resource dict (single-object) or wrapper dict.
    type: dict
    returned: always
changed:
    description: Whether any assignment was created or deleted.
    type: bool
    returned: always
'''


def main():
    # All execution is handled by the action plugin.
    # This stub is never called directly.
    pass


if __name__ == '__main__':
    main()
