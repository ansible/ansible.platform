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
    CONTROLLER_JOB_ENDPOINT,
    CONTROLLER_JOB_TEMPLATE_LAUNCH_ENDPOINT,
    JobLaunchTransformMixin_v2,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import WaitTimeoutError
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext

_ACTION_ONLY_FIELDS = frozenset({"wait", "interval", "timeout"})


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "job_launch"
    MODEL_CLASS = AnsibleJobLaunch

    _WRITE_ONLY_FIELDS = _ACTION_ONLY_FIELDS
    _NO_LOG_FIELDS = frozenset({"credential_passwords"})

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp
        self._task_vars = task_vars

        doc = self._get_documentation()
        argspec = self._build_argspec_from_docs(doc) if doc else None
        if not argspec:
            raise AnsibleError("Could not load DOCUMENTATION for job_launch module")

        validated_input = self._validate_data(self._task.args.copy(), argspec, "input")
        manager, facts_to_set = self._get_or_spawn_manager(task_vars)
        self._client = manager
        if facts_to_set:
            result["ansible_facts"] = facts_to_set
            result["_ansible_facts_cacheable"] = True

        params = validated_input.validated_parameters

        wait = params.pop("wait", False)
        interval = params.pop("interval", 2.0)
        raw_timeout = params.pop("timeout", None)
        # timeout=0 means "wait indefinitely" (legacy AWX behavior);
        # the shared waiter treats negative values as no-timeout.
        if raw_timeout is not None:
            timeout = -1.0 if float(raw_timeout) == 0 else float(raw_timeout)
        else:
            timeout = None

        if self._task.check_mode:
            result.update({"changed": True, "failed": False, "msg": "Job launch skipped (check mode)"})
            return result

        try:
            model_fields = {f.name for f in dataclass_fields(AnsibleJobLaunch)}
            ansible_obj = AnsibleJobLaunch(**{k: v for k, v in params.items() if v is not None and k not in self._AUTH_PARAMS and k in model_fields})
            context = TransformContext(
                manager=manager,
                session=getattr(manager, "session", None),
                cache={},
                api_version="2",
                service="controller",
                operation="launch",
            )
            api_data = JobLaunchTransformMixin_v2.from_ansible_data(ansible_obj, context)
            payload = JobLaunchTransformMixin_v2.to_launch_payload(api_data)
            jt_id = api_data.job_template_id

            launch_result = manager.launch_resource(
                CONTROLLER_JOB_TEMPLATE_LAUNCH_ENDPOINT.format(id=jt_id),
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
        job_url = launch_result.get("url", CONTROLLER_JOB_ENDPOINT.format(id=job_id))

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
                result["msg"] = f"Job {job_id} finished with status: {final_status}"
        except WaitTimeoutError as exc:
            lr = exc.last_result or {}
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
