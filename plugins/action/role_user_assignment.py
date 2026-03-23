#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.role_user_assignment module.

Assigns or removes a role for a user against one or more objects (teams/orgs).
Handles multi-object iteration at the action plugin level; FK resolution and
API calls are delegated to manager.execute() via the transform mixin.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
import time
from dataclasses import asdict

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.role_user_assignment import AnsibleRoleUserAssignment

logger = logging.getLogger(__name__)


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for role_user_assignment module."""

    MODULE_NAME = 'role_user_assignment'

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = dict()

        self._task_vars = task_vars
        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp

        action_start = time.perf_counter()

        auth_params = [
            'gateway_hostname', 'gateway_username', 'gateway_password',
            'gateway_token', 'gateway_validate_certs', 'gateway_request_timeout',
            'aap_hostname', 'aap_username', 'aap_password', 'aap_token',
            'aap_validate_certs', 'aap_request_timeout',
        ]

        try:
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                from ansible.errors import AnsibleError
                raise AnsibleError("Could not load DOCUMENTATION for role_user_assignment module")

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
            user_param = validated_params.get('user')
            user_ansible_id = validated_params.get('user_ansible_id')
            object_id = validated_params.get('object_id')
            object_ids = validated_params.get('object_ids')
            object_ansible_id = validated_params.get('object_ansible_id')

            # Determine entity type from role_definition prefix so we can
            # resolve object names (strings) to integer IDs.
            _role_type_map = {
                'Team': 'teams',
                'Organization': 'organizations',
            }
            entity_type = next(
                (mapped for prefix, mapped in _role_type_map.items()
                 if role_definition_str and role_definition_str.startswith(prefix)),
                None,
            )

            # Collect list of object ids to iterate over
            if object_ids is not None:
                objects_to_process = list(object_ids)
            elif object_id is not None:
                objects_to_process = [object_id]
            else:
                objects_to_process = [None]  # Assign without object (platform-level)

            overall_changed = False
            assignments = []

            for obj in objects_to_process:
                # Build an AnsibleRoleUserAssignment for this single object
                assignment_data = {
                    'role_definition': role_definition_str,
                }
                if user_param is not None:
                    assignment_data['user'] = user_param
                if user_ansible_id is not None:
                    assignment_data['user_ansible_id'] = user_ansible_id
                if obj is not None:
                    # Resolve object name → integer ID when possible.
                    resolved_obj = None
                    if str(obj).isdigit():
                        resolved_obj = int(obj)
                    elif entity_type:
                        # obj is a name string — resolve to integer ID.
                        # Primary: fast lookup_resource_id (single GET with name filter).
                        try:
                            resolved_obj = manager.lookup_resource_id(entity_type, 'name', str(obj))
                        except Exception as _lookup_exc:
                            logger.debug(
                                "role_user_assignment: lookup_resource_id('%s', 'name', '%s') failed: %s",
                                entity_type, obj, _lookup_exc
                            )

                        # Secondary fallback: use execute('find') for the entity module.
                        # This uses the module's own transform mixin (a proven code path).
                        # Only applicable for organizations — teams require 'organization'
                        # as a required field which we may not have here.
                        if resolved_obj is None and entity_type == 'organizations':
                            try:
                                _found = manager.execute(
                                    operation='find',
                                    module_name='organization',
                                    ansible_data={'name': str(obj)},
                                )
                                if _found and _found.get('id'):
                                    resolved_obj = int(_found['id'])
                                    logger.debug(
                                        "role_user_assignment: secondary find resolved '%s' → id=%s",
                                        obj, resolved_obj
                                    )
                            except Exception as _find_exc:
                                logger.debug(
                                    "role_user_assignment: secondary find('organization', name='%s') failed: %s",
                                    obj, _find_exc
                                )

                    if resolved_obj is None and not str(obj).isdigit():
                        # Both lookup paths failed — cannot send a name string as
                        # object_id to the API ("Expected pk value, received str.").
                        # Fail early with a useful message.
                        raise ValueError(
                            "Cannot resolve object name '%s' (entity type: '%s') to an "
                            "integer ID. Ensure the %s exists on the gateway or pass an "
                            "integer object_id instead."
                            % (obj, entity_type or "unknown", entity_type or "resource")
                        )

                    if resolved_obj is None:
                        # entity_type was unknown — keep obj as-is; the transform mixin
                        # will attempt its own resolution and raise if it also fails.
                        resolved_obj = obj

                    assignment_data['object_id'] = resolved_obj
                if object_ansible_id is not None:
                    assignment_data['object_ansible_id'] = object_ansible_id

                assignment = AnsibleRoleUserAssignment(**assignment_data)
                ansible_data = asdict(assignment)

                # Try to find existing assignment via manager.execute('find')
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
                                "Role user assignment does not exist: role='%s', "
                                "user='%s', object='%s'"
                                % (role_definition_str, user_param or user_ansible_id, obj)
                            ),
                        })
                        return result
                    assignments.append(existing)

                elif state == 'absent':
                    if existing and existing.get('id'):
                        if not self._task.check_mode:
                            # Set id on the ansible_data for delete
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

            if len(assignments) == 1:
                primary = assignments[0]
            else:
                primary = {'assignments': assignments}

            result.update({
                'changed': overall_changed,
                'failed': False,
                self.MODULE_NAME: primary,
                'id': primary.get('id') if len(assignments) == 1 else None,
                'assignments': assignments,
            })

            result.setdefault('_timing', {})['action_plugin_time'] = time.perf_counter() - action_start

        except Exception as e:
            import traceback
            self._display.vvv("Error in role_user_assignment action plugin: %s" % e)
            result['failed'] = True
            result['msg'] = str(e)
            if self._display.verbosity >= 3:
                result['exception'] = traceback.format_exc()

        return result
