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

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
# Lazy import: AnsibleUser imported inside run() to avoid worker crashes
from ansible_collections.ansible.platform.plugins.plugin_utils.docs.user import DOCUMENTATION

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
        import time

        if task_vars is None:
            task_vars = dict()

        # Store task_vars for cleanup() method
        self._task_vars = task_vars

        # Performance timing: Action plugin start
        action_start = time.perf_counter()

        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp  # not used

        try:
            # Build argspec from DOCUMENTATION (includes fragments)
            argspec = self._build_argspec_from_docs(DOCUMENTATION)

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

            # Lazy import AnsibleUser to avoid module-level import crashes
            from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.user import AnsibleUser

            validated_params = validated_input.validated_parameters
            user_data = {
                k: v for k, v in validated_params.items()
                if v is not None and k not in auth_params
            }
            user = AnsibleUser(**user_data)

            # Detect operation
            operation = self._detect_operation(validated_params)

            # For 'create' with state='present', check if user exists first (idempotency)
            if operation == 'create' and validated_params.get('state') == 'present':
                try:
                    find_result = manager.execute(
                        operation='find',
                        module_name=self.MODULE_NAME,
                        ansible_data={'username': user.username}
                    )
                    if find_result and find_result.get('id'):
                        operation = 'update'
                        user.id = find_result.get('id')
                except Exception as e:
                    # User doesn't exist, proceed with create
                    pass

            # For 'delete' operations, find user first to get ID if not provided
            if operation == 'delete' and not user.id:
                try:
                    find_result = manager.execute(
                        operation='find',
                        module_name=self.MODULE_NAME,
                        ansible_data={'username': user.username}
                    )
                    if find_result and find_result.get('id'):
                        user.id = find_result.get('id')
                    else:
                        # User doesn't exist, skip delete (idempotent)
                        result.update({
                            'changed': False,
                            'failed': False,
                            self.MODULE_NAME: {},
                            'msg': f"User '{user.username}' does not exist (already absent)"
                        })
                        return result
                except Exception as e:
                    # User doesn't exist, skip delete (idempotent)
                    result.update({
                        'changed': False,
                        'failed': False,
                        self.MODULE_NAME: {},
                        'msg': f"User '{user.username}' does not exist (already absent)"
                    })
                    return result

            # Execute via manager
            manager_result = manager.execute(
                operation=operation,
                module_name=self.MODULE_NAME,
                ansible_data=user.__dict__
            )

            # Validate output
            read_only_fields = {'id', 'created', 'modified', 'url'}
            argspec_fields = set(argspec.get('argument_spec', {}).keys())
            filtered_result = {
                k: v for k, v in manager_result.items()
                if k in argspec_fields or k in read_only_fields
            }
            try:
                validated_output = self._validate_data(
                    {k: v for k, v in filtered_result.items() if k in argspec_fields},
                    argspec,
                    'output'
                )
                for field in read_only_fields:
                    if field in filtered_result:
                        validated_output[field] = filtered_result[field]
            except Exception:
                validated_output = manager_result

            # Format return dict
            result.update({
                'changed': manager_result.get('changed', False),
                'failed': False,
                self.MODULE_NAME: validated_output,
                'id': validated_output.get('id'),
            })

            # Performance timing: Action plugin end
            action_end = time.perf_counter()
            action_elapsed = action_end - action_start

            # Extract timing info from manager result if available
            timing = {}
            if isinstance(manager_result, dict) and '_timing' in manager_result:
                timing = manager_result['_timing']

            # Calculate our code time (excluding AAP response time)
            rpc_time = timing.get('rpc_time', 0)
            manager_time = timing.get('manager_processing_time', 0)
            api_time = timing.get('api_call_time', 0)

            # Our code time = RPC + Manager processing (excluding API call which is AAP's time)
            our_code_time = rpc_time + manager_time

            # Add timing to result
            result.setdefault('_timing', {})['action_plugin_time'] = action_elapsed
            result['_timing']['action_plugin_start'] = action_start
            result['_timing']['action_plugin_end'] = action_end
            result['_timing']['total_time'] = action_elapsed

            # Add component times
            result['_timing']['rpc_time'] = rpc_time
            result['_timing']['manager_processing_time'] = manager_time
            result['_timing']['api_call_time'] = api_time  # AAP response time

            # Key metric: Our code execution time (excluding AAP)
            result['_timing']['our_code_time'] = our_code_time
            result['_timing']['aap_response_time'] = api_time

            # Add HTTP and TLS metrics from manager
            result['_timing']['http_request_count'] = timing.get('http_request_count', 0)
            result['_timing']['tls_handshake_count'] = timing.get('tls_handshake_count', 0)

            self._display.vvv("Action plugin completed successfully")

        except Exception as e:
            import traceback
            self._display.vvv(f"❌ Error in action plugin: {e}")
            result['failed'] = True
            result['msg'] = str(e)

            # Include traceback in verbose mode
            if self._display.verbosity >= 3:
                result['exception'] = traceback.format_exc()

        return result
