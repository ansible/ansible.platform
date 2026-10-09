#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.job_wait module.

Polls a Controller job (or project_update, inventory_update, workflow_job)
until it reaches a finished state, then reports success or failure.

This is a non-CRUD action plugin: it overrides run() and uses
manager.search_api() directly instead of manager.execute().
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import time

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin

# Map job_type parameter to the controller API endpoint path
_JOB_TYPE_ENDPOINT_MAP = {
    "jobs": "/api/controller/v2/jobs/{id}/",
    "project_updates": "/api/controller/v2/project_updates/{id}/",
    "inventory_updates": "/api/controller/v2/inventory_updates/{id}/",
    "workflow_jobs": "/api/controller/v2/workflow_jobs/{id}/",
}

# Job statuses that indicate the job has completed
_FINISHED_STATUSES = frozenset({"successful", "failed", "error", "canceled"})


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for job_wait module."""

    MODULE_NAME = "job_wait"

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = dict()

        self._task_vars = task_vars
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        try:
            # Load and validate arguments from DOCUMENTATION
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                from ansible.errors import AnsibleError

                raise AnsibleError("Could not load DOCUMENTATION for job_wait module")

            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, "input")
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            validated_params = validated_input.validated_parameters

            job_id = validated_params.get("job_id")
            job_type = validated_params.get("job_type", "jobs")
            timeout = validated_params.get("timeout")
            interval = validated_params.get("interval", 2)

            # Validate job_type
            if job_type not in _JOB_TYPE_ENDPOINT_MAP:
                result["failed"] = True
                result["msg"] = "Invalid job_type '%s'. Must be one of: %s" % (
                    job_type,
                    ", ".join(sorted(_JOB_TYPE_ENDPOINT_MAP.keys())),
                )
                return result

            endpoint = _JOB_TYPE_ENDPOINT_MAP[job_type].format(id=job_id)

            # First, verify the job exists
            try:
                job_data = manager.search_api(endpoint)
            except Exception as e:
                error_msg = str(e)
                if "404" in error_msg or "not found" in error_msg.lower():
                    result["failed"] = True
                    result["msg"] = (
                        "Unable to wait, no %s %s found: The requested object could not be found."
                        % (job_type.rstrip("s"), job_id)
                    )
                else:
                    result["failed"] = True
                    result["msg"] = "Unable to wait for %s %s: %s" % (
                        job_type.rstrip("s"),
                        job_id,
                        error_msg,
                    )
                return result

            if not job_data or not job_data.get("id"):
                result["failed"] = True
                result["msg"] = (
                    "Unable to wait, no %s %s found: The requested object could not be found."
                    % (job_type.rstrip("s"), job_id)
                )
                return result

            # Poll until the job finishes or timeout
            start_time = time.monotonic()

            while True:
                # Check if job is finished
                status = job_data.get("status", "")
                finished = job_data.get("finished")

                if finished is not None or status in _FINISHED_STATUSES:
                    # Job is done
                    result["id"] = job_data.get("id")
                    result["status"] = status
                    result["elapsed"] = job_data.get("elapsed")
                    result["started"] = job_data.get("started")
                    result["finished"] = finished

                    if status in ("successful",):
                        result["changed"] = True
                        result["failed"] = False
                    elif status == "canceled":
                        result["failed"] = True
                        result["msg"] = "Job %s was canceled." % job_id
                    else:
                        result["failed"] = True
                        result["msg"] = "Job %s finished with status '%s'." % (
                            job_id,
                            status,
                        )
                    return result

                # Check timeout
                if timeout is not None:
                    elapsed_wait = time.monotonic() - start_time
                    if elapsed_wait >= timeout:
                        result["failed"] = True
                        result["id"] = job_data.get("id")
                        result["status"] = status
                        result["msg"] = (
                            "Monitoring of %s %s aborted due to timeout." % (job_type.rstrip("s"), job_id)
                        )
                        return result

                # Wait before polling again
                time.sleep(interval)

                # Poll for updated job data
                try:
                    job_data = manager.search_api(endpoint)
                except Exception as e:
                    result["failed"] = True
                    result["msg"] = "Failed to poll %s %s: %s" % (
                        job_type.rstrip("s"),
                        job_id,
                        str(e),
                    )
                    return result

        except Exception as e:
            import traceback

            self._display.vvv("Error in job_wait action plugin: %s" % e)
            result["failed"] = True
            result["msg"] = str(e)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result
