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
            - This option is deprecated and will be removed in a release after 2026-01-31.
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

from ..module_utils.aap_module import AAPModule


def assign_user_role(module, auto_exit=False, **role_args):
    """
    Assigns a user role to a specific object.
    Args:
        module:(AAPModule) Ansible module instance.
        auto_exit:(bool) If True, the module will exit automatically after the operation.
        role_args:(dict) role assignment parameters.
    """
    if role_args.get('state') == 'exists' and not role_args.get('role_user_assignment'):

        module.fail_json(
            msg=(
                f"User role assignment does not exist: {role_args.get('role_definition_str')}, "
                f"user: {role_args.get('user_param') or role_args.get('user_ansible_id')}, "
                f"object: {role_args.get('object_id') or role_args.get('object_ansible_id')}"
            )
        )

        module.exit_json(**module.json_output)

    elif role_args.get('state') == 'absent':
        module.delete_if_needed(role_args.get('role_user_assignment'))

    elif role_args.get('state') == 'present':
        module.create_if_needed(
            role_args.get('role_user_assignment'),
            role_args.get('kwargs'),
            endpoint='role_user_assignments',
            item_type='role_user_assignment',
            auto_exit=auto_exit
        )
    return


def main():
    # Any additional arguments that are not fields of the item can be added here
    argument_spec = dict(
        user=dict(required=False, type='str'),
        object_id=dict(required=False, type="int"),
        object_ids=dict(required=False, type='list', elements='str'),
        role_definition=dict(required=True, type='str'),
        object_ansible_id=dict(required=False, type='str'),
        user_ansible_id=dict(required=False, type='str'),
        state=dict(default='present', choices=['present', 'absent', 'exists']),
    )

    module = AAPModule(
        argument_spec=argument_spec,
        mutually_exclusive=[
            ('user', 'user_ansible_id'),
            ('object_ids', 'object_ansible_id'),
            ('object_ids', 'object_id'),
            ('object_id', 'object_ansible_id')
        ],
    )

    user_param = module.params.get('user')
    object_id = module.params.get('object_id')
    object_ids = module.params.get('object_ids')
    role_definition_str = module.params.get('role_definition')
    object_ansible_id = module.params.get('object_ansible_id')
    user_ansible_id = module.params.get('user_ansible_id')
    state = module.params.get('state')

    role_definition = module.get_one('role_definitions', allow_none=False, name_or_id=role_definition_str)
    user = module.get_one('users', allow_none=True, name_or_id=user_param)

    kwargs = {
        'role_definition': role_definition['id'],
    }

    if object_id:
        object_id = [object_id]
        kwargs['object_id'] = [object_id]
        module.deprecate(
            msg="The usage of 'object_id' parameter in the 'role_user_assignment' module is not recommended. "
            "For associating a user to team(s)/organization(s), please use the 'object_ids' parameter. ",
            date="2026-01-31",
            collection_name="ansible.platform",
        )
    if object_ids is not None:
        kwargs['object_id'] = object_ids
    if user is not None:
        kwargs['user'] = user['id']
    if user_ansible_id is not None:
        kwargs['user_ansible_id'] = user_ansible_id

    role_map = {
        'Team': 'teams',
        'Organization': 'organizations',
    }

    entity_type = next((
        mapped
        for prefix, mapped in role_map.items()
        if role_definition_str.startswith(prefix)
    ), None)
    object_param = object_ids or object_id

    role_args = {
        'role_definition_str': role_definition_str,
        'user_param': user_param,
        'user_ansible_id': user_ansible_id,
        'state': state,
        'kwargs': kwargs,
    }

    if role_definition_str.lower().startswith('platform') and role_definition["id"] == 1:
        role_user_assignment = module.get_one('role_user_assignments', **{'data': kwargs})
        role_args['role_user_assignment'] = role_user_assignment
        assign_user_role(module, **role_args)

    elif entity_type and object_param:

        for entity in object_param:

            if not isinstance(entity, int):
                response = module.get_one(entity_type, allow_none=True, name_or_id=entity)
                if response is None:
                    module.fail_json(
                        msg=f"Unable to find {entity_type} with name or id: {entity}"
                    )
                entity = response.get('id')

            if entity:
                kwargs['object_id'] = entity

            role_user_assignment = module.get_one('role_user_assignments', **{'data': kwargs})
            role_args['role_user_assignment'] = role_user_assignment

            assign_user_role(module, **role_args)

    elif object_ansible_id:
        kwargs["object_ansible_id"] = object_ansible_id
        role_user_assignment = module.get_one('role_user_assignments', **{'data': kwargs})
        role_args['role_user_assignment'] = role_user_assignment
        assign_user_role(module, **role_args)

    module.exit_json(**module.json_output)


if __name__ == '__main__':
    main()
