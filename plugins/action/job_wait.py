#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.job_wait module.

Polls a controller job until it reaches a terminal state (successful,
failed, error, canceled).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for job_wait module."""

    MODULE_NAME = "job_wait"

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

                raise AnsibleError("Could not load DOCUMENTATION for job_wait module")

            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, "input")
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            validated_params = validated_input.validated_parameters

            ansible_data = {
                "job_id": validated_params.get("job_id"),
                "interval": validated_params.get("interval", 2),
                "timeout": validated_params.get("timeout"),
                "job_type": validated_params.get("job_type", "jobs"),
            }

            wait_result = manager.execute(
                operation="resolve",
                module_name=self.MODULE_NAME,
                ansible_data=ansible_data,
            )

            result.update(
                {
                    "changed": wait_result.get("changed", False),
                    "failed": wait_result.get("failed", False),
                    "id": wait_result.get("id"),
                    "status": wait_result.get("status"),
                    "elapsed": wait_result.get("elapsed"),
                    "started": wait_result.get("started"),
                    "finished": wait_result.get("finished"),
                }
            )

            if wait_result.get("failed"):
                result["msg"] = wait_result.get("msg", "Job failed")

        except Exception as e:
            import traceback

            self._display.vvv("Error in job_wait action plugin: %s" % e)
            result["failed"] = True
            result["msg"] = str(e)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result
