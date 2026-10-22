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

from typing import Optional

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.bulk_job_launch import AnsibleBulkJobLaunch
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.bulk_job_launch import BULK_JOB_LAUNCH_ENDPOINT
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_client import WaitTimeoutError


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
            name = validated_params.get("name")
            description = validated_params.get("description")
            organization = validated_params.get("organization")
            inventory = validated_params.get("inventory")
            limit = validated_params.get("limit")
            scm_branch = validated_params.get("scm_branch")
            extra_vars = validated_params.get("extra_vars")
            job_tags = validated_params.get("job_tags")
            skip_tags = validated_params.get("skip_tags")
            wait = validated_params.get("wait", True)
            interval = validated_params.get("interval", 2.0)
            timeout = validated_params.get("timeout")

            if not jobs:
                raise AnsibleError("jobs is required and must be a non-empty list")

            if self._task.check_mode:
                result.update(
                    {
                        "changed": True,
                        "msg": "Bulk job launch would be attempted (check mode)",
                    }
                )
                return result

            # Build the launch payload
            post_data: dict = {"jobs": jobs}

            if name is not None:
                post_data["name"] = name
            if description is not None:
                post_data["description"] = description

            # Resolve organization FK (name → id)
            if organization is not None:
                if str(organization).strip().isdigit():
                    post_data["organization"] = int(organization)
                else:
                    post_data["organization"] = manager.lookup_resource_id("organizations", "name", organization)

            # Resolve inventory FK (name → id)
            if inventory is not None:
                if str(inventory).strip().isdigit():
                    post_data["inventory"] = int(inventory)
                else:
                    post_data["inventory"] = manager.lookup_resource_id("inventories", "name", inventory, service="controller")

            if limit is not None:
                post_data["limit"] = limit
            if scm_branch is not None:
                post_data["scm_branch"] = scm_branch
            if extra_vars is not None:
                post_data["extra_vars"] = extra_vars
            if job_tags is not None:
                post_data["job_tags"] = job_tags
            if skip_tags is not None:
                post_data["skip_tags"] = skip_tags

            # Launch the bulk job
            launch_result = manager.launch_resource(
                BULK_JOB_LAUNCH_ENDPOINT,
                post_data,
                service="controller",
            )

            job_id = launch_result.get("id")
            job_status = launch_result.get("status", "pending")

            result.update(
                {
                    "changed": True,
                    "id": job_id,
                    "status": job_status,
                    "job_info": launch_result,
                }
            )

            if not wait or not job_id:
                return result

            # Wait for the workflow job to complete
            try:
                job_result = manager.wait_for_completion(
                    f"workflow_jobs/{job_id}",
                    timeout=float(timeout) if timeout is not None else None,
                    interval=interval,
                    service="controller",
                )
                final_status = job_result.get("status", "")
                result["status"] = final_status
                result["job_info"] = job_result

                if final_status in ("failed", "error"):
                    result["failed"] = True
                    result["msg"] = f"Bulk job {job_id} finished with status '{final_status}'"

            except WaitTimeoutError as exc:
                last = exc.last_result or {}
                result["failed"] = True
                result["msg"] = str(exc)
                result["status"] = last.get("status", "unknown")

        except Exception as exc:
            import traceback as _tb

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result
