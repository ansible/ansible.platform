#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.group module.

Migrated from awx.awx/ansible.controller group module. Uses Pattern C
(custom run override) due to association fields (hosts, children).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
from typing import Any

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.group import AnsibleGroup

logger = logging.getLogger(__name__)

_ASSOCIATION_FIELDS = ("hosts", "children")

_GROUP_BASE_PATH = "/api/controller/v2/groups"

_ASSOCIATION_MAP = {
    "hosts": ("/api/controller/v2/hosts/", "name"),
    "children": ("/api/controller/v2/groups/", "name"),
}


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for group module."""

    MODULE_NAME = "group"
    MODEL_CLASS = AnsibleGroup
    LOOKUP_FIELD = "name"

    _WRITE_ONLY_FIELDS = frozenset(_ASSOCIATION_FIELDS + ("preserve_existing_hosts", "preserve_existing_children"))

    def _build_ansible_data(self, resource: Any, validated_params: dict, operation: str) -> dict:
        """Build ansible_data from explicitly-provided task parameters only."""
        data = {k: getattr(resource, k) for k in validated_params if hasattr(resource, k)}
        if getattr(resource, "id", None) is not None:
            data["id"] = resource.id
        return data

    def run(self, tmp: object = None, task_vars: dict = None) -> dict:
        """Run the group action plugin.

        Extends the base run() to sync hosts/children association fields after
        standard CRUD. All HTTP calls are delegated to the SDK layer
        (PlatformService / DirectHTTPClient).
        """
        state = self._task.args.get("state", "present")
        preserve_hosts = bool(self._task.args.pop("preserve_existing_hosts", False))
        preserve_children = bool(self._task.args.pop("preserve_existing_children", False))

        association_data = {}
        for field in _ASSOCIATION_FIELDS:
            val = self._task.args.pop(field, None)
            if val is not None:
                # Popped before BaseResourceActionPlugin.run() validates self._task.args,
                # so the documented list/elements:str constraint never runs on these —
                # restore the minimum check that protects manage_associations() from
                # silently iterating a wrong-typed value (e.g. a bare string) character by
                # character instead of failing clearly.
                if not isinstance(val, list):
                    return {
                        "changed": False,
                        "failed": True,
                        "msg": "argument '%s' is of type %s and we were unable to convert to a list" % (field, type(val).__name__),
                    }
                association_data[field] = val

        result = super().run(tmp, task_vars)

        if result.get("failed"):
            return result

        group_id = result.get("id") or (result.get(self.MODULE_NAME, {}) or {}).get("id")

        # check_mode: base_action.py's own create/update short-circuit happens before
        # this point, but for an *update* to an already-existing resource it still
        # returns the real group_id — skip the association sync entirely so
        # check_mode never issues real associate/disassociate writes.
        if group_id and state not in ("absent", "deleted", "exists") and not self._task.check_mode:
            manager = self._client
            if manager:
                preserve_map = {"hosts": preserve_hosts, "children": preserve_children}
                for field, (lookup_ep, lookup_field) in _ASSOCIATION_MAP.items():
                    desired = association_data.get(field)
                    if desired is not None:
                        changed = manager.manage_associations(
                            _GROUP_BASE_PATH,
                            group_id,
                            field,
                            desired,
                            lookup_ep,
                            lookup_field,
                            disassociate_missing=not preserve_map[field],
                        )
                        if changed:
                            result["changed"] = True

        return result
