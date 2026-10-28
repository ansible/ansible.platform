#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for waiting for a Controller job to finish."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import time

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.job_wait import JOB_TYPE_RESOURCE_MAP

_FINISHED_STATUSES = frozenset({"successful", "failed", "error", "canceled"})
_JOB_TYPE_LABELS = {
    "jobs": "job",
    "project_updates": "project update",
    "inventory_updates": "inventory update",
    "workflow_jobs": "workflow job",
}


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for job_wait module."""

    MODULE_NAME = "job_wait"

    @staticmethod
    def _is_not_found_error(exc):
        """Return whether the SDK error represents an HTTP 404."""
        status_code = getattr(exc, "status_code", None)
        if status_code is None:
            status_code = (getattr(exc, "details", None) or {}).get("status_code")
        if status_code is None:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
        return status_code == 404

    def _find_job(self, manager, job_id, job_type):
        """Fetch the current job through the SDK's standard find operation."""
        return manager.execute(
            operation="find",
            module_name=self.MODULE_NAME,
            ansible_data={"job_id": job_id, "job_type": job_type},
        )

    def _poll_job(self, manager, job_id, job_type, job_data, start_time, timeout, interval):
        """Poll until the job finishes or the positive timeout expires."""
        while True:
            status = job_data.get("status", "")
            if job_data.get("finished") or status in _FINISHED_STATUSES:
                return job_data, False

            # AWX treats timeout=0 as unlimited; an omitted timeout does too.
            timed = timeout is not None and timeout > 0
            remaining = timeout - (time.monotonic() - start_time) if timed else None
            if remaining is not None and remaining <= 0:
                return job_data, True

            time.sleep(min(interval, remaining) if remaining is not None else interval)

            # Do not issue another request after the deadline.
            if timed and time.monotonic() - start_time >= timeout:
                return job_data, True

            try:
                job_data = self._find_job(manager, job_id, job_type)
            except Exception as exc:
                label = _JOB_TYPE_LABELS[job_type]
                raise AnsibleError("Failed to poll %s %s: %s" % (label, job_id, exc)) from exc

    @staticmethod
    def _set_job_result(result, job_data):
        """Populate the job result fields using Ansible's task-result naming."""
        for field in ("id", "status", "elapsed", "started"):
            result[field] = job_data.get(field)
        # ansible-core reserves the top-level ``finished`` task-result key as a
        # boolean, so expose the Controller timestamp under ``finished_at``.
        result["finished"] = bool(job_data.get("finished"))
        result["finished_at"] = job_data.get("finished")

    def run(self, tmp=None, task_vars=None):
        """Wait for the requested job and return its final Controller fields."""
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            manager = prepared["manager"]

            job_id = validated_params["job_id"]
            job_type = validated_params.get("job_type", "jobs")
            timeout = validated_params.get("timeout")
            interval = validated_params.get("interval")
            if interval is None:
                interval = 2.0

            if job_type not in JOB_TYPE_RESOURCE_MAP:
                raise AnsibleError("Invalid job_type '%s'. Must be one of: %s" % (job_type, ", ".join(sorted(JOB_TYPE_RESOURCE_MAP))))
            if interval <= 0:
                raise AnsibleError("interval must be greater than 0")
            if timeout is not None and timeout < 0:
                raise AnsibleError("timeout must be 0 or greater")

            label = _JOB_TYPE_LABELS[job_type]
            start_time = time.monotonic()
            try:
                job_data = self._find_job(manager, job_id, job_type)
            except Exception as exc:
                if self._is_not_found_error(exc):
                    result["failed"] = True
                    result["changed"] = False
                    result["msg"] = "Unable to wait, no %s %s found: The requested object could not be found." % (label, job_id)
                    return result
                raise AnsibleError("Unable to wait for %s %s: %s" % (label, job_id, exc)) from exc

            if not job_data or not job_data.get("id"):
                result["failed"] = True
                result["changed"] = False
                result["msg"] = "Unable to wait, no %s %s found: The requested object could not be found." % (label, job_id)
                return result

            job_data, timed_out = self._poll_job(manager, job_id, job_type, job_data, start_time, timeout, interval)
            self._set_job_result(result, job_data)

            status = job_data.get("status", "")
            result["changed"] = False
            if timed_out:
                result["failed"] = True
                result["msg"] = "Monitoring of %s %s aborted due to timeout." % (label, job_id)
            elif status == "successful":
                result["failed"] = False
            elif status == "canceled":
                result["failed"] = True
                result["msg"] = "Job %s was canceled." % job_id
            else:
                result["failed"] = True
                result["msg"] = "Job %s finished with status '%s'." % (job_id, status)

        except Exception as exc:
            import traceback as _tb

            self._display.vvv("Error in job_wait action plugin: %s" % exc)
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result
