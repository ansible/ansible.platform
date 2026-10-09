#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for controller_workflow_approval.

Waits for a workflow approval node to become pending, then approves or denies it.
This is a non-CRUD action plugin that uses search_api() for polling and
direct_request() for the approve/deny POST.

All HTTP stays in the SDK layer -- the action plugin never makes HTTP requests directly.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import time

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import (
    BaseResourceActionPlugin,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_workflow_approval import (
    AnsibleControllerWorkflowApproval,
)


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "controller_workflow_approval"
    MODEL_CLASS = AnsibleControllerWorkflowApproval

    def run(self, tmp=None, task_vars=None):
        """Wait for an approval node and approve or deny it.

        Flow:
          1. Poll /api/controller/v2/workflow_jobs/{id}/workflow_nodes/
             filtering by job__name until a pending approval node appears.
          2. Extract the related job URL from the matching node.
          3. POST to {related_job_url}/{action}/ to approve or deny.
        """
        if task_vars is None:
            task_vars = {}
        self._task_vars = task_vars
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        try:
            # ---- argument validation ----------------------------------------
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                raise AnsibleError("Could not load DOCUMENTATION for %s module" % self.MODULE_NAME)

            validated_input = self._validate_data(self._task.args.copy(), argspec, "input")
            validated_params = validated_input.validated_parameters

            # ---- connect to manager -----------------------------------------
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager
            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            workflow_job_id = validated_params["workflow_job_id"]
            name = validated_params["name"]
            action = validated_params.get("action", "approve")
            timeout = validated_params.get("timeout", 10)
            interval = validated_params.get("interval", 1.0)

            # ---- poll for the approval node ---------------------------------
            nodes_endpoint = "/api/controller/v2/workflow_jobs/%d/workflow_nodes/" % workflow_job_id

            approval_node = None
            start_time = time.time()

            while time.time() - start_time < timeout:
                try:
                    nodes_response = manager.search_api(
                        nodes_endpoint,
                        query_params={"job__name": name},
                    )
                except Exception as poll_exc:
                    self._display.vvv("controller_workflow_approval: poll error: %s" % poll_exc)
                    time.sleep(interval)
                    continue

                for node in nodes_response.get("results", []):
                    summary_job = node.get("summary_fields", {}).get("job", {})
                    job_type = summary_job.get("type", "")
                    job_status = summary_job.get("status", "")

                    if job_type == "workflow_approval" and job_status == "pending":
                        approval_node = node
                        break

                if approval_node is not None:
                    break

                time.sleep(interval)

            if approval_node is None:
                result["failed"] = True
                result["changed"] = False
                result["msg"] = "Timed out waiting for approval node '%s' in workflow job %d after %d seconds" % (name, workflow_job_id, timeout)
                return result

            # ---- resolve the approval job endpoint --------------------------
            related_job = approval_node.get("related", {}).get("job", "")
            if not related_job:
                # Fallback: build URL from summary_fields job id
                job_id = approval_node.get("summary_fields", {}).get("job", {}).get("id")
                if job_id:
                    related_job = "/api/controller/v2/workflow_approvals/%d/" % job_id
                else:
                    result["failed"] = True
                    result["changed"] = False
                    result["msg"] = "Found approval node '%s' but could not determine the approval job endpoint" % name
                    return result

            # Ensure the related_job path ends with /
            if not related_job.endswith("/"):
                related_job += "/"

            # ---- POST approve or deny ---------------------------------------
            action_url = "%s%s/" % (related_job, action)

            self._display.vvv("controller_workflow_approval: POSTing to %s" % action_url)

            manager.direct_request("POST", action_url)

            result["changed"] = True
            result["failed"] = False
            result["msg"] = "Workflow approval node '%s' has been %sd" % (name, action)

        except Exception as exc:
            import traceback as _tb

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result
