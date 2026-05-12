#!/usr/bin/python
# coding: utf-8 -*-

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

ANSIBLE_METADATA = {"metadata_version": "1.1", "status": ["preview"], "supported_by": "community"}

DOCUMENTATION = """
---
module: role_user_assignment
author: "Seth Foster (@fosterseth)"
short_description: Gives a user permission to a resource or an organization.
description:
    - Use this endpoint to give a user permission to a resource or an organization.
    - After creation, the assignment cannot be edited, but can be deleted to remove those permissions.
options:
    role_definition:
        description:
            - The name or id of the role definition to assign to the user.
        required: True
        type: str
    object_id:
        description:
            - B(Deprecated)
            - This option is deprecated and will be removed in a release after 2026-05-20.
            - For associating a user to team(s)/organization(s), please use the object_ids param.
            - HORIZONTALLINE
            - Primary key/Name of the object this assignment applies to.
            - This option is mutually exclusive with I(object_ids) and I(object_ansible_id).
        required: False
        type: int
    object_ids:
        description:
            - List of object IDs(Primary Key ) or names this assignment applies to.
            - This option is mutually exclusive with I(object_id) and I(object_ansible_id).
        required: False
        type: list
        elements: str
    user:
        description:
            - The name or id of the user to assign to the object.
            - This option is mutually exclusive with I(user_ansible_id).
        required: False
        type: str
    object_ansible_id:
        description:
            - UUID of the object(team/organization) this role applies to. Alternative to the object_id/object_ids field.
            - This option is mutually exclusive with I(object_id) and I(object_ids)
        required: False
        type: str
    user_ansible_id:
        description:
            - Resource id of the user who will receive permissions from this assignment. Alternative to user field.
            - This option is mutually exclusive with I(user).
        required: False
        type: str
    state:
      description:
        - Desired state of the resource.
      choices: ["present", "absent", "exists"]
      default: "present"
      type: str
extends_documentation_fragment:
- ansible.platform.auth
"""

EXAMPLES = """
- name: Give bob organization admin role for a single org
  ansible.platform.role_user_assignment:
    role_definition: Organization Admin
    object_id: 1
    user: bob
  register: assignment

- name: Give bob team admin role for multiple teams by id and name
  ansible.platform.role_user_assignment:
    role_definition: Team Admin
    object_ids: ['1', 'dev-team']
    user: bob

- name: Give bob a role using object_ansible_id (UUID)
  ansible.platform.role_user_assignment:
    role_definition: Organization Admin
    object_ansible_id: c891b9f7-cc08-4b62-9843-c9ebfda262a9
    user: bob

- name: Grant platform-level auditor role (no object scoping)
  ansible.platform.role_user_assignment:
    role_definition: Platform Auditor
    user: bob

- name: Check whether an assignment exists
  ansible.platform.role_user_assignment:
    role_definition: Organization Admin
    object_id: 1
    user: bob
    state: exists

- name: Remove an assignment
  ansible.platform.role_user_assignment:
    role_definition: Organization Admin
    object_id: 1
    user: bob
    state: absent
...
"""

RETURN = """
changed:
  description: Whether an assignment was created or removed.
  returned: always
  type: bool

role_user_assignment:
  description: >
    The role assignment resource after the operation. For a single-object
    assignment this is the assignment dict. For multi-object (C(object_ids)),
    this is C({assignments: [...]}).
    API-managed fields (C(created), C(url)) and Ansible directives
    (C(state), C(object_ids)) are excluded so that C(result.role_user_assignment)
    represents only the resource data.
  returned: when state is present or exists
  type: dict
  contains:
    id:
      description: Numeric database ID of the assignment.
      type: int
    role_definition:
      description: Name or ID of the role definition assigned.
      type: str
    user:
      description: Username or ID of the user receiving the role.
      type: str
    object_id:
      description: Primary key of the object this assignment applies to (if scoped).
      type: int
...
"""
