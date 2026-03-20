#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.token module.

Tokens are non-idempotent: each 'present' call creates a new token.
Delete uses existing_token_id or existing_token['id'].
Sets ansible_facts.aap_token with the created token data.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
import time

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin

logger = logging.getLogger(__name__)


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for token module."""

    MODULE_NAME = 'token'

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
                raise AnsibleError("Could not load DOCUMENTATION for token module")

            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, 'input')
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result['ansible_facts'] = facts_to_set
                result['_ansible_facts_cacheable'] = True

            validated_params = validated_input.validated_parameters
            state = validated_params.get('state', 'present')

            # Detect API version for correct path
            if manager.api_version is None:
                try:
                    manager.api_version = manager._detect_api_version()
                except Exception:
                    manager.api_version = '1'

            tokens_path = '/api/gateway/v%s/tokens/' % manager.api_version

            if state == 'absent':
                # Delete token by id (from existing_token or existing_token_id)
                token_id = None
                existing_token = validated_params.get('existing_token')
                existing_token_id = validated_params.get('existing_token_id')

                if existing_token_id is not None:
                    token_id = int(existing_token_id)
                elif existing_token and isinstance(existing_token, dict):
                    token_id = existing_token.get('id')

                if token_id is None:
                    result.update({
                        'changed': False,
                        'failed': False,
                        self.MODULE_NAME: {'state': 'absent'},
                        'msg': 'No token id provided for deletion.',
                    })
                    return result

                if self._task.check_mode:
                    result.update({
                        'changed': True,
                        'failed': False,
                        self.MODULE_NAME: {'state': 'absent', 'id': token_id},
                    })
                    return result

                delete_path = '%s%s/' % (tokens_path, token_id)
                try:
                    manager.direct_request('DELETE', delete_path)
                    result.update({
                        'changed': True,
                        'failed': False,
                        self.MODULE_NAME: {'state': 'absent', 'id': token_id},
                    })
                except Exception as e:
                    if '404' in str(e) or 'not found' in str(e).lower():
                        result.update({
                            'changed': False,
                            'failed': False,
                            self.MODULE_NAME: {'state': 'absent'},
                            'msg': 'Token %s already absent.' % token_id,
                        })
                    else:
                        raise

            else:
                # state == 'present': create a new token (always creates, never idempotent)
                payload = {}
                description = validated_params.get('description')
                scope = validated_params.get('scope')
                if description is not None:
                    payload['description'] = description
                if scope is not None:
                    payload['scope'] = scope

                # Resolve application FK if provided
                application = validated_params.get('application')
                if application is not None:
                    if str(application).isdigit():
                        payload['application'] = int(application)
                    else:
                        try:
                            app_id = manager.lookup_resource_id('applications', 'name', str(application))
                            if app_id:
                                payload['application'] = app_id
                        except Exception:
                            payload['application'] = application

                if self._task.check_mode:
                    result.update({
                        'changed': True,
                        'failed': False,
                        self.MODULE_NAME: {'state': 'present'},
                        'ansible_facts': {'aap_token': {}},
                        '_ansible_facts_cacheable': False,
                    })
                    return result

                token_data = manager.direct_request('POST', tokens_path, data=payload)

                # Set ansible fact so the token value is accessible in the play
                aap_token = {
                    'id': token_data.get('id'),
                    'token': token_data.get('token'),
                    'description': token_data.get('description'),
                    'scope': token_data.get('scope'),
                    'created': token_data.get('created'),
                    'modified': token_data.get('modified'),
                    'url': token_data.get('url'),
                }

                result.update({
                    'changed': True,
                    'failed': False,
                    self.MODULE_NAME: token_data,
                    'id': token_data.get('id'),
                    'ansible_facts': {'aap_token': aap_token},
                    '_ansible_facts_cacheable': False,
                })

            result.setdefault('_timing', {})['action_plugin_time'] = time.perf_counter() - action_start

        except Exception as e:
            import traceback
            self._display.vvv("Error in token action plugin: %s" % e)
            result['failed'] = True
            result['msg'] = str(e)
            if self._display.verbosity >= 3:
                result['exception'] = traceback.format_exc()

        return result
