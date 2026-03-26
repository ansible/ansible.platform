#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.user module.

This action plugin uses the persistent connection manager architecture.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.user import AnsibleUser

logger = logging.getLogger(__name__)


class ActionModule(BaseResourceActionPlugin):
    """
    Action plugin for user module.

    Uses the persistent connection manager architecture for improved performance.
    """

    MODULE_NAME = 'user'

    def __init__(self, *args, **kwargs):
        """Initialize action plugin."""
        super().__init__(*args, **kwargs)

    def run(self, tmp=None, task_vars=None):
        """
        Execute the user module using persistent manager or direct HTTP client.

        Args:
            tmp: Temporary directory (deprecated)
            task_vars: Task variables from Ansible

        Returns:
            Result dictionary with user data
        """
        if task_vars is None:
            task_vars = dict()

        # Store task_vars for cleanup() method
        self._task_vars = task_vars

        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp  # not used

        try:
            # Build argspec from DOCUMENTATION in sibling module (plugins/modules/user.py)
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if argspec is None:
                raise AnsibleError("Could not load DOCUMENTATION for user module")

            # Extract auth parameters separately (not part of module validation)
            # Auth params come from task_vars or task args, handled by extract_gateway_config
            auth_params = [
                'gateway_hostname', 'gateway_username', 'gateway_password',
                'gateway_token', 'gateway_validate_certs', 'gateway_request_timeout',
                'aap_hostname', 'aap_username', 'aap_password', 'aap_token',
                'aap_validate_certs', 'aap_request_timeout'
            ]

            # Validate input (module-specific params only, auth params excluded)
            module_args = self._task.args.copy()
            validated_input = self._validate_data(
                module_args,
                argspec,
                'input'
            )

            # Get or spawn manager (could be persistent or ephemeral)
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)

            # Store client reference for cleanup() method
            self._client = manager

            # Set facts in result if a new manager was spawned
            if facts_to_set:
                result['ansible_facts'] = facts_to_set
                result['_ansible_facts_cacheable'] = True

            # Create dataclass from validated input
            validated_params = validated_input.validated_parameters
            user_data = {
                k: v for k, v in validated_params.items()
                if v is not None and k not in auth_params
            }
            update_secrets = user_data.pop('update_secrets', True)

            # Handle deprecated fields — emit warnings and strip before dataclass
            deprecated_fields = {
                'authenticators': "The 'authenticators' parameter is deprecated. Use 'associated_authenticators' instead.",
                'authenticator_uid': "The 'authenticator_uid' parameter is deprecated. Use 'associated_authenticators' instead.",
            }
            for field, msg in deprecated_fields.items():
                if field in user_data and user_data[field] is not None:
                    result.setdefault('deprecations', []).append({
                        'msg': msg,
                        'version': '4.0.0',
                        'collection_name': 'ansible.platform',
                    })
                user_data.pop(field, None)

            user = AnsibleUser(**user_data)

            # Detect operation
            operation = self._detect_operation(validated_params)

            # When username is numeric, treat it as an ID (e.g. username: "{{ joe.id }}")
            username_is_id = str(user.username).isdigit()
            if username_is_id:
                user.id = int(user.username)

            # For 'create' with state='present', check if user exists first (idempotency)
            if operation == 'create' and validated_params.get('state') == 'present':
                try:
                    if username_is_id:
                        find_data = {'username': user.username, 'id': user.id}
                    else:
                        find_data = {'username': user.username}
                    find_result = manager.execute(
                        operation='find',
                        module_name=self.MODULE_NAME,
                        ansible_data=find_data
                    )
                    if find_result and find_result.get('id'):
                        operation = 'update'
                        user.id = find_result.get('id')
                        if username_is_id:
                            user.username = find_result.get('username', user.username)
                except Exception as e:
                    # User doesn't exist, proceed with create
                    pass

            # For 'delete' operations, find user first to get ID if not provided
            if operation == 'delete' and not user.id:
                try:
                    if username_is_id:
                        find_data = {'username': user.username, 'id': user.id}
                    else:
                        find_data = {'username': user.username}
                    find_result = manager.execute(
                        operation='find',
                        module_name=self.MODULE_NAME,
                        ansible_data=find_data
                    )
                    if find_result and find_result.get('id'):
                        user.id = find_result.get('id')
                        if username_is_id:
                            user.username = find_result.get('username', user.username)
                    else:
                        # User doesn't exist, skip delete (idempotent)
                        result.update({
                            'changed': False,
                            'failed': False,
                            self.MODULE_NAME: {'state': 'absent'},
                            'msg': f"User '{user.username}' does not exist (already absent)"
                        })
                        return result
                except Exception as e:
                    # User doesn't exist, skip delete (idempotent)
                    result.update({
                        'changed': False,
                        'failed': False,
                        self.MODULE_NAME: {'state': 'absent'},
                        'msg': f"User '{user.username}' does not exist (already absent)"
                    })
                    return result

            # Handle 'enforced': find then merge (task + defaults for omitted), then create or update
            if operation == 'enforced':
                read_only_fields = {'id', 'created', 'modified', 'url'}
                argspec_fields = set(argspec.get('argument_spec', {}).keys())
                try:
                    find_result = manager.execute(
                        operation='find',
                        module_name=self.MODULE_NAME,
                        ansible_data={'username': user.username}
                    )
                except ValueError:
                    find_result = None
                if find_result and find_result.get('id'):
                    # User exists: build merged state (task wins; omitted optional fields default to None so API can clear them)
                    required_fields = {'username'}  # required by AnsibleUser
                    merged = {}
                    for k in argspec_fields:
                        if k in auth_params:
                            continue
                        if k in validated_params:
                            merged[k] = validated_params[k]
                        elif k in required_fields:
                            merged[k] = find_result.get(k) or getattr(user, k, None)
                        else:
                            merged[k] = None  # omitted optional -> default None so API can clear
                    for ro in read_only_fields:
                        if ro in find_result:
                            merged[ro] = find_result[ro]
                    # Ensure required fields are never missing (argspec/validator may not include them)
                    merged.setdefault('username', user.username or find_result.get('username'))
                    user_data = {k: v for k, v in merged.items() if hasattr(AnsibleUser, k)}
                    user_data.setdefault('username', user.username)
                    user = AnsibleUser(**user_data)
                    operation = 'update'
                else:
                    # User does not exist: create with task params
                    operation = 'create'

            # Execute via manager. Only pass fields that were in the task so we don't send
            # dataclass defaults (e.g. organizations=[]) and cause false "changed" on idempotent runs.
            ansible_data = {k: getattr(user, k) for k in validated_params if hasattr(user, k)}
            ansible_data.pop('update_secrets', None)
            if getattr(user, 'id', None) is not None:
                ansible_data['id'] = user.id
            if operation == 'update' and validated_params.get('state') == 'enforced':
                ansible_data['_platform_enforced'] = True

            # When update_secrets is false and we're updating, strip write-only secret
            # fields so the API doesn't report a false change for unreadable fields.
            if not update_secrets and operation == 'update':
                ansible_data.pop('password', None)

            # Check mode: do not perform create/update/delete
            if self._task.check_mode and operation in ('create', 'update', 'delete'):
                if operation == 'create':
                    result.update({
                        'changed': True,
                        'failed': False,
                        self.MODULE_NAME: {'username': user.username},
                    })
                elif operation == 'update':
                    result.update({
                        'changed': True,
                        'failed': False,
                        self.MODULE_NAME: {'username': user.username, 'id': getattr(user, 'id', None)},
                    })
                else:  # delete
                    result.update({
                        'changed': bool(getattr(user, 'id', None)),
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
                        'msg': f"User '{user.username}' does not exist"
                    })
                    return result
                raise

            # Validate output
            # Keys excluded from the resource sub-dict ('user'):
            #
            #   _internal_keys     — injected by the manager/RPC layer; not resource data.
            #
            #   _api_readonly      — fields the API returns but does not accept as input
            #                        (created, modified, url). Including them breaks
            #                        idempotent round-trip.
            #
            #   _ansible_directives — argspec fields that are Ansible control parameters
            #                        (state). 'state' defaults to 'present' so omitting it
            #                        from the returned dict does not affect round-trip.
            #
            # 'id' is NOT in the argspec but IS included in the resource dict because it
            # is the stable numeric identifier needed by subsequent tasks.
            _internal_keys = {'_timing', 'changed'}
            _api_readonly = {'created', 'modified', 'url'}
            _ansible_directives = {'state'}
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

            self._display.vvv("Action plugin completed successfully")

        except Exception as e:
            import traceback
            self._display.vvv(f"❌ Error in action plugin: {e}")
            result['failed'] = True
            err_str = str(e)
            # Surface clearer hint for connection/network errors (e.g. Max retries exceeded, Connection refused)
            if not err_str or 'Max retries exceeded' in err_str or 'ConnectionError' in type(e).__name__:
                hint = (
                    "Gateway unreachable (connection/network or SSL). Check base_url (gateway_hostname), "
                    "that the host is reachable, and gateway_validate_certs (use false for self-signed). "
                )
                result['msg'] = hint + "Original error: " + (err_str or type(e).__name__)
            else:
                result['msg'] = err_str

            # Include traceback in verbose mode
            if self._display.verbosity >= 3:
                result['exception'] = traceback.format_exc()

        return result
