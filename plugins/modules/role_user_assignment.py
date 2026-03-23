#!/usr/bin/python
# coding: utf-8 -*-

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1', 'status': ['preview'], 'supported_by': 'community'}

DOCUMENTATION = '''
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
            - This option is deprecated and will be removed in a release after 2027-01-31.
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
'''

EXAMPLES = '''
- name: Give Bob organization admin role for org 1
  ansible.platform.role_user_assignment:
    role_definition: Organization Admin
    object_id: 1
    user: bob
    state: present

- name: Give Bob Team admin role for teams with id 1 and name "team2"
  ansible.platform.role_user_assignment:
    role_definition: Team Admin
    object_ids: ['1', 'team2']
    user: bob
    state: present

- name: Give Bob team admin role for org 1 using object_ansible_id
  ansible.platform.role_user_assignment:
    role_definition: Team Admin
    object_ansible_id: c891b9f7-cc08-4b62-9843-c9ebfda262a9
    user: bob
    state: present

...
'''
