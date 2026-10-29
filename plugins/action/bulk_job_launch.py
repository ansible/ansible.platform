#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for bulk_job_launch module.

Launches multiple jobs in a single API request via the Controller bulk
job launch endpoint and optionally waits for the resulting workflow job
to complete.  Non-idempotent: every invocation creates a new bulk job.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import fields
from typing import Optional

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.bulk_job_launch import AnsibleBulkJobLaunch
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import WaitTimeoutError


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "bulk_job_launch"
    MODEL_CLASS = AnsibleBulkJobLaunch

    def run(self, tmp: object = None, task_vars: Optional[dict] = None) -> dict:
        """Launch bulk jobs via the SDK."""
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            manager = prepared["manager"]

            jobs = validated_params.get("jobs", [])
            wait = validated_params.get("wait", True)
            interval = validated_params.get("interval", 2.0)
            timeout = validated_params.get("timeout")
            model_fields = {model_field.name for model_field in fields(self.MODEL_CLASS)}
            model_params = {key: value for key, value in validated_params.items() if key in model_fields}

            if not jobs:
                raise AnsibleError("jobs is required and must be a non-empty list")

            if timeout is not None and timeout < 0:
                raise AnsibleError("timeout must be 0 or greater")

            if wait and (interval is None or interval <= 0):
                raise AnsibleError("interval must be greater than 0")

            # The legacy launch action waited indefinitely when timeout was omitted.
            wait_timeout = float(timeout) if timeout is not None else -1.0

            if self._task.check_mode:
                # Resolve named foreign keys without submitting the launch request.
                lookup_params = {key: model_params[key] for key in ("organization", "inventory") if key in model_params}
                if lookup_params:
                    manager.execute("resolve", self.MODULE_NAME, lookup_params)
                result.update(
                    {
                        "changed": True,
                        "msg": "Bulk job launch would be attempted (check mode)",
                    }
                )
                return result

            # The create operation applies the API transform and posts the launch payload.
            launch_result = manager.execute("create", self.MODULE_NAME, model_params)

            job_id = launch_result.get("id")
            if not job_id:
                result.update({"changed": True, "failed": True, "msg": "Launch response did not include a workflow job ID"})
                return result
            job_status = launch_result.get("status") or "pending"

            result.update(
                {
                    "changed": True,
                    "id": job_id,
                    "status": job_status,
                    "job_info": launch_result.get("job_info") or {},
                }
            )

            if not wait:
                return result

            # Wait for the workflow job to complete
            try:
                job_result = manager.wait_for_completion(
                    f"workflow_jobs/{job_id}",
                    timeout=wait_timeout,
                    interval=interval,
                    service="controller",
                )
                final_status = job_result.get("status", "")
                result["status"] = final_status
                result["job_info"] = job_result

                if job_result.get("failed") or final_status in ("failed", "error", "canceled"):
                    result["failed"] = True
                    result["msg"] = f"Bulk job {job_id} finished with status '{final_status}'"

            except WaitTimeoutError as exc:
                last = exc.last_result or {}
                result["failed"] = True
                result["msg"] = str(exc)
                result["status"] = last.get("status", "unknown")
                if last:
                    result["job_info"] = last

        except Exception as exc:
            import traceback as _tb

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result
