#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.settings module.

Settings is a singleton resource: GET /settings/all/ to read, PATCH to update.
Uses direct_request() for raw HTTP access to the singleton endpoint.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
import time

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin

logger = logging.getLogger(__name__)


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for settings module."""

    MODULE_NAME = 'settings'

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
                raise AnsibleError("Could not load DOCUMENTATION for settings module")

            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, 'input')
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result['ansible_facts'] = facts_to_set
                result['_ansible_facts_cacheable'] = True

            validated_params = validated_input.validated_parameters
            desired_settings = validated_params.get('settings', {}) or {}

            # Detect API version for correct path
            if manager.api_version is None:
                try:
                    manager.api_version = manager._detect_api_version()
                except Exception:
                    manager.api_version = '1'

            settings_path = '/api/gateway/v%s/settings/all/' % manager.api_version

            # GET current settings
            current_settings = manager.direct_request('GET', settings_path)

            # Idempotency: check which desired keys differ from current
            to_update = {
                k: v for k, v in desired_settings.items()
                if str(current_settings.get(k)) != str(v)
            }

            if not to_update:
                # Nothing to change
                result.update({
                    'changed': False,
                    'failed': False,
                    self.MODULE_NAME: {
                        'settings': current_settings,
                        'old_values': {},
                        'new_values': {},
                        'changed': False,
                    },
                })
                return result

            if self._task.check_mode:
                result.update({
                    'changed': True,
                    'failed': False,
                    self.MODULE_NAME: {
                        'settings': current_settings,
                        'old_values': {k: current_settings.get(k) for k in to_update},
                        'new_values': to_update,
                        'changed': True,
                    },
                })
                return result

            # PATCH only the changed keys
            updated_settings = manager.direct_request('PATCH', settings_path, data=to_update)

            result.update({
                'changed': True,
                'failed': False,
                self.MODULE_NAME: {
                    'settings': updated_settings,
                    'old_values': {k: current_settings.get(k) for k in to_update},
                    'new_values': to_update,
                    'changed': True,
                },
            })

            result.setdefault('_timing', {})['action_plugin_time'] = time.perf_counter() - action_start

        except Exception as e:
            import traceback
            self._display.vvv("Error in settings action plugin: %s" % e)
            result['failed'] = True
            result['msg'] = str(e)
            if self._display.verbosity >= 3:
                result['exception'] = traceback.format_exc()

        return result
