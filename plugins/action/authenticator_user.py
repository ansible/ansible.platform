#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.authenticator_user module.

Moves a user from one authenticator to another via manager.execute('find')
to read the current state and manager.execute('update') for the PATCH.
FK resolution (authenticator name → id) is handled by the transform mixin.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
import time
from dataclasses import asdict

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.authenticator_user import AnsibleAuthenticatorUser

logger = logging.getLogger(__name__)


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for authenticator_user module."""

    MODULE_NAME = 'authenticator_user'

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
                raise AnsibleError("Could not load DOCUMENTATION for authenticator_user module")

            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, 'input')
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result['ansible_facts'] = facts_to_set
                result['_ansible_facts_cacheable'] = True

            validated_params = validated_input.validated_parameters
            state = validated_params.get('state', 'present')

            authenticator_user_id = validated_params.get('authenticator_user_id')
            authenticator = validated_params.get('authenticator')

            if not authenticator_user_id:
                result.update({
                    'changed': False,
                    'failed': True,
                    'msg': 'authenticator_user_id is required.',
                })
                return result

            # GET current authenticator_user by id via manager.execute('find')
            find_data = {'authenticator_user_id': str(authenticator_user_id), 'authenticator': authenticator or ''}
            # The mixin's from_ansible_data maps authenticator_user_id to API id
            # So we can pass id directly for the find
            find_data_with_id = dict(find_data)
            if str(authenticator_user_id).isdigit():
                find_data_with_id['id'] = int(authenticator_user_id)

            try:
                current = manager.execute(
                    operation='find',
                    module_name=self.MODULE_NAME,
                    ansible_data=find_data_with_id,
                )
            except Exception as e:
                result.update({
                    'changed': False,
                    'failed': True,
                    'msg': "Authenticator user '%s' not found: %s" % (authenticator_user_id, e),
                })
                return result

            # Resolve the desired authenticator to an id for comparison.
            # The find result's 'authenticator' field is a string (from from_api),
            # so we compare stringified values.
            current_auth = current.get('authenticator')

            if state == 'exists':
                # Just verify the resource exists and authenticator matches
                if authenticator is not None and str(current_auth) != str(authenticator):
                    # Need to resolve authenticator name to id for accurate comparison
                    result.update({
                        'changed': False,
                        'failed': True,
                        'msg': (
                            "Authenticator user %s exists but authenticator is %s, expected %s"
                            % (authenticator_user_id, current_auth, authenticator)
                        ),
                        self.MODULE_NAME: current,
                    })
                else:
                    result.update({
                        'changed': False,
                        'failed': False,
                        self.MODULE_NAME: current,
                        'id': current.get('id'),
                    })
                return result

            # state == 'present': update the authenticator if it differs
            # Build update data with all relevant fields
            update_data = {
                'authenticator_user_id': str(authenticator_user_id),
                'authenticator': authenticator,
            }
            for field in ('new_uid', 'keep_memberships', 'merge_with_user',
                          'merge_accounts_with_same_uid', 'remove_other_authenticators'):
                val = validated_params.get(field)
                if val is not None:
                    update_data[field] = val

            # Set id for the update path param
            if str(authenticator_user_id).isdigit():
                update_data['id'] = int(authenticator_user_id)

            auth_user = AnsibleAuthenticatorUser(**update_data)
            ansible_data = asdict(auth_user)

            # Check idempotency: if no fields would change, skip the update
            needs_update = False
            if authenticator is not None and str(current_auth) != str(authenticator):
                needs_update = True
            for field in ('new_uid', 'keep_memberships', 'merge_with_user',
                          'merge_accounts_with_same_uid', 'remove_other_authenticators'):
                val = validated_params.get(field)
                if val is not None and current.get(field) != val:
                    needs_update = True

            if not needs_update:
                result.update({
                    'changed': False,
                    'failed': False,
                    self.MODULE_NAME: current,
                    'id': current.get('id'),
                })
                return result

            if self._task.check_mode:
                result.update({
                    'changed': True,
                    'failed': False,
                    self.MODULE_NAME: current,
                    'id': current.get('id'),
                })
                return result

            manager_result = manager.execute(
                operation='update',
                module_name=self.MODULE_NAME,
                ansible_data=ansible_data,
            )

            result.update({
                'changed': manager_result.get('changed', True),
                'failed': False,
                self.MODULE_NAME: manager_result,
                'id': manager_result.get('id', current.get('id')),
            })

            result.setdefault('_timing', {})['action_plugin_time'] = time.perf_counter() - action_start

        except Exception as e:
            import traceback
            self._display.vvv("Error in authenticator_user action plugin: %s" % e)
            result['failed'] = True
            result['msg'] = str(e)
            if self._display.verbosity >= 3:
                result['exception'] = traceback.format_exc()

        return result
