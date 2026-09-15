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

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.job_wait import AnsibleJobWait
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_client import WaitTimeoutError


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for waiting on an existing job/update to finish."""

    MODULE_NAME = "job_wait"
    MODEL_CLASS = AnsibleJobWait

    def _build_resource(self, resource_data):
        """Filter resource_data to model fields before constructing MODEL_CLASS.

        The job_wait argspec includes control params (interval, timeout) that
        are not AnsibleJobWait fields.
        """
        model_fields = {f.name for f in dataclasses.fields(self.MODEL_CLASS)}
        return self.MODEL_CLASS(**{k: v for k, v in resource_data.items() if k in model_fields})

    def run(self, tmp=None, task_vars=None):
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            resource_data = prepared["resource_data"]
            manager = prepared["manager"]

            resource = self._build_resource(resource_data)

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
