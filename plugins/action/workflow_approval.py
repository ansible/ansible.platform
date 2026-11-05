#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for workflow_approval.

Waits for a workflow approval node to become pending, then approves or denies it.
This is a non-CRUD action plugin that uses search_api() for polling and
direct_request() for the approve/deny POST.

All HTTP stays in the SDK layer -- the action plugin never makes HTTP requests directly.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import time

from ansible_collections.ansible.platform.plugins.action.base_action import (
    BaseResourceActionPlugin,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.workflow_approval import (
    AnsibleWorkflowApproval,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.workflow_approval import (
    WorkflowApprovalTransformMixin_v2,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import build_endpoint_request

_RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "workflow_approval"
    MODEL_CLASS = AnsibleWorkflowApproval

    def run(self, tmp=None, task_vars=None):
        """Wait for an approval node and approve or deny it."""
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            manager = prepared["manager"]

            workflow_job_id = validated_params["workflow_job_id"]
            name = validated_params["name"]
            action = validated_params.get("action", "approve")
            timeout = validated_params.get("timeout", 10)
            interval = validated_params.get("interval", 1.0)

            # ---- poll for the approval node ---------------------------------
            operations = WorkflowApprovalTransformMixin_v2.get_endpoint_operations()
            nodes_endpoint = build_endpoint_request(operations["workflow_nodes"], {"workflow_job_id": workflow_job_id})[0]

            approval_node = None
            start_time = time.time()
            no_timeout = timeout == 0

            while no_timeout or (time.time() - start_time < timeout):
                try:
                    nodes_response = manager.search_api(
                        nodes_endpoint,
                        query_params=WorkflowApprovalTransformMixin_v2.get_workflow_node_query_params(name),
                    )
                except Exception as poll_exc:
                    status_code = getattr(poll_exc, "status_code", None)
                    if self._is_retryable(poll_exc) or status_code == 404:
                        self._display.vvv("workflow_approval: poll error (will retry): %s" % poll_exc)
                    else:
                        raise
                    elapsed = time.time() - start_time
                    remaining = timeout - elapsed if not no_timeout else interval
                    if remaining > 0:
                        time.sleep(min(interval, remaining))
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

                elapsed = time.time() - start_time
                remaining = timeout - elapsed if not no_timeout else interval
                if remaining > 0:
                    time.sleep(min(interval, remaining))

            if approval_node is None:
                result["failed"] = True
                result["changed"] = False
                result["msg"] = "Timed out waiting for approval node '%s' in workflow job %d after %d seconds" % (name, workflow_job_id, timeout)
                return result

            # ---- resolve the approval job endpoint --------------------------
            related_job = approval_node.get("related", {}).get("job", "")
            action_operation = operations[action]
            action_payload = build_endpoint_request(action_operation, {})[1]
            if not related_job:
                job_id = approval_node.get("summary_fields", {}).get("job", {}).get("id")
                if job_id:
                    related_job = build_endpoint_request(operations["get"], {"id": job_id})[0]
                else:
                    result["failed"] = True
                    result["changed"] = False
                    result["msg"] = "Found approval node '%s' but could not determine the approval job endpoint" % name
                    return result

            if not related_job.endswith("/"):
                related_job += "/"

            # The API's related URL identifies the approval resource; the
            # operation declaration supplies the action suffix and method.
            action_suffix = action_operation.path.split("/{id}/", 1)[1]
            action_url = "%s/%s" % (related_job.rstrip("/"), action_suffix)

            if self._task.check_mode:
                action_past = "approved" if action == "approve" else "denied"
                result["changed"] = True
                result["msg"] = "Workflow approval node '%s' would be %s (check mode)" % (name, action_past)
                return result

            self._display.vvv("workflow_approval: POSTing to %s" % action_url)

            if action_payload:
                manager.direct_request(action_operation.method, action_url, data=action_payload)
            else:
                manager.direct_request(action_operation.method, action_url)

            result["changed"] = True
            result["failed"] = False
            action_past = "approved" if action == "approve" else "denied"
            result["msg"] = "Workflow approval node '%s' has been %s" % (name, action_past)

        except Exception as exc:
            import traceback as _tb

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result

    @staticmethod
    def _is_retryable(exc):
        status_code = getattr(exc, "status_code", None)
        if status_code is not None:
            return status_code in _RETRYABLE_STATUS_CODES
        retryable = getattr(exc, "retryable", None)
        if retryable is not None:
            return retryable
        exc_str = str(exc).lower()
        return "timeout" in exc_str or "connection" in exc_str
