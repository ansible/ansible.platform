#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import fields as dataclass_fields

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.job_launch import AnsibleJobLaunch
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.job_launch import (
    JobLaunchTransformMixin_v2,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import WaitTimeoutError
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import build_endpoint_request

_ACTION_ONLY_FIELDS = frozenset({"wait", "interval", "timeout"})


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "job_launch"
    MODEL_CLASS = AnsibleJobLaunch

    _WRITE_ONLY_FIELDS = _ACTION_ONLY_FIELDS
    _NO_LOG_FIELDS = frozenset({"credential_passwords"})

    @staticmethod
    def _set_job_timing(result, job_data):
        """Populate Controller timing fields with Ansible's boolean finished flag."""
        for field in ("elapsed", "started"):
            result[field] = job_data.get(field)
        result["finished"] = bool(job_data.get("finished"))
        result["finished_at"] = job_data.get("finished")

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp
        self._task_vars = task_vars

        params = self._validate_action_input().validated_params
        manager, facts_to_set = self._get_or_spawn_manager(task_vars)
        self._client = manager
        if facts_to_set:
            result["ansible_facts"] = facts_to_set
            result["_ansible_facts_cacheable"] = True

        wait = params.pop("wait", False)
        interval = params.pop("interval", 2.0)
        raw_timeout = params.pop("timeout", None)
        # Legacy AWX treats an omitted timeout or timeout=0 as no limit.
        # The shared waiter treats negative values as no-timeout and zero as
        # an immediate timeout.
        timeout = -1.0 if raw_timeout is None or float(raw_timeout) == 0 else float(raw_timeout)

        try:
            model_fields = {f.name for f in dataclass_fields(AnsibleJobLaunch)}
            ansible_obj = AnsibleJobLaunch(**{k: v for k, v in params.items() if v is not None and k not in self._AUTH_PARAMS and k in model_fields})
            context = {"manager": manager, "operation": "launch"}
            api_data = JobLaunchTransformMixin_v2.from_ansible_data(ansible_obj, context)
            prompt_errors = self._validate_launch_prompts(manager, api_data.job_template_id, params)
            if prompt_errors:
                result.update(
                    {
                        "changed": False,
                        "failed": True,
                        "msg": "Parameters specified which can not be passed into job template, see errors for details",
                        "errors": prompt_errors,
                    }
                )
                return result
            if self._task.check_mode:
                result.update({"changed": True, "failed": False, "msg": "Job launch skipped (check mode)"})
                return result

            launch_operation = JobLaunchTransformMixin_v2.get_endpoint_operations()["launch"]
            if launch_operation.method != "POST":
                raise AnsibleError("Job launch endpoint operation must use POST")
            launch_path, payload = build_endpoint_request(launch_operation, api_data, path_values={"id": api_data.job_template_id})

            launch_result = manager.launch_resource(
                launch_path,
                payload,
                service="controller",
                retry=False,
            )
        except Exception as exc:
            result.update({"changed": False, "failed": True, "msg": str(exc)})
            return result

        job_id = launch_result.get("id") or launch_result.get("job")
        if not job_id:
            result.update({"changed": True, "failed": True, "msg": "Launch response did not include a job ID"})
            return result
        job_status = launch_result.get("status", "unknown")
        job_detail_operation = JobLaunchTransformMixin_v2.get_endpoint_operations()["get"]
        job_url = launch_result.get("url", job_detail_operation.path.format(id=job_id))

        ignored_fields = launch_result.get("ignored_fields", {})
        if ignored_fields:
            result["warnings"] = [f"Launch ignored fields: {ignored_fields}"]

        if not wait:
            result.update({"changed": True, "failed": False, "id": job_id, "status": job_status})
            return result

        try:
            wait_result = manager.wait_for_completion(
                job_url,
                timeout=timeout,
                interval=float(interval),
                service="controller",
            )
            final_status = wait_result.get("status", "unknown")
            self._set_job_timing(result, wait_result)
            failed = final_status in ("failed", "error", "canceled")
            result.update(
                {
                    "changed": True,
                    "failed": failed,
                    "id": wait_result.get("id", job_id),
                    "status": final_status,
                }
            )
            if failed:
                result["job_data"] = wait_result
                result["msg"] = f"Job {job_id} finished with status: {final_status}"
        except WaitTimeoutError as exc:
            lr = exc.last_result or {}
            self._set_job_timing(result, lr)
            result.update(
                {
                    "changed": True,
                    "failed": True,
                    "msg": str(exc),
                    "id": lr.get("id", job_id),
                    "status": lr.get("status", "unknown"),
                }
            )
        except Exception as exc:
            result.update(
                {
                    "changed": True,
                    "failed": True,
                    "msg": "Failed to poll job %s: %s" % (job_id, exc),
                    "id": job_id,
                    "status": "unknown",
                }
            )

        return result

    @staticmethod
    def _validate_launch_prompts(manager, job_template_id, params):
        """Reject launch overrides that the selected job template does not prompt for."""
        checks = {
            "scm_branch": "ask_scm_branch_on_launch",
            "diff_mode": "ask_diff_mode_on_launch",
            "limit": "ask_limit_on_launch",
            "tags": "ask_tags_on_launch",
            "skip_tags": "ask_skip_tags_on_launch",
            "job_type": "ask_job_type_on_launch",
            "verbosity": "ask_verbosity_on_launch",
            "inventory": "ask_inventory_on_launch",
            "credentials": "ask_credential_on_launch",
            "execution_environment": "ask_execution_environment_on_launch",
            "forks": "ask_forks_on_launch",
            "instance_groups": "ask_instance_groups_on_launch",
            "labels": "ask_labels_on_launch",
            "job_slice_count": "ask_job_slice_count_on_launch",
            "job_timeout": "ask_timeout_on_launch",
        }
        param_errors = []
        requested_fields = [field for field in checks if params.get(field) is not None]
        check_extra_vars = params.get("extra_vars") is not None
        if not requested_fields and not check_extra_vars:
            return param_errors

        detail_operation = JobLaunchTransformMixin_v2.get_endpoint_operations()["get_job_template"]
        template_path = detail_operation.path.format(id=job_template_id)
        template = manager.search_api(template_path, service="controller")
        for field in requested_fields:
            if not template.get(checks[field]):
                param_errors.append("The field %s was specified but the job template does not allow for it to be overridden" % field)

        if check_extra_vars and not (template.get("ask_variables_on_launch") or template.get("survey_enabled")):
            param_errors.append("The field extra_vars was specified but the job template does not allow for it to be overridden")

        return param_errors
