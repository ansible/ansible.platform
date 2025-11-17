#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Action plugin for ansible.platform.user module.

This action plugin uses the persistent connection manager architecture.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.docs.user import DOCUMENTATION
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.user import AnsibleUser


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
        if task_vars is None:
            task_vars = dict()

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
                manager = self._get_or_spawn_manager(task_vars)
                self._display.vvv("✅ Connected to manager")
            except Exception as e:
                self._display.vvv(f"❌ Manager connection failed: {e}")
                self._display.vvv("⚠️  Falling back to legacy module implementation")
                
                # Fallback to old implementation
                result.update(
                    self._execute_module(
                        module_name='ansible.platform.user',
                        module_args=self._task.args,
                        task_vars=task_vars,
                    )
                )
                return result
            
            # Step 4: Create dataclass from validated input
            self._display.vvv("📦 Creating user dataclass...")
            # Filter out None values and auth params for dataclass
            user_data = {
                k: v for k, v in validated_input.items()
                if v is not None and k not in auth_params
            }
            user = AnsibleUser(**user_data)
            
            # Step 5: Detect operation
            operation = self._detect_operation(validated_input)
            self._display.vvv(f"🎯 Operation detected: {operation}")
            
            # Step 5.5: For 'create' with state='present', check if user exists first (idempotency)
            if operation == 'create' and validated_input.get('state') == 'present':
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
            
            self._display.vvv("=" * 80)
            self._display.vvv("✅ Action plugin completed successfully")
            self._display.vvv("=" * 80)
            
        except Exception as e:
            self._display.vvv(f"❌ Error in action plugin: {e}")
            result['failed'] = True
            result['msg'] = str(e)
            
            # Include traceback in verbose mode
            if self._display.verbosity >= 3:
                import traceback
                result['exception'] = traceback.format_exc()
        
        return result

