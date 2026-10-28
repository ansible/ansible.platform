#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_project import (
    AnsibleControllerProject,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.controller_project import BASE_PATH

_ASSOC_MAP = {
    "notification_templates_started": ("notification_templates", "name"),
    "notification_templates_success": ("notification_templates", "name"),
    "notification_templates_error": ("notification_templates", "name"),
}

_SERVICE = "controller"


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "controller_project"
    MODEL_CLASS = AnsibleControllerProject
    LOOKUP_FIELD = "name"

    _WRITE_ONLY_FIELDS = frozenset({"copy_from", "wait", "update_project", "interval"} | set(_ASSOC_MAP))

    def _resolve_lookup(self, resource, resource_data, validated_params):
        organization = getattr(resource, "organization", None)
        if organization is not None and str(organization).strip().isdigit():
            names = self._client.lookup_organization_names([int(organization)])
            if names:
                resource.organization = names[0]
                resource_data["organization"] = names[0]

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}

        copy_from = self._task.args.pop("copy_from", None)
        association_data = {field: self._task.args.pop(field, None) for field in _ASSOC_MAP}

        wait = self._task.args.pop("wait", True)
        update_project = self._task.args.pop("update_project", False)
        interval = self._task.args.pop("interval", 2.0)

        name = self._task.args.get("name")
        organization = self._task.args.get("organization")
        timeout = self._task.args.get("timeout")
        state = self._task.args.get("state", "present")
        check_mode = self._task.check_mode

        copied = False
        if copy_from and state not in ("absent", "exists") and not check_mode:
            try:
                super(BaseResourceActionPlugin, self).run(tmp, task_vars)
                self._task_vars = task_vars
                manager, facts_to_set = self._get_or_spawn_manager(task_vars)
                self._client = manager
                query_params = {"name": name}
                if organization is not None:
                    if str(organization).strip().isdigit():
                        query_params["organization"] = int(organization)
                    else:
                        query_params["organization"] = manager.lookup_resource_id("organizations", "name", organization)
                existing = manager.search_api(BASE_PATH, query_params=query_params)
                if not any(item.get("name") == name for item in existing.get("results", [])):
                    manager.copy_resource(self.MODULE_NAME, copy_from, name, BASE_PATH, service=_SERVICE)
                    copied = True
            except Exception as exc:
                return {"changed": False, "failed": True, "msg": "Failed to copy from '%s': %s" % (copy_from, exc)}

        result = super().run(tmp, task_vars)
        if copied:
            result["changed"] = True
        if result.get("failed") or state in ("absent", "exists"):
            return result

        project_id = result.get("id") or (result.get(self.MODULE_NAME) or {}).get("id")
        if not project_id:
            return result

        reconcile_fields = {k: v for k, v in association_data.items() if v is not None}
        if check_mode:
            if reconcile_fields or update_project:
                result["changed"] = True
            return result

        try:
            manager = self._client
            changed = False
            for field, (lookup_endpoint, lookup_field) in _ASSOC_MAP.items():
                desired = association_data.get(field)
                if desired is not None and manager.manage_associations(BASE_PATH, project_id, field, desired, lookup_endpoint, lookup_field, service=_SERVICE):
                    changed = True
        except Exception as exc:
            result["failed"] = True
            result["msg"] = "Failed to reconcile associations: %s" % exc
            return result

        if changed:
            result["changed"] = True

        # --- Project sync / update logic ---
        if state not in ("absent", "exists"):
            try:
                self._handle_project_sync(result, manager, project_id, wait, update_project, interval, timeout)
            except Exception as exc:
                result["failed"] = True
                result["msg"] = "Project sync failed: %s" % exc

        return result

    def _handle_project_sync(self, result, manager, project_id, wait, update_project, interval, timeout):
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import WaitTimeoutError

        project_data = result.get(self.MODULE_NAME) or {}
        summary_fields = project_data.get("summary_fields", {})
        current_update = summary_fields.get("current_update", {})
        scm_revision_before = project_data.get("scm_revision", "")

        if current_update.get("id"):
            if wait:
                update_result = manager.wait_for_completion(
                    "project_updates/%d" % current_update["id"],
                    timeout=float(timeout) if timeout is not None else None,
                    interval=interval,
                    service=_SERVICE,
                )
                if update_result.get("status") not in ("successful",):
                    raise ValueError("Project sync finished with status '%s'" % update_result.get("status"))

        elif update_project:
            launch_result = manager.launch_resource(
                "projects/%d/update" % project_id,
                {},
                service=_SERVICE,
            )

            if not wait:
                result["changed"] = True
                return

            update_url = launch_result.get("url", "project_updates/%d" % launch_result.get("id", project_id))
            update_id = launch_result.get("id")
            if update_id:
                update_url = "project_updates/%d" % update_id

            try:
                update_result = manager.wait_for_completion(
                    update_url,
                    timeout=float(timeout) if timeout is not None else None,
                    interval=interval,
                    service=_SERVICE,
                )
            except WaitTimeoutError:
                result["failed"] = True
                result["msg"] = "Timed out waiting for project sync"
                return

            final_status = update_result.get("status", "")
            if final_status != "successful":
                raise ValueError("Project sync finished with status '%s'" % final_status)

            if update_result.get("scm_revision", "") != scm_revision_before:
                result["changed"] = True
            else:
                result["changed"] = True
