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
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.workflow_launch import (
    WJT_LIST_ENDPOINT,
    WorkflowLaunchTransformMixin_v2,
)


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
            manager = prepared["manager"]
            resource_data = prepared["resource_data"] or prepared["validated_params"]
            launch = AnsibleWorkflowLaunch(**resource_data)

            if not launch.name:
                raise AnsibleError("name is required")

            wait = launch.wait
            interval = launch.interval
            timeout = launch.timeout
            if wait and interval <= 0:
                raise AnsibleError("Polling interval must be positive, got %s" % interval)

            launch_request = WorkflowLaunchTransformMixin_v2.from_ansible_data(launch, {"manager": manager})
            organization = launch_request.organization

            # Look up the workflow job template
            query_params = {"name": launch.name}
            if organization is not None:
                query_params["organization"] = organization

            wjt_response = manager.search_api(
                WJT_LIST_ENDPOINT,
                query_params=query_params,
                return_all=True,
            )
            wjt_results = wjt_response.get("results", [])
            if not wjt_results:
                raise AnsibleError(f"Unable to find workflow job template '{launch.name}'")
            if len(wjt_results) > 1:
                scope_hint = "specify an organization" if organization is None else "use a unique name within the organization"
                raise AnsibleError(f"Multiple workflow job templates named '{launch.name}' matched; {scope_hint} to disambiguate")
            wjt = wjt_results[0]
            wjt_id = wjt["id"]

            # Build the launch payload from the transformed API request.
            post_data = WorkflowLaunchTransformMixin_v2.to_launch_payload(launch_request)

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
            if launch.extra_vars and not (wjt.get("ask_variables_on_launch") or wjt.get("survey_enabled")):
                param_errors.append("The field extra_vars was specified but the workflow job template does not allow it to be overridden")
            if param_errors:
                raise AnsibleError("Parameters specified which cannot be passed into workflow job template launch: " + "; ".join(param_errors))

            if self._task.check_mode:
                result.update(
                    {
                        "changed": True,
                        "msg": "Workflow launch would be attempted (check mode)",
                    }
                )
                return result

            # Launch the workflow
            launch_result = manager.launch_resource(
                f"workflow_job_templates/{wjt_id}/launch",
                post_data,
                service="controller",
                retry=False,
            )

            result["changed"] = True
            workflow_job_id = launch_result.get("id")
            if workflow_job_id is None:
                raise AnsibleError("Workflow launch response did not include a workflow job ID")

            workflow_status = launch_result.get("status", "pending")

            result.update(
                {
                    "id": workflow_job_id,
                    "status": workflow_status,
                    self.MODULE_NAME: {
                        "id": workflow_job_id,
                        "status": workflow_status,
                    },
                    "job_info": {"id": workflow_job_id},
                }
            )

            if not wait:
                return result

            # Wait for the workflow job to complete
            from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import WaitTimeoutError

            try:
                # The legacy module waited indefinitely when timeout was omitted.
                # The SDK uses negative timeout values for an unbounded wait.
                wait_timeout = float(timeout) if timeout is not None else -1
                job_result = manager.wait_for_completion(
                    f"workflow_jobs/{workflow_job_id}",
                    timeout=wait_timeout,
                    interval=interval,
                    service="controller",
                )
                final_status = job_result.get("status", "")
                result["status"] = final_status
                result[self.MODULE_NAME]["status"] = final_status

                if final_status in ("failed", "error", "canceled"):
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
