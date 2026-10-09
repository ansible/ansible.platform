#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.group import AnsibleGroup

_ASSOCIATION_FIELDS = {
    "hosts": ("hosts", "name"),
    "children": ("groups", "name"),
}

_PRESERVE_FIELDS = {
    "hosts": "preserve_existing_hosts",
    "children": "preserve_existing_children",
}


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "group"
    MODEL_CLASS = AnsibleGroup

    _WRITE_ONLY_FIELDS = frozenset(
        list(_ASSOCIATION_FIELDS) + list(_PRESERVE_FIELDS.values())
    )

    def run(self, tmp=None, task_vars=None):
        state = self._task.args.get("state", "present")

        association_data = {}
        preserve_flags = {}
        for field in _ASSOCIATION_FIELDS:
            val = self._task.args.pop(field, None)
            if val is not None:
                association_data[field] = val
        for assoc_field, preserve_field in _PRESERVE_FIELDS.items():
            preserve_flags[assoc_field] = self._task.args.pop(preserve_field, False)

        result = super().run(tmp, task_vars)
        if result.get("failed"):
            return result

        resource_id = result.get("id") or (result.get(self.MODULE_NAME) or {}).get("id")

        if resource_id and state not in ("absent", "deleted", "exists") and association_data:
            for field, (lookup_ep, lookup_field) in _ASSOCIATION_FIELDS.items():
                desired = association_data.get(field)
                if desired is not None:
                    if preserve_flags.get(field, False):
                        assoc_path = f"/api/controller/v2/groups/{resource_id}/{field}/"
                        current_data = self._client.search_api(assoc_path, return_all=True)
                        current_ids = [str(item["id"]) for item in current_data.get("results", [])]
                        desired = list(desired) + current_ids

                    if self._client.manage_associations(
                        "groups",
                        resource_id,
                        field,
                        desired,
                        lookup_ep,
                        lookup_field,
                        service="controller",
                    ):
                        result["changed"] = True

        return result
