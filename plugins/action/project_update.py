#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.project_update import (
    CONTROLLER_PROJECT_UPDATE_ENDPOINT,
    CONTROLLER_PROJECT_UPDATES_ENDPOINT,
    CONTROLLER_PROJECTS_ENDPOINT,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_client import WaitTimeoutError

_SERVICE = "controller"


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "project_update"
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
            raise AnsibleError("Could not load DOCUMENTATION for project_update module")

        validated_input = self._validate_data(self._task.args.copy(), argspec, "input")
        manager, facts_to_set = self._get_or_spawn_manager(task_vars)
        self._client = manager
        if facts_to_set:
            result["ansible_facts"] = facts_to_set
            result["_ansible_facts_cacheable"] = True

        params = validated_input.validated_parameters

        name = params.get("name")
        organization = params.get("organization")
        wait = params.get("wait", True)
        interval = params.get("interval", 2.0)
        timeout = params.get("timeout")

        if self._task.check_mode:
            result.update({"changed": True, "failed": False, "msg": "Project update skipped (check mode)"})
            return result

        try:
            project_id = self._resolve_project(manager, name, organization)
            project_data = manager.search_api(CONTROLLER_PROJECTS_ENDPOINT + str(project_id) + "/")
            scm_revision_original = project_data.get("scm_revision", "")

            update_url = CONTROLLER_PROJECT_UPDATE_ENDPOINT.format(id=project_id)
            launch_result = manager.launch_resource(update_url, {}, service=_SERVICE)
        except Exception as exc:
            result.update({"changed": False, "failed": True, "msg": str(exc)})
            return result

        job_id = launch_result.get("id") or launch_result.get("project_update")
        job_status = launch_result.get("status", "unknown")
        job_url = launch_result.get("url", CONTROLLER_PROJECT_UPDATES_ENDPOINT.format(id=job_id))

        if not wait:
            result.update({"changed": True, "failed": False, "id": job_id, "status": job_status})
            return result

        try:
            wait_result = manager.wait_for_completion(
                job_url,
                timeout=float(timeout) if timeout else None,
                interval=float(interval),
                service=_SERVICE,
            )
            final_status = wait_result.get("status", "unknown")
            failed = final_status in ("failed", "error", "canceled")

            scm_revision_new = wait_result.get("scm_revision", "")
            changed = scm_revision_new != scm_revision_original

            result.update({"changed": changed, "failed": failed, "id": wait_result.get("id", job_id), "status": final_status})
            if failed:
                result["msg"] = "Project update %s finished with status: %s" % (job_id, final_status)
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
                    "msg": "Failed to poll project update %s: %s" % (job_id, exc),
                    "id": job_id,
                    "status": "unknown",
                }
            )

        return result

    def _resolve_project(self, manager, name, organization):
        if str(name).isdigit():
            return int(name)
        if organization:
            org_id = manager.lookup_resource_id("organizations", "name", organization)
            data = manager.search_api(
                CONTROLLER_PROJECTS_ENDPOINT,
                query_params={"name": name, "organization": org_id},
            )
            results = data.get("results", [])
            if not results:
                raise AnsibleError("Project '%s' not found in organization '%s'" % (name, organization))
            return results[0]["id"]
        return manager.lookup_resource_id("projects", "name", name, service=_SERVICE)
