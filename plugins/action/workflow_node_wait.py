#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for workflow_node_wait module.

Two-phase wait: first polls the workflow job's node list until a node
matching the requested name appears, then polls the node's underlying
job until it reaches a terminal status.  Read-only — never creates or
modifies anything; changed is always False.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import time
from typing import Optional
from urllib.parse import urlparse

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.workflow_node_wait import AnsibleWorkflowNodeWait
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import WaitTimeoutError

FAILED_STATUSES = frozenset({"failed", "error", "canceled"})
WORKFLOW_NODES_LIST_ENDPOINT = "workflow_jobs/{workflow_job_id}/workflow_nodes/"


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "workflow_node_wait"
    MODEL_CLASS = AnsibleWorkflowNodeWait

    def run(self, tmp: object = None, task_vars: Optional[dict] = None) -> dict:
        """Wait for a workflow node to appear and its job to finish."""
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            manager = prepared["manager"]

            workflow_job_id = validated_params.get("workflow_job_id")
            name = validated_params.get("name")
            interval = validated_params.get("interval", 1.0)
            timeout = validated_params.get("timeout", 10)

            if not workflow_job_id:
                raise AnsibleError("workflow_job_id is required")
            if not name:
                raise AnsibleError("name is required")
            if interval <= 0:
                raise AnsibleError("interval must be greater than 0")

            # Phase 1: poll workflow nodes until matching node appears
            nodes_url = WORKFLOW_NODES_LIST_ENDPOINT.format(workflow_job_id=workflow_job_id)
            start = time.time()

            node_data = None
            while True:
                elapsed = time.time() - start
                if timeout is not None and timeout >= 0 and elapsed >= timeout:
                    raise AnsibleError(f"Timed out waiting for workflow node '{name}' to appear in workflow job {workflow_job_id} after {timeout}s")

                response = manager.search_api(
                    nodes_url,
                    query_params={"job__name": name},
                    service="controller",
                )

                if response.get("count", 0) > 0:
                    node_data = response["results"][0]
                    break

                time.sleep(interval)

            # Extract the node's job URL from related links
            related = node_data.get("related", {})
            job_url = related.get("job")

            if not job_url:
                result.update(
                    {
                        "changed": False,
                        "id": node_data.get("id"),
                        "status": node_data.get("summary_fields", {}).get("job", {}).get("status", "unknown"),
                        "job_data": node_data,
                    }
                )
                return result

            # Phase 2: wait for the node's underlying job to finish
            remaining_timeout = timeout
            if timeout is not None and timeout >= 0:
                remaining_timeout = max(0.0, timeout - (time.time() - start))

            # Convert full URL to resource path for wait_for_completion
            # job_url is like "/api/controller/v2/jobs/123/" — strip the prefix
            resource_path = job_url
            path_parts = urlparse(resource_path).path.strip("/").split("/")
            if len(path_parts) >= 4 and path_parts[:2] == ["api", "controller"] and path_parts[2].startswith("v"):
                resource_path = "/".join(path_parts[3:]) + "/"

            try:
                job_result = manager.wait_for_completion(
                    resource_url=resource_path,
                    timeout=float(remaining_timeout) if remaining_timeout is not None else None,
                    interval=float(interval),
                    service="controller",
                )

                status = job_result.get("status", "")
                result.update(
                    {
                        "changed": False,
                        "id": job_result.get("id"),
                        "elapsed": job_result.get("elapsed", 0.0),
                        "status": status,
                        "job_data": job_result,
                    }
                )

                if status in FAILED_STATUSES:
                    result["failed"] = True
                    result["msg"] = f"Workflow node '{name}' job finished with status: {status}"

            except WaitTimeoutError as exc:
                last = exc.last_result or {}
                result["failed"] = True
                result["msg"] = str(exc)
                result["id"] = last.get("id")
                result["status"] = last.get("status", "unknown")
                result["elapsed"] = last.get("elapsed", 0.0)

        except Exception as exc:
            import traceback as _tb

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result
