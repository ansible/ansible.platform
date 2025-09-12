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
                required: False
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
- name: Assign roles for multiple objects using names
  ansible.platform.role_team_assignment:
    assignment_objects:
      - name: "{{ org1.name }}"
        type: "organizations"
      - name: "{{ org2.name }}"
        type: "organizations"
    role_definition: Organization Inventory Admin
    team: "{{ team2.name }}"
    state: present
  register: result

- name: Delete team role assignments for multiple objects using names
  ansible.platform.role_team_assignment:
    assignment_objects:
      - name: "{{ org1.name }}"
        type: "organizations"
      - name: "{{ org2.name }}"
        type: "organizations"
    role_definition: Organization Inventory Admin
    team: "{{ team2.name }}"
    state: absent
  register: result

- name: Role Team assignment using object_ansible_id
  ansible.platform.role_team_assignment:
    team: "APAC-BLR"
    assignment_objects:
      - object_ansible_id: "c891b9f7-cc08-4b62-9843-c9ebfda362a8"
    role_definition: Organization Inventory Admin
    state: present
    register: result

- name: Check Role Team assignment exists
  ansible.platform.role_team_assignment:
    team: "APAC-BLR"
    assignment_objects:
      - object_ansible_id: "c891b9f7-cc08-4b62-9843-c9ebfda362a8"
    role_definition: Organization Inventory Admin
    state: exists
    register: result

- name: Role Team assignment
  ansible.platform.role_team_assignment:
    team: "APAC-BLR"
    assignment_objects:
      - object_ansible_id: "c891b9f7-cc08-4b62-9843-c9ebfda362a8"
    role_definition: Organization Inventory Admin
    state: absent
    register: result
...
'''

from ..module_utils.aap_module import AAPModule


def assign_team_role(module, state, role_team_assignment, kwargs,
                     role_definition_str, team_param, team_ansible_id, auto_exit=False):
    """
    Create/delete/assert a team role assignment.s.
    """
    if state == 'exists':
        if not role_team_assignment:
            module.fail_json(
                msg=(
                    "Team role assignment does not exist: %s, team: %s"
                    % (role_definition_str, team_param or team_ansible_id)
                )
            )
    elif state == 'absent':
        module.delete_if_needed(role_team_assignment, auto_exit=auto_exit)

    elif state == 'present':
        module.create_if_needed(
            role_team_assignment,
            kwargs,
            endpoint='role_team_assignments',
            item_type='role_team_assignment',
            auto_exit=auto_exit
        )
    return


def _validate_selector(entry, module):
    """
    Enforce exactly one selector per item:
      EITHER (name AND type) OR object_id OR object_ansible_id.
    If 'name' is used, 'type' is required.
    """
    has_name = bool(entry.get('name'))
    has_type = bool(entry.get('type'))
    has_pk = entry.get('object_id') is not None
    has_uuid = bool(entry.get('object_ansible_id'))

    # If name is present, type must be present (and vice versa)
    if has_name ^ has_type:
        module.fail_json(msg="When using 'name', you must also provide 'type' in each assignment_objects item.")

    count = (1 if (has_name and has_type) else 0) + (1 if has_pk else 0) + (1 if has_uuid else 0)
    if count == 0:
        module.fail_json(
            msg="Each assignment_objects item must include exactly one of: "
                "(name & type) OR object_id OR object_ansible_id."
        )
    if count > 1:
        module.fail_json(
            msg="Each assignment_objects item must not include more than one of: "
                "(name & type), object_id, object_ansible_id."
        )

    # Optional: constrain allowed types for name-based lookup
    if has_name and has_type:
        allowed = ("organizations", "teams")  # extend if/when we support more
        if entry["type"] not in allowed:
            module.fail_json(msg=f"Unsupported type '{entry['type']}'. Valid types: {', '.join(allowed)}")


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
    results = []

    if role_definition_str.lower().startswith('platform') and role_definition["id"] == 1:
        role_team_assignment = module.get_one('role_team_assignments', **{'data': kwargs})
        assign_team_role(module, state, role_team_assignment, kwargs,
                         role_definition_str, team_param, team_ansible_id)

    elif entity_type and object_param:
        for entity in object_param:
            _validate_selector(entity, module)

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
            assign_team_role(module, state, role_team_assignment, kwargs,
                             role_definition_str, team_param, team_ansible_id)

            # copy current state before it gets overwritten
            results.append(module.json_output.copy())

    # At the end, return *all* results
    module.exit_json(changed=any(r.get("changed", False) for r in results), assignments=results)


if __name__ == '__main__':
    main()
