#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.organization module.

This action plugin uses the persistent connection manager architecture.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
from dataclasses import asdict

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.organization import AnsibleOrganization

logger = logging.getLogger(__name__)


class ActionModule(BaseResourceActionPlugin):
    """
    Action plugin for organization module.

    Uses the persistent connection manager architecture for improved performance.
    """

    MODULE_NAME = 'organization'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = dict()

        self._task_vars = task_vars
        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp

        auth_params = [
            'gateway_hostname', 'gateway_username', 'gateway_password',
            'gateway_token', 'gateway_validate_certs', 'gateway_request_timeout',
            'aap_hostname', 'aap_username', 'aap_password', 'aap_token',
            'aap_validate_certs', 'aap_request_timeout'
        ]

        try:
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                from ansible.errors import AnsibleError
                raise AnsibleError("Could not load DOCUMENTATION for organization module")
            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, 'input')
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result['ansible_facts'] = facts_to_set
                result['_ansible_facts_cacheable'] = True

            validated_params = validated_input.validated_parameters
            org_data = {
                k: v for k, v in validated_params.items()
                if v is not None and k not in auth_params
            }
            org = AnsibleOrganization(**org_data)
            operation = self._detect_operation(validated_params)

            # Idempotent create: find by name, then update if exists
            if operation == 'create' and validated_params.get('state') == 'present':
                try:
                    find_result = manager.execute(
                        operation='find',
                        module_name=self.MODULE_NAME,
                        ansible_data={'name': org.name}
                    )
                    if find_result and find_result.get('id'):
                        operation = 'update'
                        org.id = find_result.get('id')
                except Exception:
                    pass

            # Delete: find by name to get id if not provided
            if operation == 'delete' and not org.id:
                try:
                    find_result = manager.execute(
                        operation='find',
                        module_name=self.MODULE_NAME,
                        ansible_data={'name': org.name}
                    )
                    if find_result and find_result.get('id'):
                        org.id = find_result.get('id')
                    else:
                        result.update({
                            'changed': False,
                            'failed': False,
                            self.MODULE_NAME: {'state': 'absent'},
                            'msg': f"Organization '{org.name}' does not exist (already absent)"
                        })
                        return result
                except Exception:
                    result.update({
                        'changed': False,
                        'failed': False,
                        self.MODULE_NAME: {'state': 'absent'},
                        'msg': f"Organization '{org.name}' does not exist (already absent)"
                    })
                    return result

            # Enforced: find then merge, then create or update
            if operation == 'enforced':
                read_only_fields = {'id', 'created', 'modified', 'url'}
                argspec_fields = set(argspec.get('argument_spec', {}).keys())
                try:
                    find_result = manager.execute(
                        operation='find',
                        module_name=self.MODULE_NAME,
                        ansible_data={'name': org.name}
                    )
                except ValueError:
                    find_result = None
                if find_result and find_result.get('id'):
                    merged = {}
                    for k in argspec_fields:
                        if k in auth_params:
                            continue
                        if k in validated_params:
                            merged[k] = validated_params[k]
                        elif k == 'name':
                            merged[k] = find_result.get(k) or org.name
                        else:
                            merged[k] = None
                    for ro in read_only_fields:
                        if ro in find_result:
                            merged[ro] = find_result[ro]
                    merged.setdefault('name', org.name or find_result.get('name'))
                    org_data = {k: v for k, v in merged.items() if hasattr(AnsibleOrganization, k)}
                    org_data.setdefault('name', org.name)
                    org = AnsibleOrganization(**org_data)
                    operation = 'update'
                else:
                    operation = 'create'

            ansible_data = asdict(org)
            if operation == 'update' and validated_params.get('state') == 'enforced':
                ansible_data['_platform_enforced'] = True

            # Check mode: do not perform create/update/delete
            if self._task.check_mode and operation in ('create', 'update', 'delete'):
                if operation == 'create':
                    result.update({
                        'changed': True,
                        'failed': False,
                        self.MODULE_NAME: {'name': org.name},
                    })
                elif operation == 'update':
                    result.update({
                        'changed': True,
                        'failed': False,
                        self.MODULE_NAME: {'name': org.name, 'id': getattr(org, 'id', None)},
                    })
                else:  # delete
                    result.update({
                        'changed': bool(getattr(org, 'id', None)),
                        'failed': False,
                        self.MODULE_NAME: {'state': 'absent'},
                    })
                return result

            try:
                manager_result = manager.execute(
                    operation=operation,
                    module_name=self.MODULE_NAME,
                    ansible_data=ansible_data
                )
            except ValueError as e:
                if operation == 'find' and ('not found' in str(e).lower() or 'resource with' in str(e).lower()):
                    result.update({
                        'changed': False,
                        'failed': False,
                        self.MODULE_NAME: {},
                        'exists': False,
                        'msg': f"Organization '{org.name}' does not exist"
                    })
                    return result
                raise

            # Validate output
            # Keys excluded from the resource sub-dict ('organization'):
            #
            #   _internal_keys     — injected by the manager/RPC layer; not resource data.
            #
            #   _api_readonly      — fields the API returns but does not accept as input
            #                        (created, modified, url). Including them breaks
            #                        idempotent round-trip.
            #
            #   _ansible_directives — argspec fields that are Ansible control parameters
            #                        (state, new_name). 'state' and 'new_name' are operation
            #                        parameters, not resource fields.
            #
            # 'id' is NOT in the argspec but IS included in the resource dict because it
            # is the stable numeric identifier needed by subsequent tasks.
            _internal_keys = {'_timing', 'changed'}
            _api_readonly = {'created', 'modified', 'url'}
            _ansible_directives = {'state', 'new_name'}
            _excluded = _internal_keys | _api_readonly | _ansible_directives
            argspec_fields = set(argspec.get('argument_spec', {}).keys())

            # Build a clean view: argspec fields (minus directives) + id.
            argspec_resource_fields = (argspec_fields - _ansible_directives) | {'id'}
            filtered_result = {
                k: v for k, v in manager_result.items()
                if k in argspec_resource_fields
                and k not in _internal_keys
            }
            try:
                validated_output = self._validate_data(
                    {k: v for k, v in filtered_result.items() if k in argspec_fields and k not in _ansible_directives},
                    argspec,
                    'output'
                )
                # Restore id after argspec validation (not an argspec field but needed).
                if 'id' in filtered_result:
                    validated_output['id'] = filtered_result['id']
            except Exception:
                # Output validation failed — fall back to filtered view, still strip excluded keys.
                validated_output = {
                    k: v for k, v in manager_result.items()
                    if k not in _excluded
                }
                if 'id' in manager_result:
                    validated_output['id'] = manager_result['id']

            # Top-level result: Ansible control keys + the clean resource sub-dict only.
            result.update({
                'changed': manager_result.get('changed', False),
                'failed': False,
                self.MODULE_NAME: validated_output,
            })
            if operation == 'find':
                result['exists'] = bool(validated_output.get('id'))
            elif operation == 'delete':
                result[self.MODULE_NAME]['state'] = 'absent'

        except Exception as e:
            import traceback
            self._display.vvv(f"Error in organization action plugin: {e}")
            result['failed'] = True
            result['msg'] = str(e)
            if self._display.verbosity >= 3:
                result['exception'] = traceback.format_exc()

        return result
