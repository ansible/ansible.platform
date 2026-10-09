#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.inventory_source import AnsibleInventorySource

_NOTIFICATION_FIELDS = {
    "notification_templates_started": ("notification_templates", "name"),
    "notification_templates_success": ("notification_templates", "name"),
    "notification_templates_error": ("notification_templates", "name"),
}


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "inventory_source"
    MODEL_CLASS = AnsibleInventorySource

    _WRITE_ONLY_FIELDS = frozenset(_NOTIFICATION_FIELDS)

    def run(self, tmp=None, task_vars=None):
        state = self._task.args.get("state", "present")

        association_data = {}
        for field in _NOTIFICATION_FIELDS:
            val = self._task.args.pop(field, None)
            if val is not None:
                association_data[field] = val

        result = super().run(tmp, task_vars)
        if result.get("failed"):
            return result

        resource_id = result.get("id") or (result.get(self.MODULE_NAME) or {}).get("id")

        if resource_id and state not in ("absent", "deleted", "exists") and association_data:
            for field, (lookup_ep, lookup_field) in _NOTIFICATION_FIELDS.items():
                desired = association_data.get(field)
                if desired is not None:
                    if self._client.manage_associations(
                        "inventory_sources",
                        resource_id,
                        field,
                        desired,
                        lookup_ep,
                        lookup_field,
                        service="controller",
                    ):
                        result["changed"] = True

        return result
