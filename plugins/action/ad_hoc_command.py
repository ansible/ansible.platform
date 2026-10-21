#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
from typing import Optional

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.ad_hoc_command import (
    AD_HOC_COMMANDS_DETAIL_ENDPOINT,
    AD_HOC_COMMANDS_ENDPOINT,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_client import WaitTimeoutError

_SERVICE = "controller"


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "ad_hoc_command"
    MODEL_CLASS = None

    def run(self, tmp: object = None, task_vars: Optional[dict] = None) -> dict:
        """Launch an ad hoc command on Controller.

        Args:
            tmp: Deprecated parameter.
            task_vars: Task variables dictionary.

        Returns:
            dict: Result with id, status, changed, and failed keys.
        """
        if task_vars is None:
            task_vars = {}
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp
        self._task_vars = task_vars

        doc = self._get_documentation()
        argspec = self._build_argspec_from_docs(doc) if doc else None
        if not argspec:
            raise AnsibleError("Could not load DOCUMENTATION for ad_hoc_command module")

        validated_input = self._validate_data(self._task.args.copy(), argspec, "input")
        manager, facts_to_set = self._get_or_spawn_manager(task_vars)
        self._client = manager
        if facts_to_set:
            result["ansible_facts"] = facts_to_set
            result["_ansible_facts_cacheable"] = True

        params = validated_input.validated_parameters

        wait = params.get("wait", False)
        interval = params.get("interval", 2.0)
        timeout = params.get("timeout")

        if self._task.check_mode:
            result.update({"changed": True, "failed": False, "msg": "Ad hoc command launch skipped (check mode)"})
            return result

        try:
            post_data = self._build_post_data(manager, params)
            launch_result = manager.launch_resource(AD_HOC_COMMANDS_ENDPOINT, post_data, service=_SERVICE)
        except Exception as exc:
            result.update({"changed": False, "failed": True, "msg": str(exc)})
            return result

        job_id = launch_result.get("id")
        job_status = launch_result.get("status", "unknown")

        if not wait:
            result.update({"changed": True, "failed": False, "id": job_id, "status": job_status})
            return result

        job_url = AD_HOC_COMMANDS_DETAIL_ENDPOINT.format(id=job_id)
        try:
            wait_result = manager.wait_for_completion(
                job_url,
                timeout=float(timeout) if timeout else None,
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

    def _build_post_data(self, manager: object, params: dict) -> dict:
        """Build the POST payload, resolving FK references and serializing extra_vars.

        Args:
            manager: Platform manager instance for FK lookups.
            params: Validated module parameters.

        Returns:
            dict: Payload suitable for the ad_hoc_commands endpoint.
        """
        post_data = {}

        post_data["inventory"] = manager.lookup_resource_id("inventories", "name", params["inventory"], service=_SERVICE)
        post_data["credential"] = manager.lookup_resource_id("credentials", "name", params["credential"], service=_SERVICE)

        if params.get("execution_environment"):
            post_data["execution_environment"] = manager.lookup_resource_id("execution_environments", "name", params["execution_environment"], service=_SERVICE)

        post_data["module_name"] = params["module_name"]

        if params.get("module_args") is not None:
            post_data["module_args"] = params["module_args"]

        for field in ("job_type", "limit", "forks", "verbosity", "become_enabled", "diff_mode"):
            if params.get(field) is not None:
                post_data[field] = params[field]

        if params.get("extra_vars") is not None:
            if isinstance(params["extra_vars"], dict):
                post_data["extra_vars"] = json.dumps(params["extra_vars"])
            else:
                post_data["extra_vars"] = str(params["extra_vars"])

        return post_data
