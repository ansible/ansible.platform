#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.authenticator_map module.
Uses the persistent connection manager architecture.
Composite find: name + authenticator_id.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
import time
from dataclasses import asdict

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.authenticator_map import AnsibleAuthenticatorMap

logger = logging.getLogger(__name__)


def _find_payload(am, manager):
    """Build find ansible_data with resolved authenticator_id.
    When name is purely numeric, treat it as id so find uses GET by id instead of list by name.
    """
    payload = asdict(am)
    if am.authenticator and not getattr(am, 'id', None):
        try:
            payload['authenticator_id'] = manager.lookup_resource_id('authenticators', 'name', am.authenticator)
        except Exception:
            pass
    if not getattr(am, 'id', None) and getattr(am, 'name', None) is not None:
        try:
            n = str(am.name).strip()
            if n.isdigit():
                payload['id'] = int(n)
        except (ValueError, TypeError):
            pass
    return payload


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = 'authenticator_map'

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
            'aap_validate_certs', 'aap_request_timeout'
        ]
        try:
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                raise AnsibleError("Could not load DOCUMENTATION for authenticator_map module")
            validated_input = self._validate_data(self._task.args.copy(), argspec, 'input')
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager
            if facts_to_set:
                result['ansible_facts'] = facts_to_set
                result['_ansible_facts_cacheable'] = True
            validated_params = validated_input.validated_parameters
            am_data = {k: v for k, v in validated_params.items() if v is not None and k not in auth_params}
            am = AnsibleAuthenticatorMap(**am_data)
            operation = self._detect_operation(validated_params)

            def find_data():
                return _find_payload(am, manager)
            # Used for idempotency detection: if we discover the resource already exists
            # while "creating", we compare desired fields against the existing payload.
            find_result = None
            if operation == 'create' and validated_params.get('state') == 'present':
                try:
                    find_result = manager.execute(
                        operation='find', module_name=self.MODULE_NAME, ansible_data=find_data()
                    )
                    if find_result and find_result.get('id'):
                        operation = 'update'
                        am.id = find_result.get('id')
                except Exception:
                    pass

            # Idempotency for "present" updates:
            # If we would switch from create->update because the resource exists,
            # we must verify whether the user actually wants any change before
            # issuing an update call (some backends report changed=true even for no-op updates).
            if (
                operation == 'update'
                and validated_params.get('state') == 'present'
                and find_result
                and validated_params.get('new_name') is None
                and validated_params.get('new_authenticator') is None
            ):
                changed = False

                # Only compare fields explicitly provided by the user (avoid treating
                # omitted options as "set to None", which would trigger spurious updates).
                explicit_fields = {
                    k: v
                    for k, v in validated_params.items()
                    if v is not None and k not in auth_params and k not in {'state', 'new_name', 'new_authenticator'}
                }

                def _authenticator_ids_match(desired, existing):
                    """
                    Return True if desired authenticator and existing authenticator refer to the same authenticator.

                    In some API/mocks, `find` returns an authenticator id, while module input is a name.
                    """
                    if desired is None or existing is None:
                        return False

                    desired_id = None
                    try:
                        desired_id = manager.lookup_resource_id('authenticators', 'name', str(desired))
                    except Exception:
                        desired_id = None

                    if desired_id is None and str(desired).strip().isdigit():
                        desired_id = int(str(desired).strip())

                    existing_id = None
                    if str(existing).strip().isdigit():
                        existing_id = int(str(existing).strip())

                    # If we couldn't resolve the desired authenticator into an ID, don't
                    # treat it as a mismatch. At this point the resource was already
                    # found (create->update transition), so we can safely assume the
                    # authenticator identity matches for idempotency purposes.
                    if desired_id is None and existing_id is not None:
                        return True

                    if desired_id is not None and existing_id is not None:
                        return desired_id == existing_id

                    # Fallback to string comparison
                    return str(desired).strip() == str(existing).strip()

                for k, v in explicit_fields.items():
                    existing = find_result.get(k)
                    if k == 'authenticator':
                        if not _authenticator_ids_match(v, existing):
                            changed = True
                            break
                        continue

                    # For dict-like fields, compare structural equality.
                    if isinstance(v, dict):
                        if (existing or {}) != v:
                            changed = True
                            break
                        continue

                    # Scalar/string-ish comparison with minimal normalization.
                    if existing is None:
                        if v is not None:
                            changed = True
                            break
                    elif str(v).strip() != str(existing).strip():
                        changed = True
                        break

                if not changed:
                    read_only_fields = {'id', 'created', 'modified', 'url'}
                    argspec_fields = set(argspec.get('argument_spec', {}).keys())
                    filtered = {k: v for k, v in find_result.items() if k in argspec_fields or k in read_only_fields}
                    try:
                        validated_output = self._validate_data(
                            {k: v for k, v in filtered.items() if k in argspec_fields},
                            argspec, 'output'
                        )
                        for f in read_only_fields:
                            if f in filtered:
                                validated_output[f] = filtered[f]
                    except Exception:
                        validated_output = find_result

                    result.update({
                        'changed': False,
                        'failed': False,
                        self.MODULE_NAME: validated_output,
                        'id': find_result.get('id'),
                        'name': find_result.get('name'),
                    })
                    return result

            if operation == 'delete' and not am.id:
                try:
                    find_result = manager.execute(
                        operation='find', module_name=self.MODULE_NAME, ansible_data=find_data()
                    )
                    if find_result and find_result.get('id'):
                        # When find used GET by id (e.g. numeric name), verify authenticator matches
                        # so "delete by wrong authenticator" does not delete the map
                        found_auth = find_result.get('authenticator')
                        requested_auth_id = None
                        if getattr(am, 'authenticator', None) is not None:
                            try:
                                requested_auth_id = manager.lookup_resource_id(
                                    'authenticators', 'name', str(am.authenticator)
                                )
                            except Exception:
                                pass
                            if requested_auth_id is None and str(am.authenticator).isdigit():
                                requested_auth_id = int(am.authenticator)
                        # Unresolvable authenticator (e.g. "NonExisting") or mismatch -> do not delete
                        if getattr(am, 'authenticator', None) is not None:
                            if requested_auth_id is None or found_auth is None or int(found_auth) != int(requested_auth_id):
                                find_result = None
                        if find_result and find_result.get('id'):
                            am.id = find_result.get('id')
                        else:
                            result.update({
                                'changed': False, 'failed': False,
                                self.MODULE_NAME: {'state': 'absent'},
                                'msg': "Authenticator map '%s' does not exist (already absent)" % am.name
                            })
                            return result
                    else:
                        result.update({
                            'changed': False, 'failed': False,
                            self.MODULE_NAME: {'state': 'absent'},
                            'msg': "Authenticator map '%s' does not exist (already absent)" % am.name
                        })
                        return result
                except Exception:
                    result.update({
                        'changed': False, 'failed': False,
                        self.MODULE_NAME: {'state': 'absent'},
                        'msg': "Authenticator map '%s' does not exist (already absent)" % am.name
                    })
                    return result
            if operation == 'enforced':
                read_only_fields = {'id', 'created', 'modified', 'url'}
                argspec_fields = set(argspec.get('argument_spec', {}).keys())
                try:
                    find_result = manager.execute(
                        operation='find', module_name=self.MODULE_NAME, ansible_data=find_data()
                    )
                except ValueError:
                    find_result = None
                if find_result and find_result.get('id'):
                    merged = {}
                    for k in argspec_fields:
                        if k in auth_params:
                            continue
                        merged[k] = validated_params.get(k) if k in validated_params else (find_result.get(k) if k == 'name' else None)
                    for ro in read_only_fields:
                        if ro in find_result:
                            merged[ro] = find_result[ro]
                    merged.setdefault('name', am.name or find_result.get('name'))
                    merged.setdefault('authenticator', am.authenticator)
                    am_data = {k: v for k, v in merged.items() if hasattr(AnsibleAuthenticatorMap, k)}
                    am = AnsibleAuthenticatorMap(**am_data)
                    operation = 'update'
                else:
                    operation = 'create'
            ansible_data = asdict(am)
            ansible_data.pop('authenticator_id', None)
            if operation == 'update' and validated_params.get('state') == 'enforced':
                ansible_data['_platform_enforced'] = True

            # Check mode: do not perform create/update/delete; return would-change result
            if self._task.check_mode and operation in ('create', 'update', 'delete'):
                if operation == 'create':
                    result.update({
                        'changed': True,
                        'failed': False,
                        self.MODULE_NAME: {'name': am.name, 'authenticator': getattr(am, 'authenticator', None)},
                        'id': None,
                        'name': am.name,
                    })
                elif operation == 'update':
                    result.update({
                        'changed': True,
                        'failed': False,
                        self.MODULE_NAME: {k: getattr(am, k, None) for k in ('name', 'authenticator', 'id') if hasattr(am, k)},
                        'id': getattr(am, 'id', None),
                        'name': getattr(am, 'name', None),
                    })
                else:  # delete
                    result.update({
                        'changed': bool(getattr(am, 'id', None)),
                        'failed': False,
                        self.MODULE_NAME: {'state': 'absent'},
                    })
                return result

            try:
                manager_result = manager.execute(
                    operation=operation, module_name=self.MODULE_NAME, ansible_data=ansible_data
                )
            except ValueError as e:
                if operation == 'find' and ('not found' in str(e).lower() or 'resource with' in str(e).lower()):
                    result.update({
                        'changed': False, 'failed': False, self.MODULE_NAME: {},
                        'exists': False, 'msg': "Authenticator map '%s' does not exist" % am.name
                    })
                    return result
                raise
            read_only_fields = {'id', 'created', 'modified', 'url'}
            argspec_fields = set(argspec.get('argument_spec', {}).keys())
            filtered_result = {k: v for k, v in manager_result.items() if k in argspec_fields or k in read_only_fields}
            try:
                validated_output = self._validate_data(
                    {k: v for k, v in filtered_result.items() if k in argspec_fields}, argspec, 'output'
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
            self._display.vvv("Error in authenticator_map action plugin: %s" % e)
            result['failed'] = True
            result['msg'] = str(e)
            if self._display.verbosity >= 3:
                result['exception'] = traceback.format_exc()
        return result
