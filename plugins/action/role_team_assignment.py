#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.role_team_assignment module.

Assigns or removes a role for a team against one or more objects
(organizations, teams, etc.).  Multi-object iteration happens at
the action plugin level; FK resolution and API calls are delegated
to manager.execute() via the transform mixin.

Supports two ways to specify the target object(s):
  - assignment_objects: list of dicts with name+type, object_id, or
    object_ansible_id.  Allows name-based lookup for organisations /
    teams.
  - object_id / object_ids / object_ansible_id: direct selectors,
    identical to role_user_assignment style.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
from dataclasses import asdict

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.role_team_assignment import AnsibleRoleTeamAssignment

logger = logging.getLogger(__name__)


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for role_team_assignment module."""

    MODULE_NAME = 'role_team_assignment'

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = dict()

        self._task_vars = task_vars
        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp

        try:
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                from ansible.errors import AnsibleError
                raise AnsibleError("Could not load DOCUMENTATION for role_team_assignment module")

            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, 'input')
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result['ansible_facts'] = facts_to_set
                result['_ansible_facts_cacheable'] = True

            validated_params = validated_input.validated_parameters
            state = validated_params.get('state', 'present')

            role_definition_str = validated_params.get('role_definition')
            team_param = validated_params.get('team')
            team_ansible_id = validated_params.get('team_ansible_id')

            # Build the list of (object_id, object_ansible_id) pairs to iterate.
            # Priority: assignment_objects > object_ids > object_id > bare (platform-level).
            assignment_objects = validated_params.get('assignment_objects') or []
            object_id = validated_params.get('object_id')
            object_ids = validated_params.get('object_ids')
            object_ansible_id = validated_params.get('object_ansible_id')

            objects_to_process = []  # list of (resolved_object_id, object_ansible_id)

            if assignment_objects:
                for entry in assignment_objects:
                    entry_object_id = entry.get('object_id')
                    entry_object_ansible_id = entry.get('object_ansible_id')
                    entry_name = entry.get('name')
                    entry_type = entry.get('type')

                    if entry_name and entry_type:
                        # Resolve name → id via manager
                        resolved = manager.lookup_resource_id(entry_type, 'name', entry_name)
                        objects_to_process.append((resolved, None))
                    elif entry_object_ansible_id:
                        objects_to_process.append((None, entry_object_ansible_id))
                    elif entry_object_id is not None:
                        objects_to_process.append((int(entry_object_id), None))
                    else:
                        objects_to_process.append((None, None))

            elif object_ids is not None:
                for oid in object_ids:
                    objects_to_process.append((int(oid) if str(oid).isdigit() else oid, None))
            elif object_id is not None:
                objects_to_process.append((object_id, None))
            elif object_ansible_id is not None:
                objects_to_process.append((None, object_ansible_id))
            else:
                objects_to_process.append((None, None))  # platform-level (no object)

            overall_changed = False
            assignments = []

            for obj_id, obj_ansible_id in objects_to_process:
                assignment_data = {
                    'role_definition': role_definition_str,
                }
                if team_param is not None:
                    assignment_data['team'] = team_param
                if team_ansible_id is not None:
                    assignment_data['team_ansible_id'] = team_ansible_id
                if obj_id is not None:
                    assignment_data['object_id'] = obj_id
                if obj_ansible_id is not None:
                    assignment_data['object_ansible_id'] = obj_ansible_id

                assignment = AnsibleRoleTeamAssignment(**assignment_data)
                ansible_data = asdict(assignment)

                # Try to find existing assignment
                existing = None
                try:
                    existing = manager.execute(
                        operation='find',
                        module_name=self.MODULE_NAME,
                        ansible_data=ansible_data,
                    )
                except (ValueError, Exception):
                    existing = None

                if state == 'exists':
                    if not existing or not existing.get('id'):
                        result.update({
                            'changed': False,
                            'failed': True,
                            'msg': (
                                "Role team assignment does not exist: role='%s', "
                                "team='%s', object='%s'"
                                % (role_definition_str, team_param or team_ansible_id, obj_id or obj_ansible_id)
                            ),
                        })
                        return result
                    assignments.append(existing)

                elif state == 'absent':
                    if existing and existing.get('id'):
                        if not self._task.check_mode:
                            ansible_data['id'] = existing['id']
                            manager.execute(
                                operation='delete',
                                module_name=self.MODULE_NAME,
                                ansible_data=ansible_data,
                            )
                        overall_changed = True
                        assignments.append({'state': 'absent', 'id': existing['id']})

                else:  # state == 'present'
                    if existing and existing.get('id'):
                        assignments.append(existing)
                    else:
                        if not self._task.check_mode:
                            created = manager.execute(
                                operation='create',
                                module_name=self.MODULE_NAME,
                                ansible_data=ansible_data,
                            )
                            assignments.append(created)
                        overall_changed = True

            # Clean each individual assignment in the list
            _internal_keys = {'_timing', 'changed'}
            _api_readonly = {'created', 'modified', 'url'}
            _excluded = _internal_keys | _api_readonly

            def _clean_assignment(a):
                if not isinstance(a, dict):
                    return a
                return {k: v for k, v in a.items() if k not in _excluded}

            cleaned_assignments = [_clean_assignment(a) for a in assignments]
            if len(cleaned_assignments) == 1:
                primary = cleaned_assignments[0]
            else:
                primary = {'assignments': cleaned_assignments}

            result.update({
                'changed': overall_changed,
                'failed': False,
                self.MODULE_NAME: primary,
            })

        except Exception as e:
            import traceback
            self._display.vvv("Error in role_team_assignment action plugin: %s" % e)
            result['failed'] = True
            result['msg'] = str(e)
            if self._display.verbosity >= 3:
                result['exception'] = traceback.format_exc()

        return result
