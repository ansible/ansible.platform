#!/usr/bin/python
# coding: utf-8 -*-

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type


DOCUMENTATION = '''
---
module: role_team_assignment
author: Rohit Thakur (@rohitthakur2590)
short_description: Gives a team permission to a resource or an organization.
description:
    - Use this module to assign team or organization related roles to a team.
    - After creation, the assignment cannot be edited, but can be deleted to remove those permissions.
    - Not all role assignments are valid. See Limitations below.
notes:
  - This module is subject to limitations of the RBAC system in AAP 2.6.
  - Global roles (e.g. Platform Auditor) cannot be assigned to teams.
  - Team roles cannot be assigned to another team (Team Admin → Team is not supported).
  - Organization Member role cannot be assigned to teams.
  - Only resource-scoped organization roles (e.g. "Organization Inventory Admin", "Organization Credential Admin") can be meaningfully assigned to teams.
  - Attempting unsupported role assignments will result in errors.
options:
    assignment_object:
      description:
        - dicts mapping resource names to their types.
        - Must include C(name) and C(type).
      type: dict
      suboptions:
        name:
          description: The object name (e.g. organization/team name).
          type: str
          required: true
        type:
          description: The object type (e.g. C(organizations), C(teams)).
          type: str
          required: true
    role_definition:
        description:
            - The role definition which defines permissions conveyed by this assignment.
        required: True
        type: str
    object_id:
        description:
          - The primary key of the object (team/organization) this assignment applies to.
          - A null value indicates system-wide assignment.
        required: False
        type: int
    object_ansible_id:
        description:
            - Resource id of the object this role applies to. Alternative to the object_id field.
        required: False
        type: str
    team:
        description:
          - The name or id of the user to assign to the object.
        required: False
        type: str
    team_ansible_id:
        description:
          - Resource id of the user who will receive permissions from this assignment. Alternative to I(team) field.
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
- name: Role Team assignment
  ansible.platform.role_team_assignment:
     role_definition: "Organization Inventory Admin"
     assignment_object:
        name: "Engineering"
        type: "organizations"
     team: APAC-BLR
     state: present
- name: Role Team assignment
  ansible.platform.role_team_assignment:
     role_definition: "Organization Inventory Admin"
     assignment_object:
        name: "Engineering"
        type: "organizations"
     team: APAC-BLR
     state: absent
...
'''

from ..module_utils.aap_module import AAPModule


def main():
    # Any additional arguments that are not fields of the item can be added here
    argument_spec = dict(
        role_definition=dict(required=True, type='str'),
        object_id=dict(required=False, type='int'),
        object_ansible_id=dict(required=False, type='str'),
        team=dict(required=False, type='str'),
        assignment_object=dict(
            type="dict",
            required=False,
            options=dict(
                name=dict(type="str", required=True),
                type=dict(type="str", required=True),
            ),
        ),
        team_ansible_id=dict(required=False, type='str'),
        state=dict(default='present', choices=['present', 'absent', 'exists']),
    )
    module = AAPModule(
        argument_spec=argument_spec,
        mutually_exclusive=[
            ('team', 'team_ansible_id'),
            ('object_id', 'object_ansible_id', 'assignment_object'),
        ],
        required_one_of=[
            ('team', 'team_ansible_id'),
            ('object_id', 'object_ansible_id', 'assignment_object'),
        ],
    )
    team_param = module.params.get('team')
    object_id = module.params.get('object_id')
    role_definition_str = module.params.get('role_definition')
    object_ansible_id = module.params.get('object_ansible_id')
    assignment_object = module.params.get("assignment_object")
    team_ansible_id = module.params.get('team_ansible_id')
    state = module.params.get('state')

    role_definition = module.get_one('role_definitions', allow_none=False, name_or_id=role_definition_str)
    team = module.get_one('teams', allow_none=True, name_or_id=team_param)

    kwargs = {
        'role_definition': role_definition['id'],
    }

    if object_id is not None:
        kwargs['object_id'] = object_id
    if team is not None:
        kwargs['team'] = team['id']
    if object_ansible_id is not None:
        kwargs['object_ansible_id'] = object_ansible_id
    if team_ansible_id is not None:
        kwargs['team_ansible_id'] = team_ansible_id
    if assignment_object:
        type = assignment_object['type']
        name = assignment_object['name']
        obj = module.get_one(type, allow_none=True, name_or_id=name)
        if obj is None:
            module.fail_json(msg=f"Object with name '{name}' not found")
        kwargs['object_id'] = obj['id']

    role_team_assignment = module.get_one('role_team_assignments', **{'data': kwargs})

    if state == 'exists':
        if role_team_assignment is None:
            module.fail_json(
                msg=f'Team role assignment does not exist: {role_definition_str}, '
                f'user: {team_param or team_ansible_id}, object: {object_id or object_ansible_id}'
            )
        module.exit_json(**module.json_output)

    elif state == 'absent':
        module.delete_if_needed(role_team_assignment)

    elif state == 'present':
        module.create_if_needed(
            role_team_assignment,
            kwargs,
            endpoint='role_team_assignments',
            item_type='role_team_assignment',
        )


if __name__ == '__main__':
    main()
