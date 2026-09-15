#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.job_wait module.

Waits for an already-launched Controller job/update/workflow job to finish.
This module never creates or changes anything — it only reads and polls.
Waiting for completion is handled entirely by PlatformService/DirectHTTPClient
(see platform_manager.py and direct_client.py) so non-Ansible SDK consumers
get the same wait semantics — this action plugin only forwards the result.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import dataclasses

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.job_wait import AnsibleJobWait
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_client import WaitTimeoutError


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for waiting on an existing job/update to finish."""

    MODULE_NAME = "job_wait"
    MODEL_CLASS = AnsibleJobWait

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}
        self._task_vars = task_vars
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        try:
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                raise AnsibleError("Could not load DOCUMENTATION for job_wait module")

            validated_input = self._validate_data(self._task.args.copy(), argspec, "input")

            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager
            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            validated_params = validated_input.validated_parameters

            resource_data = {k: v for k, v in validated_params.items() if v is not None and k not in self._AUTH_PARAMS}
            model_fields = {f.name for f in dataclasses.fields(self.MODEL_CLASS)}
            resource = self.MODEL_CLASS(**{k: v for k, v in resource_data.items() if k in model_fields})

            ansible_data = dataclasses.asdict(resource)
            # This module always waits — that is its entire purpose — unlike
            # launch modules (inventory_source_update, job_launch) where wait
            # is a user choice.
            ansible_data["wait"] = True
            ansible_data["interval"] = validated_params.get("interval", 2.0)
            ansible_data["timeout"] = validated_params.get("timeout")

            wait_result = manager.execute(
                operation="create",
                module_name=self.MODULE_NAME,
                ansible_data=ansible_data,
            )

            status = wait_result.get("status")
            result.update(
                {
                    "changed": False,
                    "id": wait_result.get("id"),
                    "status": status,
                    "started": wait_result.get("started"),
                    "finished": wait_result.get("finished"),
                    "elapsed": wait_result.get("elapsed"),
                }
            )

            if status in ("error", "failed", "canceled"):
                result["failed"] = True
                result["msg"] = "Job %s finished with status: %s" % (wait_result.get("id"), status)

        except WaitTimeoutError as exc:
            last = exc.last_result
            result.update(
                {
                    "changed": False,
                    "failed": True,
                    "id": last.get("id"),
                    "status": last.get("status", "unknown"),
                    "msg": str(exc),
                }
            )

        except Exception as exc:
            import traceback as _tb

            self._display.vvv("Error in job_wait action plugin: %s" % exc)
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result
