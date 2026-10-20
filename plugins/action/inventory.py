#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.inventory import AnsibleInventory
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.inventory import BASE_PATH

_ASSOC_MAP = {
    "instance_groups": ("instance_groups", "name"),
    "input_inventories": ("inventories", "name"),
}

_SERVICE = "controller"


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "inventory"
    MODEL_CLASS = AnsibleInventory
    LOOKUP_FIELD = "name"

    _WRITE_ONLY_FIELDS = frozenset({"copy_from"} | set(_ASSOC_MAP))

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

        inv_id = result.get("id") or (result.get(self.MODULE_NAME) or {}).get("id")
        if not inv_id:
            return result

        reconcile_fields = {k: v for k, v in association_data.items() if v is not None}
        if check_mode:
            if reconcile_fields:
                result["changed"] = True
            return result

        try:
            manager = self._client
            changed = False
            for field, (lookup_endpoint, lookup_field) in _ASSOC_MAP.items():
                desired = association_data.get(field)
                if desired is not None and manager.manage_associations(BASE_PATH, inv_id, field, desired, lookup_endpoint, lookup_field, service=_SERVICE):
                    changed = True
        except Exception as exc:
            result["failed"] = True
            result["msg"] = "Failed to reconcile associations: %s" % exc
            return result

        if changed:
            result["changed"] = True
        return result
