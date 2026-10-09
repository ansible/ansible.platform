#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.controller_subscriptions module.

Subscriptions is a singleton resource: manager.execute('find') posts credentials
to the Controller API and returns the list of available subscriptions.
Client-side filtering is applied in the action plugin.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import asdict

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_subscriptions import AnsibleControllerSubscriptions


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for controller_subscriptions module."""

    MODULE_NAME = "controller_subscriptions"

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = dict()

        self._task_vars = task_vars
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        try:
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                from ansible.errors import AnsibleError

                raise AnsibleError("Could not load DOCUMENTATION for controller_subscriptions module")

            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, "input")
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            validated_params = validated_input.validated_parameters

            username = validated_params.get("username")
            password = validated_params.get("password")
            client_id = validated_params.get("client_id")
            client_secret = validated_params.get("client_secret")
            filters = validated_params.get("filters") or {}

            # Build the ansible data for the manager
            ansible_data = asdict(
                AnsibleControllerSubscriptions(
                    username=username,
                    password=password,
                    client_id=client_id,
                    client_secret=client_secret,
                    filters=filters,
                )
            )

            # POST credentials to retrieve subscriptions via manager.execute('find')
            find_result = manager.execute(
                operation="find",
                module_name=self.MODULE_NAME,
                ansible_data=ansible_data,
            )

            all_subscriptions = find_result.get("subscriptions", []) or []

            # Apply client-side filters
            filtered = []
            for subscription in all_subscriptions:
                add = True
                for key, value in filters.items():
                    sub_value = subscription.get(key, None)
                    if sub_value and value not in sub_value:
                        add = False
                        break
                if add:
                    filtered.append(subscription)

            result.update(
                {
                    "changed": False,
                    "failed": False,
                    "subscriptions": filtered,
                }
            )

        except Exception as e:
            import traceback

            self._display.vvv("Error in controller_subscriptions action plugin: %s" % e)
            result["failed"] = True
            result["msg"] = str(e)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result
