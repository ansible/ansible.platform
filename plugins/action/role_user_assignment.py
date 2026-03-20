#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.role_user_assignment module.

Assigns or removes a role for a user against one or more objects (teams/orgs).
Handles FK resolution (role_definition, user, objects) and multi-object iteration.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
import time

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin

logger = logging.getLogger(__name__)


def _resolve_id(manager, endpoint, lookup_field, value, api_version):
    """Resolve a name or id to an integer id."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    try:
        return manager.lookup_resource_id(endpoint, lookup_field, s)
    except Exception:
        return None


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

            # Detect API version
            if manager.api_version is None:
                try:
                    manager.api_version = manager._detect_api_version()
                except Exception:
                    manager.api_version = '1'

            api_version = manager.api_version
            assignments_base = '/api/gateway/v%s/role_user_assignments/' % api_version

            role_definition_str = validated_params.get('role_definition')
            user_param = validated_params.get('user')
            user_ansible_id = validated_params.get('user_ansible_id')
            object_id = validated_params.get('object_id')
            object_ids = validated_params.get('object_ids')
            object_ansible_id = validated_params.get('object_ansible_id')

            # Resolve role_definition -> id
            role_def_id = _resolve_id(
                manager, 'role_definitions', 'name', role_definition_str, api_version
            )
            if role_def_id is None:
                result.update({
                    'changed': False,
                    'failed': True,
                    'msg': "Could not find role_definition: '%s'" % role_definition_str,
                })
                return result

            # Resolve user -> id
            user_id = None
            if user_param is not None:
                user_id = _resolve_id(manager, 'users', 'username', user_param, api_version)

            # Map role prefix to endpoint for object resolution
            role_map = {
                'Team': 'teams',
                'Organization': 'organizations',
            }
            entity_type = next(
                (mapped for prefix, mapped in role_map.items()
                 if role_definition_str and role_definition_str.startswith(prefix)),
                None
            )

            # Build base kwargs for assignment API
            base_kwargs = {'role_definition': role_def_id}
            if user_id is not None:
                base_kwargs['user'] = user_id
            if user_ansible_id is not None:
                base_kwargs['user_ansible_id'] = user_ansible_id

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
                kwargs = dict(base_kwargs)
                resolved_obj_id = None

                if obj is not None:
                    # Resolve object name -> id if entity_type is known
                    if entity_type and not str(obj).isdigit():
                        resolved_obj_id = _resolve_id(
                            manager, entity_type,
                            'name' if entity_type == 'organizations' else 'name',
                            str(obj), api_version
                        )
                        if resolved_obj_id is None:
                            result.update({
                                'changed': False,
                                'failed': True,
                                'msg': "Could not find %s: '%s'" % (entity_type, obj),
                            })
                            return result
                    else:
                        resolved_obj_id = int(obj) if str(obj).isdigit() else obj

                    if resolved_obj_id is not None:
                        kwargs['object_id'] = resolved_obj_id

                if object_ansible_id is not None:
                    kwargs['object_ansible_id'] = object_ansible_id

                # Find existing assignment
                existing_assignment = self._find_assignment(
                    manager, assignments_base, kwargs
                )

                if state == 'exists':
                    if not existing_assignment:
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
                    assignments.append(existing_assignment)

                elif state == 'absent':
                    if existing_assignment:
                        if not self._task.check_mode:
                            delete_path = '%s%s/' % (assignments_base, existing_assignment['id'])
                            manager.direct_request('DELETE', delete_path)
                        overall_changed = True
                        assignments.append({'state': 'absent', 'id': existing_assignment['id']})

                else:  # state == 'present'
                    if existing_assignment:
                        assignments.append(existing_assignment)
                    else:
                        if not self._task.check_mode:
                            created = manager.direct_request('POST', assignments_base, data=kwargs)
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

    def _find_assignment(self, manager, base_path, kwargs):
        """Find an existing role_user_assignment matching the given kwargs."""
        from urllib.parse import urlencode
        query_params = {k: v for k, v in kwargs.items() if v is not None}
        url = base_path
        if query_params:
            url = '%s?%s' % (base_path, urlencode(query_params))
        try:
            response = manager.direct_request('GET', url)
            results = response.get('results', [])
            if results:
                return results[0]
        except Exception:
            pass
        return None
