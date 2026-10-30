#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import fields
from typing import Optional

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.ad_hoc_command import AnsibleAdHocCommand
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.ad_hoc_command import (
    AD_HOC_COMMANDS_DETAIL_ENDPOINT,
    AdHocCommandTransformMixin_v2,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import WaitTimeoutError

_SERVICE = "controller"


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "ad_hoc_command"

    def run(self, tmp: object = None, task_vars: Optional[dict] = None) -> dict:
        """Launch an ad hoc command on Controller.

        Args:
            tmp: Deprecated parameter.
            task_vars: Task variables dictionary.

        Returns:
            dict: Result with id, status, changed, and failed keys.
        """
        prepared = self._prepare_action(tmp, task_vars)
        result = prepared["result"]
        params = prepared["validated_params"]
        manager = prepared["manager"]

        wait = params.get("wait", False)
        interval = params.get("interval", 2.0)
        timeout = params.get("timeout")
        wait_timeout = float(timeout) if timeout is not None else None
        if wait_timeout is None or wait_timeout == 0:
            wait_timeout = -1.0

        try:
            ansible_data = AnsibleAdHocCommand(**{field.name: params[field.name] for field in fields(AnsibleAdHocCommand) if field.name in params})
            transform_context = {
                "manager": manager,
                "session": getattr(manager, "session", None),
                "cache": getattr(manager, "cache", {}),
                "api_version": "2",
            }
            create_operation = AdHocCommandTransformMixin_v2.get_endpoint_operations()["create"]
            post_data = AdHocCommandTransformMixin_v2.to_payload(ansible_data, transform_context)
        except Exception as exc:
            result.update({"changed": False, "failed": True, "msg": str(exc)})
            return result

        if self._task.check_mode:
            result.update({"changed": True, "failed": False, "msg": "Ad hoc command launch skipped (check mode)"})
            return result

        try:
            launch_result = manager.launch_resource(create_operation.path, post_data, service=_SERVICE, retry=False)
        except Exception as exc:
            result.update({"changed": False, "failed": True, "msg": str(exc)})
            return result

        job_id = launch_result.get("id")
        if not job_id:
            result.update({"changed": True, "failed": True, "msg": "Launch response did not include a job ID"})
            return result
        job_status = launch_result.get("status", "unknown")

        if not job_id:
            result.update({"changed": True, "failed": True, "msg": "Launch response did not include a job ID"})
            return result

        if not wait:
            result.update({"changed": True, "failed": False, "id": job_id, "status": job_status})
            return result

        job_url = AD_HOC_COMMANDS_DETAIL_ENDPOINT.format(id=job_id)
        try:
            wait_result = manager.wait_for_completion(
                job_url,
                timeout=wait_timeout,
                interval=float(interval),
                service=_SERVICE,
            )
            final_status = wait_result.get("status", "unknown")
            failed = final_status in ("failed", "error", "canceled")

            result.update({"changed": True, "failed": failed, "id": wait_result.get("id", job_id), "status": final_status})
            if failed:
                result["msg"] = "Ad hoc command %s finished with status: %s" % (job_id, final_status)
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
                    "msg": "Failed to poll ad hoc command %s: %s" % (job_id, exc),
                    "id": job_id,
                    "status": "unknown",
                }
            )

        return result
