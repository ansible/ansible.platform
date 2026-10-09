#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.subscriptions module.

Subscriptions is a query-only resource: POST Red Hat credentials to the
controller API to retrieve available subscriptions. Client-side filters
are applied after retrieval.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for subscriptions module."""

    MODULE_NAME = "subscriptions"

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

                raise AnsibleError("Could not load DOCUMENTATION for subscriptions module")

            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, "input")
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            validated_params = validated_input.validated_parameters
            filters = validated_params.get("filters", {}) or {}

            ansible_data = {
                "username": validated_params.get("username"),
                "password": validated_params.get("password"),
                "client_id": validated_params.get("client_id"),
                "client_secret": validated_params.get("client_secret"),
                "filters": filters,
            }

            query_result = manager.execute(
                operation="resolve",
                module_name=self.MODULE_NAME,
                ansible_data=ansible_data,
            )

            all_subscriptions = query_result.get("subscriptions", [])

            filtered_subscriptions = []
            for subscription in all_subscriptions:
                add = True
                for key, filter_val in filters.items():
                    sub_val = subscription.get(key)
                    if sub_val is not None and filter_val not in sub_val:
                        add = False
                        break
                if add:
                    filtered_subscriptions.append(subscription)

            result.update(
                {
                    "changed": False,
                    "failed": False,
                    "subscriptions": filtered_subscriptions,
                }
            )

        except Exception as e:
            import traceback

            self._display.vvv("Error in subscriptions action plugin: %s" % e)
            result["failed"] = True
            result["msg"] = str(e)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result
