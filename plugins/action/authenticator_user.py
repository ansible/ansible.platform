#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.authenticator_user module.

Moves a user from one authenticator to another via PATCH on the authenticator_user
resource identified by authenticator_user_id.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
import time

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin

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

            # Detect API version
            if manager.api_version is None:
                try:
                    manager.api_version = manager._detect_api_version()
                except Exception:
                    manager.api_version = '1'

            base_path = '/api/gateway/v%s/authenticator_users/' % manager.api_version
            resource_path = '%s%s/' % (base_path, authenticator_user_id)

            # GET current authenticator_user
            try:
                current = manager.direct_request('GET', resource_path)
            except Exception as e:
                result.update({
                    'changed': False,
                    'failed': True,
                    'msg': "Authenticator user '%s' not found: %s" % (authenticator_user_id, e),
                })
                return result

            # Resolve authenticator FK (name -> id)
            authenticator_id = None
            if authenticator is not None:
                if str(authenticator).isdigit():
                    authenticator_id = int(authenticator)
                else:
                    try:
                        authenticator_id = manager.lookup_resource_id('authenticators', 'name', str(authenticator))
                    except Exception:
                        authenticator_id = None

            if state == 'exists':
                # Just verify the resource exists and authenticator matches
                current_auth = current.get('authenticator')
                if authenticator_id is not None and current_auth != authenticator_id:
                    result.update({
                        'changed': False,
                        'failed': True,
                        'msg': (
                            "Authenticator user %s exists but authenticator is %s, expected %s"
                            % (authenticator_user_id, current_auth, authenticator_id)
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
            current_auth = current.get('authenticator')
            if authenticator_id is not None and current_auth == authenticator_id:
                # Already correct authenticator
                result.update({
                    'changed': False,
                    'failed': False,
                    self.MODULE_NAME: current,
                    'id': current.get('id'),
                })
                return result

            # Build PATCH payload
            payload = {}
            if authenticator_id is not None:
                payload['authenticator'] = authenticator_id

            for field in ('new_uid', 'keep_memberships', 'merge_with_user',
                          'merge_accounts_with_same_uid', 'remove_other_authenticators'):
                val = validated_params.get(field)
                if val is not None:
                    payload[field] = val

            if not payload:
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

            updated = manager.direct_request('PATCH', resource_path, data=payload)

            result.update({
                'changed': True,
                'failed': False,
                self.MODULE_NAME: updated,
                'id': updated.get('id', current.get('id')),
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
