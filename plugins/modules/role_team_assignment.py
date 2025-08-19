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
    assignment_objects:
        description:
            - List of dicts mapping resource names to their types.
            - When using name, each dict must include C(name) and C(type).
        type: list
        elements: dict
        suboptions:
            name:
                description:
                  - The object name (e.g. organization/team name).
                  - Internally resolved into its ansible_id.
                type: str
                required: False
            type:
                description: The object type (e.g. C(organizations), C(teams)).
                type: str
                required: true
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
    role_definition:
        description:
            - The role definition which defines permissions conveyed by this assignment.
        required: True
        type: str
    team:
        description:
          - The name or id of the team to assign to the object.
        required: False
        type: str
    team_ansible_id:
        description:
          - Resource id of the team who will receive permissions from this assignment. Alternative to I(team) field.
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
    team: "APAC-BLR"
    assignment_objects:
      - object_ansible_id: "Engineering"
      role_definition: Organization Inventory Admin
      state: present
    register: result

- name: Role Team assignment
  ansible.platform.role_team_assignment:
    team: "APAC-BLR"
    assignment_objects:
      - object_ansible_id: "Engineering"
      role_definition: Organization Inventory Admin
      state: exist
    register: result

- name: Role Team assignment
  ansible.platform.role_team_assignment:
    team: "APAC-BLR"
    assignment_objects:
      - object_ansible_id: "Engineering"
      role_definition: Organization Inventory Admin
      state: absent
    register: result
...
'''

from ..module_utils.aap_module import AAPModule


def assign_team_role(module, auto_exit=False, **role_args):
    """
    Assigns a team role to a specific object.
    Args:
        module:(AAPModule) Ansible module instance.
        auto_exit:(bool) If True, the module will exit automatically after the operation.
        role_args:(dict) role assignment parameters.
    """
    if role_args.get('state') == 'exists' and not role_args.get('role_team_assignment'):

        module.fail_json(
            msg=(
                f"Team role assignment does not exist: {role_args.get('role_definition_str')}, "
                f"team: {role_args.get('team_param') or role_args.get('team_ansible_id')}, "
                f"object: {role_args.get('object_id') or role_args.get('object_ansible_id')}"
            )
        )

        module.exit_json(**module.json_output)

    elif role_args.get('state') == 'absent':
        module.delete_if_needed(role_args.get('role_team_assignment'))

    elif role_args.get('state') == 'present':
        module.create_if_needed(
            role_args.get('role_team_assignment'),
            role_args.get('kwargs'),
            endpoint='role_team_assignments',
            item_type='role_team_assignment',
            auto_exit=auto_exit
        )
    return

def main():
    # Any additional arguments that are not fields of the item can be added here
    argument_spec = dict(
        role_definition=dict(required=True, type='str'),
        team=dict(required=False, type='str'),
        assignment_objects=dict(required=False, type='list', elements='dict', options=dict(
            name=dict(type='str', required=False),
            type=dict(type='str', required=False),
            object_id=dict(required=False, type='int'),
            object_ansible_id=dict(required=False, type='str'),
        )),
        team_ansible_id=dict(required=False, type='str'),
        state=dict(default='present', choices=['present', 'absent', 'exists']),
    )
    module = AAPModule(
        argument_spec=argument_spec,
        mutually_exclusive=[
            ('team', 'team_ansible_id'),
        ],
        required_one_of=[
            ('team', 'team_ansible_id'),
        ],
    )
    team_param = module.params.get('team')
    role_definition_str = module.params.get('role_definition')
    assignment_objects = module.params.get("assignment_objects")
    team_ansible_id = module.params.get('team_ansible_id')
    state = module.params.get('state')

    role_definition = module.get_one('role_definitions', allow_none=False, name_or_id=role_definition_str)
    team = module.get_one('teams', allow_none=True, name_or_id=team_param)


    kwargs = {
        'role_definition': role_definition['id'],
    }
    if team:
        kwargs['team'] = team['id']
    if team_ansible_id is not None:
        kwargs['team_ansible_id'] = team_ansible_id

    role_map = {
        'Team': 'teams',
        'Organization': 'organizations',
    }

    entity_type = next((
        mapped
        for prefix, mapped in role_map.items()
        if role_definition_str.startswith(prefix)
    ), None)
    object_param = assignment_objects

    role_args = {
        'role_definition_str': role_definition_str,
        'team_param': team_param,
        'team_ansible_id': team_ansible_id,
        'state': state,
        'kwargs': kwargs,
    }
    if role_definition_str.lower().startswith('platform') and role_definition["id"] == 1:
        role_team_assignment = module.get_one('role_team_assignments', **{'data': kwargs})
        role_args['role_team_assignment'] = role_team_assignment
        assign_team_role(module, **role_args)

    elif entity_type and object_param:

        for entity in object_param:
            if entity['name'] and entity['type']:
                obj = module.get_one(entity['type'], allow_none=False, name_or_id=entity['name'])
            elif entity['object_id']:
                obj = module.get_one(entity['object_id'], allow_none=False, name_or_id=entity['object_id'])
            else:
                obj = module.get_one(entity['object_ansible_id'], allow_none=False, name_or_id=entity['object_ansible_id'])

            if obj is None:
                module.fail_json(msg=f"Unable to find {entity['type']} with name {entity['name']}")
            entity_id = obj['id']

            if entity_id:
                kwargs['object_id'] = entity_id

            role_team_assignment = module.get_one('role_team_assignments', **{'data': kwargs})
            role_args['role_team_assignment'] = role_team_assignment

            assign_team_role(module, **role_args)

    module.exit_json(**module.json_output)


if __name__ == '__main__':
    main()
