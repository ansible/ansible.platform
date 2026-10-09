#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.workflow_approval module.

Workflow approvals are non-CRUD: the plugin polls for a pending approval
node in a running workflow job, then posts to its approve or deny
sub-endpoint via manager.execute().
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import time

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for workflow_approval module."""

    MODULE_NAME = "workflow_approval"

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

                raise AnsibleError("Could not load DOCUMENTATION for workflow_approval module")

            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, "input")
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            validated_params = validated_input.validated_parameters
            workflow_job_id = validated_params.get("workflow_job_id")
            name = validated_params.get("name")
            action = validated_params.get("action", "approve")
            timeout = validated_params.get("timeout", 10)
            interval = validated_params.get("interval", 1)

            if self._task.check_mode:
                result.update(
                    {
                        "changed": True,
                        "failed": False,
                        self.MODULE_NAME: {
                            "workflow_job_id": workflow_job_id,
                            "name": name,
                            "action": action,
                        },
                    }
                )
                return result

            # Poll for the pending approval node
            approval_id = self._wait_for_approval_node(
                manager, workflow_job_id, name, timeout, interval
            )

            if approval_id is None:
                result["failed"] = True
                result["msg"] = (
                    "Timed out waiting for approval node '%s' in workflow job %s "
                    "after %s seconds" % (name, workflow_job_id, timeout)
                )
                return result

            # Map action to SDK operation:
            #   approve -> 'create' (mixin maps create to POST .../approve/)
            #   deny    -> 'delete' (mixin maps delete to POST .../deny/)
            operation = "create" if action == "approve" else "delete"

            manager.execute(
                operation=operation,
                module_name=self.MODULE_NAME,
                ansible_data={"id": approval_id},
            )

            result["changed"] = True
            result["failed"] = False
            result[self.MODULE_NAME] = {
                "workflow_job_id": workflow_job_id,
                "name": name,
                "action": action,
                "approval_id": approval_id,
            }

        except Exception as e:
            import traceback

            self._display.vvv("Error in workflow_approval action plugin: %s" % e)
            result["failed"] = True
            result["msg"] = str(e)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result

    def _wait_for_approval_node(self, manager, workflow_job_id, name, timeout, interval):
        """Poll workflow job nodes until a pending approval node with the given name appears.

        Args:
            manager: Platform manager client (DirectHTTPClient or ManagerRPCClient).
            workflow_job_id: ID of the workflow job to monitor.
            name: Name of the approval node to find.
            timeout: Maximum seconds to wait.
            interval: Seconds between polls.

        Returns:
            int: The workflow approval job ID, or None if timed out.
        """
        start_time = time.time()
        endpoint = "/api/controller/v2/workflow_jobs/%s/workflow_nodes/" % workflow_job_id

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                return None

            try:
                response = manager.search_api(
                    endpoint,
                    query_params={"job__name": name},
                )
            except Exception as e:
                self._display.vvv(
                    "Error polling workflow nodes for job %s: %s" % (workflow_job_id, e)
                )
                time.sleep(interval)
                continue

            results = response.get("results", [])
            for node in results:
                summary_job = node.get("summary_fields", {}).get("job", {})
                if summary_job.get("type") == "workflow_approval":
                    status = summary_job.get("status")
                    if status == "pending":
                        return summary_job.get("id")

            time.sleep(interval)
