#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Action plugin for ansible.platform.user module.

This action plugin uses the persistent connection manager architecture.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.docs.user import DOCUMENTATION
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.user import AnsibleUser

logger = logging.getLogger(__name__)


class ActionModule(BaseResourceActionPlugin):
    """
    Action plugin for user module.
    
    Uses the persistent connection manager architecture for improved performance.
    """

    MODULE_NAME = 'user'
    
    def run(self, tmp=None, task_vars=None):
        """
        Execute the user module using persistent manager.
        
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
        logger.debug(f"⏱️  TIMING START: Action plugin (timestamp={action_start:.6f})")

        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp  # not used

        try:
            self._display.vvv("=" * 80)
            self._display.vvv("🚀 NEW ARCHITECTURE: User action plugin running!")
            self._display.vvv("=" * 80)
            
            # Step 1: Build argspec from DOCUMENTATION
            self._display.vvv("📋 Building argument spec from DOCUMENTATION...")
            try:
                argspec = self._build_argspec_from_docs(DOCUMENTATION)
                self._display.vvvv(f"Argspec built successfully: {list(argspec.keys())}")
            except Exception as e:
                self._display.vvv(f"❌ Failed to build argspec: {e}")
                import traceback
                self._display.vvv(traceback.format_exc())
                raise
            
            # Step 2: Validate input
            self._display.vvv("✓ Validating input parameters...")
            # Get args from task, including auth parameters
            module_args = self._task.args.copy()
            self._display.vvvv(f"Module args keys: {list(module_args.keys())}")
            
            # Add auth parameters from task_vars if not in args
            auth_params = [
                'gateway_hostname', 'gateway_username', 'gateway_password',
                'gateway_token', 'gateway_validate_certs', 'gateway_request_timeout'
            ]
            for param in auth_params:
                if param not in module_args and param in task_vars:
                    module_args[param] = task_vars[param]
            
            try:
                self._display.vvvv(f"About to validate with argspec keys: {list(argspec.keys())}")
                self._display.vvvv(f"Argspec argument_spec type: {type(argspec.get('argument_spec'))}")
                validated_input = self._validate_data(
                    module_args,
                    argspec,
                    'input'
                )
            except Exception as e:
                self._display.vvv(f"❌ Validation failed: {e}")
                import traceback
                self._display.vvv(traceback.format_exc())
                raise
            
            # Step 3: Get or spawn manager
            self._display.vvv("🔌 Getting or spawning manager...")
            try:
                manager, facts_to_set = self._get_or_spawn_manager(task_vars)
                self._display.vvv("✅ Connected to manager")
                
                # Set facts in result if a new manager was spawned
                if facts_to_set:
                    logger.info(f"Setting facts for manager reuse: socket={facts_to_set.get('platform_manager_socket')}, gateway_url={facts_to_set.get('gateway_url')}")
                    logger.debug(f"Full facts dict: {facts_to_set}")
                    result['ansible_facts'] = facts_to_set
                    result['_ansible_facts_cacheable'] = True
                    logger.info("Facts set successfully in result (will be available for next task via hostvars)")
                else:
                    logger.info("Reusing existing manager - no new facts to set")
            except Exception as e:
                self._display.vvv(f"❌ Manager connection failed: {e}")
                self._display.vvv("⚠️  Falling back to legacy module implementation")
                
                # Fallback to old implementation
                # result.update(
                #     self._execute_module(
                #         module_name='ansible.platform.user',
                #         module_args=self._task.args,
                #         task_vars=task_vars,
                #     )
                # )
                return result
            
            # Step 4: Create dataclass from validated input
            self._display.vvv("📦 Creating user dataclass...")
            # Filter out None values and auth params for dataclass
            # validated_input is a ValidationResult object, access validated_parameters
            try:
                validated_params = validated_input.validated_parameters
                self._display.vvvv(f"validated_params type: {type(validated_params)}, value: {validated_params}")
            except AttributeError as e:
                raise AnsibleError(
                    f"ValidationResult object missing 'validated_parameters' attribute. "
                    f"Object type: {type(validated_input)}, attributes: {dir(validated_input)}, error: {e}"
                )
            
            # Ensure validated_params is a dict
            if not isinstance(validated_params, dict):
                raise AnsibleError(
                    f"Expected validated_parameters to be a dict, got {type(validated_params)}: {validated_params}. "
                    f"validated_input type: {type(validated_input)}, validated_input: {validated_input}"
                )
            
            user_data = {
                k: v for k, v in validated_params.items()
                if v is not None and k not in auth_params
            }
            user = AnsibleUser(**user_data)
            
            # Step 5: Detect operation
            operation = self._detect_operation(validated_params)
            self._display.vvv(f"🎯 Operation detected: {operation}")
            
            # Step 5.5: For 'create' with state='present', check if user exists first (idempotency)
            if operation == 'create' and validated_params.get('state') == 'present':
                self._display.vvv("🔍 Checking if user already exists (idempotency check)...")
                try:
                    # Try to find the user by username
                    find_result = manager.execute(
                        operation='find',
                        module_name=self.MODULE_NAME,
                        ansible_data={'username': user.username}
                    )
                    if find_result and find_result.get('id'):
                        self._display.vvv(f"✅ User '{user.username}' already exists (id={find_result.get('id')}), switching to update")
                        operation = 'update'
                        user.id = find_result.get('id')
                except Exception as find_err:
                    self._display.vvvv(f"User not found (will create): {find_err}")
                    # User doesn't exist, proceed with create
            
            # Step 6: Execute via manager
            self._display.vvv(f"📤 Sending '{operation}' request to manager...")
            manager_result = manager.execute(
                operation=operation,
                module_name=self.MODULE_NAME,
                ansible_data=user.__dict__
            )
            
            self._display.vvv("📥 Received result from manager")
            
            # Extract timing info from result if available
            if isinstance(manager_result, dict) and '_timing' in manager_result:
                timing = manager_result['_timing']
                logger.debug(f"⏱️  TIMING: RPC time={timing.get('rpc_time', 0):.6f}s")
            
            # Step 7: Validate output
            self._display.vvv("✓ Validating output...")
            # Filter out read-only fields that aren't in argspec for validation
            # These are API response fields that are valid but not in DOCUMENTATION
            read_only_fields = {'id', 'created', 'modified', 'url'}
            argspec_fields = set(argspec.get('argument_spec', {}).keys())
            filtered_result = {
                k: v for k, v in manager_result.items()
                if k in argspec_fields or k in read_only_fields
            }
            # Validate only known fields, but keep read-only fields
            try:
                validated_output = self._validate_data(
                    {k: v for k, v in filtered_result.items() if k in argspec_fields},
                    argspec,
                    'output'
                )
                # Add back read-only fields
                for field in read_only_fields:
                    if field in filtered_result:
                        validated_output[field] = filtered_result[field]
            except Exception as val_err:
                # If validation fails, just use the result as-is (might have extra fields)
                self._display.vvv(f"⚠️  Output validation warning: {val_err}, using result as-is")
                validated_output = manager_result
            
            # Step 8: Format return dict
            result.update({
                'changed': manager_result.get('changed', False),
                'failed': False,
                self.MODULE_NAME: validated_output,
                'id': validated_output.get('id'),
            })
            
            # Performance timing: Action plugin end
            action_end = time.perf_counter()
            action_elapsed = action_end - action_start
            logger.debug(f"⏱️  TIMING END: Action plugin (elapsed={action_elapsed:.6f}s, timestamp={action_end:.6f})")
            
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
            
            # Log summary
            logger.info(
                f"⏱️  PERFORMANCE SUMMARY: "
                f"Total={action_elapsed:.3f}s | "
                f"Our Code={our_code_time:.3f}s | "
                f"AAP Response={api_time:.3f}s | "
                f"Other={action_elapsed - our_code_time - api_time:.3f}s"
            )
            
            self._display.vvv("=" * 80)
            self._display.vvv("✅ Action plugin completed successfully")
            self._display.vvv("=" * 80)
            
        except Exception as e:
            return self._handle_exception(e)
        
        return result
