#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2025, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for workflow_launch module.

Launches a Controller workflow job template via the SDK's launch_resource()
method and optionally waits for completion via wait_for_completion().
Non-idempotent: every invocation creates a new workflow job.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from typing import Optional

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.workflow_launch import AnsibleWorkflowLaunch
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.workflow_launch import WJT_LIST_ENDPOINT


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "workflow_launch"
    MODEL_CLASS = AnsibleWorkflowLaunch

    def run(self, tmp: object = None, task_vars: Optional[dict] = None) -> dict:
        """Launch a workflow job template via the SDK.

        This overrides the standard CRUD run() because launch is a
        Shape 2 operation (non-idempotent POST), not a standard
        create/update/delete.
        """
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            manager = prepared["manager"]

            name = validated_params.get("name")
            organization = validated_params.get("organization")
            inventory = validated_params.get("inventory")
            wait = validated_params.get("wait", True)
            interval = validated_params.get("interval", 2.0)
            timeout = validated_params.get("timeout")
            limit = validated_params.get("limit")
            tags = validated_params.get("tags")
            skip_tags = validated_params.get("skip_tags")
            scm_branch = validated_params.get("scm_branch")
            extra_vars = validated_params.get("extra_vars")

            if not name:
                raise AnsibleError("name is required")

            if self._task.check_mode:
                result.update(
                    {
                        "changed": True,
                        "msg": "Workflow launch would be attempted (check mode)",
                    }
                )
                return result

            # Look up the workflow job template
            query_params = {"name": name}
            if organization is not None:
                if str(organization).strip().isdigit():
                    org_id = int(organization)
                else:
                    org_id = manager.lookup_resource_id("organizations", "name", organization)
                query_params["organization"] = org_id

            wjt_response = manager.search_api(
                WJT_LIST_ENDPOINT,
                query_params=query_params,
            )
            wjt_results = wjt_response.get("results", [])
            if not wjt_results:
                raise AnsibleError(f"Unable to find workflow job template '{name}'")
            wjt = wjt_results[0]
            wjt_id = wjt["id"]

            # Build the launch payload
            post_data = {}

            if inventory is not None:
                if str(inventory).strip().isdigit():
                    post_data["inventory"] = int(inventory)
                else:
                    post_data["inventory"] = manager.lookup_resource_id("inventories", "name", inventory, service="controller")

            if limit:
                post_data["limit"] = limit
            if tags:
                post_data["job_tags"] = ",".join(tags)
            if skip_tags:
                post_data["skip_tags"] = ",".join(skip_tags)
            if scm_branch:
                post_data["scm_branch"] = scm_branch
            if extra_vars:
                post_data["extra_vars"] = extra_vars

            # Validate prompt-on-launch settings
            prompt_checks = {
                "inventory": "ask_inventory_on_launch",
                "limit": "ask_limit_on_launch",
                "job_tags": "ask_tags_on_launch",
                "skip_tags": "ask_skip_tags_on_launch",
                "scm_branch": "ask_scm_branch_on_launch",
            }
            param_errors = []
            for field_name, prompt_flag in prompt_checks.items():
                if field_name in post_data and not wjt.get(prompt_flag):
                    param_errors.append(f"The field {field_name} was specified but the workflow job template does not allow it to be overridden")
            if extra_vars and not (wjt.get("ask_variables_on_launch") or wjt.get("survey_enabled")):
                param_errors.append("The field extra_vars was specified but the workflow job template does not allow it to be overridden")
            if param_errors:
                raise AnsibleError("Parameters specified which cannot be passed into workflow job template launch: " + "; ".join(param_errors))

            # Launch the workflow
            launch_result = manager.launch_resource(
                f"workflow_job_templates/{wjt_id}/launch",
                post_data,
                service="controller",
            )

            workflow_job_id = launch_result.get("id")
            workflow_status = launch_result.get("status", "pending")

            result.update(
                {
                    "changed": True,
                    "id": workflow_job_id,
                    "status": workflow_status,
                    self.MODULE_NAME: {
                        "id": workflow_job_id,
                        "status": workflow_status,
                    },
                }
            )

            if not wait or not workflow_job_id:
                return result

            # Wait for the workflow job to complete
            from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_client import WaitTimeoutError

            try:
                job_result = manager.wait_for_completion(
                    f"workflow_jobs/{workflow_job_id}",
                    timeout=float(timeout) if timeout is not None else None,
                    interval=interval,
                    service="controller",
                )
                final_status = job_result.get("status", "")
                result["status"] = final_status
                result[self.MODULE_NAME]["status"] = final_status

                if final_status in ("failed", "error"):
                    result["failed"] = True
                    result["msg"] = f"Workflow job {workflow_job_id} finished with status '{final_status}'"

            except WaitTimeoutError as exc:
                last = exc.last_result or {}
                result["failed"] = True
                result["msg"] = str(exc)
                result["status"] = last.get("status", "unknown")
                result[self.MODULE_NAME]["status"] = last.get("status", "unknown")

        except Exception as exc:
            import traceback as _tb

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result
