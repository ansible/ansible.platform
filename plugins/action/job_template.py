#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.job_template import AnsibleJobTemplate
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.job_template import BASE_PATH

# sub-endpoint name -> (lookup_endpoint, lookup_field) used to resolve association items to IDs.
_ASSOC_MAP = {
    "credentials": ("credentials", "name"),
    "labels": ("labels", "name"),
    "instance_groups": ("instance_groups", "name"),
    "notification_templates_started": ("notification_templates", "name"),
    "notification_templates_success": ("notification_templates", "name"),
    "notification_templates_error": ("notification_templates", "name"),
}

_SERVICE = "controller"

# Deprecated field -> (message, version). Surfaced manually in run() below rather than
# via BaseResourceActionPlugin's automatic _DEPRECATED_FIELDS handling, since credential/
# vault_credential are popped from self._task.args before super().run() (and its
# _prepare_action()) ever sees them.
_DEPRECATIONS = {
    "credential": ("The 'credential' parameter is deprecated, use 'credentials' instead.", "4.0.0"),
    "vault_credential": ("The 'vault_credential' parameter is deprecated, use 'credentials' instead.", "4.0.0"),
}


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "job_template"
    MODEL_CLASS = AnsibleJobTemplate
    LOOKUP_FIELD = "name"

    # Safety net: _prepare_action() pops these from resource_data if any slip
    # through the manual pop in run() below, so MODEL_CLASS(**resource_data)
    # never chokes on them.
    _WRITE_ONLY_FIELDS = frozenset(
        {
            "copy_from",
            "survey_spec",
            "credential",
            "vault_credential",
        }
        | set(_ASSOC_MAP)
    )

    def _should_update(self, desired_data, current_data):
        """Compare user-facing FK names or IDs without treating organization as a JT field."""
        desired = dict(desired_data)
        desired.pop("organization", None)
        for field, endpoint in (
            ("inventory", "inventories"),
            ("project", "projects"),
            ("execution_environment", "execution_environments"),
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

        # Pop extra fields before CRUD — they aren't AnsibleJobTemplate fields.
        copy_from = self._task.args.pop("copy_from", None)
        survey_spec = self._task.args.pop("survey_spec", None)
        association_data = {field: self._task.args.pop(field, None) for field in _ASSOC_MAP}

        # Legacy credential/vault_credential aliases fold into credentials.
        credential = self._task.args.pop("credential", None)
        vault_credential = self._task.args.pop("vault_credential", None)
        deprecations = []
        if credential or vault_credential:
            credentials = association_data.get("credentials")
            if credentials is None:
                credentials = []
            if vault_credential:
                credentials.append(vault_credential)
                msg, version = _DEPRECATIONS["vault_credential"]
                deprecations.append({"msg": msg, "version": version, "collection_name": "ansible.platform"})
            if credential:
                credentials.append(credential)
                msg, version = _DEPRECATIONS["credential"]
                deprecations.append({"msg": msg, "version": version, "collection_name": "ansible.platform"})
            association_data["credentials"] = credentials

        name = self._task.args.get("name")
        state = self._task.args.get("state", "present")
        check_mode = self._task.check_mode

        # copy_from replaces create: copy the source resource under the new name first.
        # The normal CRUD flow below then finds the newly copied resource by name and
        # applies any remaining parameters as an update, exactly like the idempotent
        # create-or-update path does for a plain create. Mirrors the legacy
        # awx_collection job_template module's copy_from.
        # Never actually copy under check_mode — the subsequent CRUD call still runs and
        # (not finding a resource under the target name) reports a simulated create.
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
        if deprecations:
            result.setdefault("deprecations", []).extend(deprecations)
        if result.get("failed") or state in ("absent", "exists"):
            return result

        jt_id = result.get("id") or (result.get(self.MODULE_NAME) or {}).get("id")
        if not jt_id:
            return result

        reconcile_fields = {k: v for k, v in association_data.items() if v is not None}
        if check_mode:
            # Never associate/disassociate or touch survey_spec under check_mode — only
            # report whether a change would be made.
            if reconcile_fields or survey_spec is not None:
                result["changed"] = True
            return result

        try:
            manager = self._client
            changed = False
            for field, (lookup_endpoint, lookup_field) in _ASSOC_MAP.items():
                desired = association_data.get(field)
                if desired is not None and manager.manage_associations(BASE_PATH, jt_id, field, desired, lookup_endpoint, lookup_field, service=_SERVICE):
                    changed = True
            if survey_spec is not None and manager.manage_sub_resource(BASE_PATH, jt_id, "survey_spec", survey_spec):
                changed = True
        except Exception as exc:
            result["failed"] = True
            result["msg"] = "Failed to reconcile associations/survey_spec: %s" % exc
            return result

        if changed:
            result["changed"] = True
        return result
