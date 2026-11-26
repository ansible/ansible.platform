#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.inventory import AnsibleInventory
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.inventory import (
    BASE_PATH,
    CONSTRUCTED_KIND,
    CONSTRUCTED_SOURCE_FIELDS,
    validate_constructed_source_options,
)

_ASSOC_MAP = {
    "instance_groups": ("instance_groups", "name"),
    "input_inventories": ("inventories", "name"),
}

_SERVICE = "controller"


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "inventory"
    MODEL_CLASS = AnsibleInventory
    _ENFORCED_EMPTY_STRING_FIELDS = frozenset({"description"})
    LOOKUP_FIELD = "name"

    _WRITE_ONLY_FIELDS = frozenset({"copy_from"} | set(_ASSOC_MAP))
    _JSON_OBJECT_FIELDS = frozenset({"source_vars"})

    def _validate_action_input(self):
        """Check that source options are supplied only for a constructed inventory."""
        validated = super()._validate_action_input()
        params = validated.validated_params
        validate_constructed_source_options(params.get("kind"), params.get("source_vars"), params.get("limit"))
        return validated

    def _find_existing_resource(self, manager, resource_data):
        """Find the inventory by name and organization before reading its source settings."""
        source_fields = {field: resource_data[field] for field in CONSTRUCTED_SOURCE_FIELDS if resource_data.get(field) is not None}
        if not source_fields:
            return super()._find_existing_resource(manager, resource_data)

        # Discover the inventory on the generic endpoint so a conflicting
        # regular inventory is found before accessing the constructed endpoint.
        lookup_data = {field: value for field, value in resource_data.items() if field not in source_fields}
        found = super()._find_existing_resource(manager, lookup_data)
        if not found or not found.get("id"):
            return found
        if found.get("kind") != CONSTRUCTED_KIND:
            raise AnsibleError("source_vars and limit cannot be applied to an existing inventory that is not constructed")
        detail_lookup = {**resource_data, "name": str(found["id"])}
        return super()._find_existing_resource(manager, detail_lookup)

    def _should_update(self, desired_data, current_data):
        """Compare the limit as text even when the stored pattern consists only of digits."""
        if desired_data.get("limit") is not None and desired_data["limit"] != current_data.get("limit"):
            return True
        return super()._should_update(desired_data, current_data)

    def _resolve_lookup(self, resource, resource_data, validated_params):
        organization = getattr(resource, "organization", None)
        if organization is not None and str(organization).strip().isdigit():
            names = self._client.lookup_organization_names([int(organization)], service=_SERVICE)
            if names:
                resource.organization = names[0]
                resource_data["organization"] = names[0]

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}

        copy_from = self._task.args.get("copy_from")
        association_data = {field: self._task.args.get(field) for field in _ASSOC_MAP}

        name = self._task.args.get("name")
        organization = self._task.args.get("organization")
        state = self._task.args.get("state", "present")
        check_mode = self._task.check_mode

        copied = False
        if copy_from and state not in ("absent", "exists") and not check_mode:
            try:
                self._validate_action_input()
            except Exception as exc:
                return {"changed": False, "failed": True, "msg": str(exc)}
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
                        query_params["organization"] = manager.lookup_resource_id("organizations", "name", organization, service=_SERVICE)
                existing = manager.search_api(BASE_PATH, query_params=query_params)
                if not any(item.get("name") == name for item in existing.get("results", [])):
                    source = copy_from
                    if any(self._task.args.get(field) is not None for field in CONSTRUCTED_SOURCE_FIELDS):
                        source_id = manager.lookup_resource_id("inventories", "name", source, service=_SERVICE)
                        if manager.search_api(f"{BASE_PATH}/{source_id}/").get("kind") != CONSTRUCTED_KIND:
                            raise AnsibleError("source_vars and limit require a constructed inventory as copy_from")
                        source = str(source_id)
                    manager.copy_resource(self.MODULE_NAME, source, name, BASE_PATH, service=_SERVICE)
                    copied = True
            except Exception as exc:
                return {"changed": False, "failed": True, "msg": "Failed to copy from '%s': %s" % (copy_from, exc)}

        result = super().run(tmp, task_vars)
        if copy_from:
            result["copied"] = copied
        if copied:
            result["changed"] = True
        if result.get("failed") or state in ("absent", "exists"):
            return result

        inv_id = result.get("id") or (result.get(self.MODULE_NAME) or {}).get("id")
        if not inv_id:
            return result

        try:
            manager = self._client
            changed = False
            for field, (lookup_endpoint, lookup_field) in _ASSOC_MAP.items():
                desired = association_data.get(field)
                if desired is not None and manager.manage_associations(
                    BASE_PATH, inv_id, field, desired, lookup_endpoint, lookup_field, service=_SERVICE, check_mode=check_mode
                ):
                    changed = True
        except Exception as exc:
            result["failed"] = True
            result["msg"] = "Failed to reconcile associations: %s" % exc
            return result

        if changed:
            result["changed"] = True
        return result
