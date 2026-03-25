#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.route module.

Uses the persistent connection manager architecture.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
import time
from dataclasses import asdict

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.route import AnsibleRoute

logger = logging.getLogger(__name__)


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for route module."""

    MODULE_NAME = 'route'

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
                raise AnsibleError("Could not load DOCUMENTATION for route module")

            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, 'input')
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result['ansible_facts'] = facts_to_set
                result['_ansible_facts_cacheable'] = True

            validated_params = validated_input.validated_parameters

            # Client-side validation: mTLS and gateway auth are mutually exclusive
            if validated_params.get('enable_mtls') and validated_params.get('enable_gateway_auth'):
                raise ValueError("Mutual TLS can only be enabled when gateway auth is disabled")

            resource_data = {
                k: v for k, v in validated_params.items()
                if v is not None and k not in auth_params
            }
            resource = AnsibleRoute(**resource_data)

            # Null out dataclass fields NOT explicitly provided by the user so that
            # the manager's secondary idempotency comparison skips them.  Without
            # this, dataclass defaults (e.g. enable_mtls=False, is_service_https=False)
            # are serialised into ansible_data and compared against the API response
            # which may not return those fields, triggering spurious changed=True.
            user_provided_keys = set(resource_data.keys())
            for _field in list(vars(resource).keys()):
                if _field not in user_provided_keys:
                    setattr(resource, _field, None)

            operation = self._detect_operation(validated_params)

            # Idempotent create: find by name, then update if exists
            if operation == 'create' and validated_params.get('state') == 'present':
                try:
                    find_result = manager.execute(
                        operation='find',
                        module_name=self.MODULE_NAME,
                        ansible_data={'name': resource.name}
                    )
                    if find_result and find_result.get('id'):
                        operation = 'update'
                        resource.id = find_result.get('id')
                except Exception:
                    pass

            # Delete: find by name to get id if not provided
            if operation == 'delete' and not resource.id:
                try:
                    find_result = manager.execute(
                        operation='find',
                        module_name=self.MODULE_NAME,
                        ansible_data={'name': resource.name}
                    )
                    if find_result and find_result.get('id'):
                        resource.id = find_result.get('id')
                    else:
                        result.update({
                            'changed': False,
                            'failed': False,
                            self.MODULE_NAME: {'state': 'absent'},
                            'msg': "Route '%s' does not exist (already absent)" % resource.name,
                        })
                        return result
                except Exception:
                    result.update({
                        'changed': False,
                        'failed': False,
                        self.MODULE_NAME: {'state': 'absent'},
                        'msg': "Route '%s' does not exist (already absent)" % resource.name,
                    })
                    return result

            if operation == 'enforced':
                operation = 'update'

            ansible_data = asdict(resource)
            if operation == 'update' and validated_params.get('state') == 'enforced':
                ansible_data['_platform_enforced'] = True

            if self._task.check_mode and operation in ('create', 'update', 'delete'):
                if operation == 'delete':
                    result.update({'changed': bool(resource.id), 'failed': False,
                                   self.MODULE_NAME: {'state': 'absent'}})
                else:
                    result.update({'changed': True, 'failed': False,
                                   self.MODULE_NAME: {'name': resource.name},
                                   'id': resource.id, 'name': resource.name})
                return result

            try:
                manager_result = manager.execute(
                    operation=operation,
                    module_name=self.MODULE_NAME,
                    ansible_data=ansible_data
                )
            except ValueError as e:
                if operation == 'find' and ('not found' in str(e).lower() or 'resource with' in str(e).lower()):
                    result.update({'changed': False, 'failed': False,
                                   self.MODULE_NAME: {}, 'exists': False,
                                   'msg': "Route '%s' does not exist" % resource.name})
                    return result
                raise

            read_only_fields = {'id', 'created', 'modified', 'url'}
            argspec_fields = set(argspec.get('argument_spec', {}).keys())
            filtered_result = {
                k: v for k, v in manager_result.items()
                if k in argspec_fields or k in read_only_fields
            }
            try:
                validated_output = self._validate_data(
                    {k: v for k, v in filtered_result.items() if k in argspec_fields},
                    argspec, 'output'
                )
                for field in read_only_fields:
                    if field in filtered_result:
                        validated_output[field] = filtered_result[field]
            except Exception:
                validated_output = manager_result

            result.update({
                'changed': manager_result.get('changed', False),
                'failed': False,
                self.MODULE_NAME: validated_output,
                'id': validated_output.get('id'),
                'name': validated_output.get('name'),
            })
            if operation == 'find':
                result['exists'] = bool(validated_output.get('id'))
            elif operation == 'delete':
                result[self.MODULE_NAME]['state'] = 'absent'

            timing = manager_result.get('_timing', {})
            result.setdefault('_timing', {})['action_plugin_time'] = time.perf_counter() - action_start
            result['_timing']['manager_processing_time'] = timing.get('manager_processing_time', 0)
            result['_timing']['api_call_time'] = timing.get('api_call_time', 0)

        except Exception as e:
            import traceback
            self._display.vvv("Error in route action plugin: %s" % e)
            result['failed'] = True
            result['msg'] = str(e)
            if self._display.verbosity >= 3:
                result['exception'] = traceback.format_exc()

        return result
