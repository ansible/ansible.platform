#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.project_update import (
    CONTROLLER_PROJECTS_ENDPOINT,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import WaitTimeoutError

_SERVICE = "controller"


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "project_update"

    def run(self, tmp=None, task_vars=None):
        prepared = self._prepare_action(tmp, task_vars)
        result = prepared["result"]
        params = prepared["validated_params"]
        manager = prepared["manager"]

        name = params.get("name")
        organization = params.get("organization")
        wait = params.get("wait", True)
        interval = params.get("interval", 2.0)
        timeout = params.get("timeout")

        try:
            project_id = self._resolve_project(manager, name, organization)
        except Exception as exc:
            result.update({"changed": False, "failed": True, "msg": str(exc)})
            return result

        if self._task.check_mode:
            result.update({"changed": True, "failed": False, "msg": "Project update skipped (check mode)"})
            return result

        if wait and interval <= 0:
            result.update({"changed": False, "failed": True, "msg": "Polling interval must be positive, got %s" % interval})
            return result

        try:
            project_data = manager.search_api(CONTROLLER_PROJECTS_ENDPOINT + str(project_id) + "/")
            scm_revision_original = project_data.get("scm_revision", "")

            launch_result = manager.launch_resource("projects/%d/update" % project_id, {}, service=_SERVICE)
        except Exception as exc:
            result.update({"changed": False, "failed": True, "msg": str(exc)})
            return result

        job_id = launch_result.get("id") or launch_result.get("project_update")
        if not job_id:
            result.update({"changed": True, "failed": True, "msg": "Launch response did not include a job ID"})
            return result
        job_status = launch_result.get("status", "unknown")
        job_url = launch_result.get("url") or "project_updates/%d" % job_id

        if not wait:
            result.update({"changed": True, "failed": False, "id": job_id, "status": job_status})
            return result

        try:
            wait_result = manager.wait_for_completion(
                job_url,
                timeout=float(timeout) if timeout is not None else None,
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

        query_params = {"name": name}
        scope = ""
        if organization:
            org_id = manager.lookup_resource_id("organizations", "name", organization, service=_SERVICE)
            query_params["organization"] = org_id
            scope = " in organization '%s'" % organization

        data = manager.search_api(CONTROLLER_PROJECTS_ENDPOINT, query_params=query_params, return_all=True)
        matches = [project for project in data.get("results", []) if project.get("name") == name]
        if not matches:
            raise AnsibleError("Project '%s' not found%s" % (name, scope))
        if len(matches) > 1:
            if organization:
                raise AnsibleError("Multiple projects named '%s' found in organization '%s'" % (name, organization))
            raise AnsibleError("Multiple projects named '%s' found; specify organization to disambiguate" % name)

        project_id = matches[0].get("id")
        if project_id is None:
            raise AnsibleError("Project '%s' has no ID%s" % (name, scope))
        return project_id
