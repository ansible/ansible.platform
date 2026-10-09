#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for controller_job_wait — Shape 3 (wait-only).

Polls an existing Controller job by ID until it reaches a terminal status.
No CRUD lifecycle — does not use manager.execute().
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import WaitTimeoutError

JOB_TYPE_ENDPOINTS = {
    "jobs": "/api/controller/v2/jobs",
    "project_updates": "/api/controller/v2/project_updates",
    "inventory_updates": "/api/controller/v2/inventory_updates",
    "workflow_jobs": "/api/controller/v2/workflow_jobs",
}


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "controller_job_wait"
    MODEL_CLASS = None

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}
        self._task_vars = task_vars
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        doc = self._get_documentation()
        argspec = self._build_argspec_from_docs(doc)
        if not argspec:
            result["failed"] = True
            result["msg"] = "Could not load DOCUMENTATION for controller_job_wait module"
            return result

        validated_input = self._validate_data(self._task.args.copy(), argspec, "input")
        manager, facts_to_set = self._get_or_spawn_manager(task_vars)
        self._client = manager
        if facts_to_set:
            result["ansible_facts"] = facts_to_set
            result["_ansible_facts_cacheable"] = True

        params = validated_input.validated_parameters
        job_id = params["job_id"]
        job_type = params.get("job_type", "jobs")
        timeout = params.get("timeout")
        interval = params.get("interval", 2)

        if self._task.check_mode:
            result.update({"changed": False, "id": job_id, "status": "unknown"})
            return result

        base_path = JOB_TYPE_ENDPOINTS.get(job_type)
        if not base_path:
            result["failed"] = True
            result["msg"] = "Unknown job_type: %s" % job_type
            return result

        try:
            wait_result = manager.wait_for_resource(
                base_path=base_path,
                resource_id=job_id,
                timeout=timeout,
                interval=interval,
            )
        except WaitTimeoutError as exc:
            wait_result = exc.last_result
            result.update(
                {
                    "changed": False,
                    "failed": True,
                    "msg": str(exc),
                    "id": wait_result.get("id", job_id),
                    "status": wait_result.get("status"),
                    "elapsed": wait_result.get("elapsed"),
                    "started": wait_result.get("started"),
                    "finished": wait_result.get("finished"),
                }
            )
            return result
        except ValueError:
            result.update(
                {
                    "failed": True,
                    "msg": "Unable to wait on %s %d; that ID does not exist." % (job_type.rstrip("s"), job_id),
                }
            )
            return result

        is_failed = wait_result.get("failed", False)
        status = wait_result.get("status", "unknown")

        result.update(
            {
                "changed": False,
                "failed": is_failed,
                "id": wait_result.get("id", job_id),
                "status": status,
                "elapsed": wait_result.get("elapsed"),
                "started": wait_result.get("started"),
                "finished": wait_result.get("finished"),
            }
        )
        if is_failed:
            result["msg"] = "Job %d finished with status: %s" % (job_id, status)

        return result
