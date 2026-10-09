#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.job_cancel module.

Cancels a running controller job by POSTing to the controller
jobs/{id}/cancel/ endpoint. Checks can_cancel before attempting
and respects fail_if_not_running semantics.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for job_cancel module."""

    MODULE_NAME = "job_cancel"

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}

        self._task_vars = task_vars
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        try:
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                raise AnsibleError("Could not load DOCUMENTATION for job_cancel module")

            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, "input")
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            validated_params = validated_input.validated_parameters
            job_id = validated_params["job_id"]
            fail_if_not_running = validated_params.get("fail_if_not_running", False)

            try:
                job_data = manager.search_api("/api/controller/v2/jobs/%d/" % job_id)
            except Exception:
                job_data = None
            if not job_data or not job_data.get("id"):
                result["failed"] = True
                result["msg"] = "Unable to find job with id %d" % job_id
                return result

            cancel_data = manager.search_api("/api/controller/v2/jobs/%d/cancel/" % job_id)
            if not cancel_data or not cancel_data.get("can_cancel"):
                if fail_if_not_running:
                    result["failed"] = True
                    result["msg"] = "Job is not running"
                    return result
                result.update({"changed": False, "id": job_id})
                return result

            if self._task.check_mode:
                result.update({"changed": True, "id": job_id})
                return result

            manager.execute(
                operation="create",
                module_name=self.MODULE_NAME,
                ansible_data={"job_id": job_id},
            )

            result.update({"changed": True, "id": job_id})

        except Exception as exc:
            import traceback

            self._display.vvv("Error in job_cancel action plugin: %s" % exc)
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result
