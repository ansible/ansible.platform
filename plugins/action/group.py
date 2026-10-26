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

_ASSOCIATION_ALIASES = {
    "groups": "children",
}

_PRESERVE_FIELDS = {
    "hosts": "preserve_existing_hosts",
    "children": "preserve_existing_children",
}

_PRESERVE_ALIASES = {
    "preserve_existing_groups": "preserve_existing_children",
}


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "group"
    MODEL_CLASS = AnsibleGroup

    _WRITE_ONLY_FIELDS = frozenset(list(_ASSOCIATION_FIELDS) + list(_PRESERVE_FIELDS.values()) + list(_ASSOCIATION_ALIASES) + list(_PRESERVE_ALIASES))

    def run(self, tmp=None, task_vars=None):
        state = self._task.args.get("state", "present")

        association_data = {}
        preserve_flags = {}
        for alias, canonical in _ASSOCIATION_ALIASES.items():
            val = self._task.args.pop(alias, None)
            if val is not None:
                self._task.args.setdefault(canonical, val)
        for field in _ASSOCIATION_FIELDS:
            val = self._task.args.pop(field, None)
            if val is not None:
                association_data[field] = val
        for alias, canonical in _PRESERVE_ALIASES.items():
            val = self._task.args.pop(alias, None)
            if val is not None:
                self._task.args.setdefault(canonical, val)
        for assoc_field, preserve_field in _PRESERVE_FIELDS.items():
            preserve_flags[assoc_field] = self._task.args.pop(preserve_field, False)

        result = super().run(tmp, task_vars)
        if result.get("failed"):
            return result

        resource_id = result.get("id") or (result.get(self.MODULE_NAME) or {}).get("id")

        if resource_id and state not in ("absent", "deleted", "exists") and association_data and not self._task.check_mode:
            for field, (lookup_ep, lookup_field) in _ASSOCIATION_FIELDS.items():
                desired = association_data.get(field)
                if desired is not None:
                    if self._client.manage_associations(
                        "groups",
                        resource_id,
                        field,
                        desired,
                        lookup_ep,
                        lookup_field,
                        service="controller",
                        preserve_existing=preserve_flags.get(field, False),
                    ):
                        result["changed"] = True

        return result
