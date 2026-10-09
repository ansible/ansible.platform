#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_client import WaitTimeoutError


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "job_launch"
    MODEL_CLASS = None

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

        name = params.get("name")
        organization = params.get("organization")
        wait = params.get("wait", False)
        interval = params.get("interval", 2.0)
        timeout = params.get("timeout")

        if self._task.check_mode:
            result.update({"changed": True, "failed": False, "msg": "Job launch skipped (check mode)"})
            return result

        jt_id = self._resolve_job_template(manager, name, organization)

        payload = self._build_launch_payload(manager, params)

        try:
            launch_result = manager.launch_resource(
                f"/api/controller/v2/job_templates/{jt_id}/launch/",
                payload,
                service="controller",
            )
        except Exception as exc:
            result.update({"changed": False, "failed": True, "msg": str(exc)})
            return result

        job_id = launch_result.get("id") or launch_result.get("job")
        job_status = launch_result.get("status", "unknown")
        job_url = launch_result.get("url", f"/api/controller/v2/jobs/{job_id}/")

        if not wait:
            result.update({"changed": True, "failed": False, "id": job_id, "status": job_status})
            return result

        try:
            wait_result = manager.wait_for_completion(
                job_url,
                timeout=float(timeout) if timeout else None,
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

        return result

    def _resolve_job_template(self, manager, name, organization):
        if str(name).isdigit():
            return int(name)
        if organization:
            org_id = manager.lookup_resource_id("organizations", "name", organization)
            data = manager.search_api(
                "/api/controller/v2/job_templates/",
                query_params={"name": name, "organization": org_id},
            )
            results = data.get("results", [])
            if not results:
                raise AnsibleError(f"Job template '{name}' not found in organization '{organization}'")
            return results[0]["id"]
        return manager.lookup_resource_id("job_templates", "name", name, service="controller")

    def _build_launch_payload(self, manager, params):
        payload = {}

        for field in ("job_type", "limit", "scm_branch", "verbosity", "diff_mode", "forks", "job_slice_count"):
            val = params.get(field)
            if val is not None:
                payload[field] = val

        extra_vars = params.get("extra_vars")
        if extra_vars is not None:
            payload["extra_vars"] = json.dumps(extra_vars) if isinstance(extra_vars, dict) else extra_vars

        tags = params.get("tags")
        if tags is not None:
            payload["job_tags"] = ",".join(tags)

        skip_tags = params.get("skip_tags")
        if skip_tags is not None:
            payload["skip_tags"] = ",".join(skip_tags)

        job_timeout = params.get("job_timeout")
        if job_timeout is not None:
            payload["timeout"] = job_timeout

        credential_passwords = params.get("credential_passwords")
        if credential_passwords is not None:
            payload["credential_passwords"] = credential_passwords

        inventory = params.get("inventory")
        if inventory is not None:
            if str(inventory).isdigit():
                payload["inventory"] = int(inventory)
            else:
                payload["inventory"] = manager.lookup_resource_id("inventories", "name", inventory, service="controller")

        execution_environment = params.get("execution_environment")
        if execution_environment is not None:
            if str(execution_environment).isdigit():
                payload["execution_environment"] = int(execution_environment)
            else:
                payload["execution_environment"] = manager.lookup_resource_id("execution_environments", "name", execution_environment, service="controller")

        credentials = params.get("credentials")
        if credentials is not None:
            payload["credentials"] = [
                int(c) if str(c).isdigit() else manager.lookup_resource_id("credentials", "name", c, service="controller") for c in credentials
            ]

        instance_groups = params.get("instance_groups")
        if instance_groups is not None:
            payload["instance_groups"] = [
                int(ig) if str(ig).isdigit() else manager.lookup_resource_id("instance_groups", "name", ig, service="controller") for ig in instance_groups
            ]

        labels = params.get("labels")
        if labels is not None:
            payload["labels"] = [int(lb) if str(lb).isdigit() else manager.lookup_resource_id("labels", "name", lb, service="controller") for lb in labels]

        return payload
