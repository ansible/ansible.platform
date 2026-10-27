#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.workflow_job_template import (
    AnsibleWorkflowJobTemplate,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.workflow_job_template import BASE_PATH

_ASSOC_MAP = {
    "labels": ("labels", "name"),
    "notification_templates_started": ("notification_templates", "name"),
    "notification_templates_success": ("notification_templates", "name"),
    "notification_templates_error": ("notification_templates", "name"),
    "notification_templates_approvals": ("notification_templates", "name"),
}

_SERVICE = "controller"


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "workflow_job_template"
    MODEL_CLASS = AnsibleWorkflowJobTemplate
    LOOKUP_FIELD = "name"

    _WRITE_ONLY_FIELDS = frozenset(
        {
            "copy_from",
            "survey_spec",
        }
        | set(_ASSOC_MAP)
    )

    def _should_update(self, desired_data, current_data):
        desired = dict(desired_data)
        desired.pop("organization", None)
        for field, endpoint in (
            ("inventory", "inventories"),
            ("webhook_credential", "credentials"),
        ):
            value = desired.get(field)
            if value is not None and str(value).isdigit() and current_data.get(field) is not None:
                resource = self._client.search_api(f"{BASE_PATH.rsplit('/', 1)[0]}/{endpoint}/{value}/")
                desired[field] = resource.get("name", value)
        return super()._should_update(desired, current_data)

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}

        copy_from = self._task.args.pop("copy_from", None)
        survey_spec = self._task.args.pop("survey_spec", None)
        association_data = {field: self._task.args.pop(field, None) for field in _ASSOC_MAP}

        name = self._task.args.get("name")
        state = self._task.args.get("state", "present")
        check_mode = self._task.check_mode

        copied = False
        if copy_from and state not in ("absent", "exists") and not check_mode:
            try:
                super(BaseResourceActionPlugin, self).run(tmp, task_vars)
                self._task_vars = task_vars
                manager, facts_to_set = self._get_or_spawn_manager(task_vars)
                self._client = manager
                existing = manager.search_api(BASE_PATH, query_params={"name": name})
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

        wjt_id = result.get("id") or (result.get(self.MODULE_NAME) or {}).get("id")
        if not wjt_id:
            return result

        reconcile_fields = {k: v for k, v in association_data.items() if v is not None}
        if check_mode:
            if reconcile_fields or survey_spec is not None:
                result["changed"] = True
            return result

        try:
            manager = self._client
            changed = False
            for field, (lookup_endpoint, lookup_field) in _ASSOC_MAP.items():
                desired = association_data.get(field)
                if desired is not None and manager.manage_associations(BASE_PATH, wjt_id, field, desired, lookup_endpoint, lookup_field, service=_SERVICE):
                    changed = True
            if survey_spec is not None and manager.manage_sub_resource(BASE_PATH, wjt_id, "survey_spec", survey_spec):
                changed = True
        except Exception as exc:
            result["failed"] = True
            result["msg"] = "Failed to reconcile associations/survey_spec: %s" % exc
            return result

        if changed:
            result["changed"] = True
        return result
