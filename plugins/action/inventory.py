#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.inventory module.

Migrated from awx.awx/ansible.controller inventory module. Uses Pattern C
(custom run override) due to:
  - Association fields (instance_groups, input_inventories)
  - Copy operation (copy_from)

Note: the legacy module also rejected changing an existing inventory's
``kind`` from a regular inventory to ``smart`` client-side, purely as a
friendlier error than whatever the API itself returns. That client-side
guard is not reproduced here — Controller's own validation on the API call
is treated as sufficient — since it is not a resource field with a value
of its own.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
from typing import Any

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.inventory import AnsibleInventory

logger = logging.getLogger(__name__)

_ASSOCIATION_FIELDS = (
    "instance_groups",
    "input_inventories",
)

_INVENTORY_BASE_PATH = "/api/controller/v2/inventories"

_ASSOCIATION_MAP = {
    "instance_groups": ("/api/controller/v2/instance_groups/", "name"),
    "input_inventories": ("/api/controller/v2/inventories/", "name"),
}


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for inventory module."""

    MODULE_NAME = "inventory"
    MODEL_CLASS = AnsibleInventory
    LOOKUP_FIELD = "name"

    _WRITE_ONLY_FIELDS = frozenset(
        {
            "copy_from",
            "instance_groups",
            "input_inventories",
        }
    )

    def _build_ansible_data(self, resource: Any, validated_params: dict, operation: str) -> dict:
        """Build ansible_data from explicitly-provided task parameters only."""
        data = {k: getattr(resource, k) for k in validated_params if hasattr(resource, k)}
        if getattr(resource, "id", None) is not None:
            data["id"] = resource.id
        return data

    def run(self, tmp: object = None, task_vars: dict = None) -> dict:
        """Run the inventory action plugin.

        Extends the base run() to handle:
        - copy_from: Copy an existing inventory before applying changes
        - Association fields: instance_groups, input_inventories

        All HTTP calls are delegated to the SDK layer (PlatformService / DirectHTTPClient).
        """
        copy_from = self._task.args.pop("copy_from", None)
        state = self._task.args.get("state", "present")

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

        if copy_from and state not in ("absent", "deleted"):
            # Preparation can fail before _prepare_action() returns a result;
            # keep a valid Ansible result available so the except block below
            # does not mask the original validation/connection error.
            result = {}
            try:
                prepared = self._prepare_action(tmp, task_vars)
                result = prepared["result"]
                manager = prepared["manager"]

                # Idempotency: copy_from should only ever seed a brand-new resource. If
                # a resource with the target name (scoped by organization) already
                # exists, skip copy_resource and fall through to a normal find-or-update
                # run instead — otherwise every re-run would create another copy.
                existing = None
                try:
                    existing = manager.execute(
                        operation="find",
                        module_name=self.MODULE_NAME,
                        ansible_data={"name": self._task.args.get("name"), "organization": self._task.args.get("organization")},
                    )
                except Exception:
                    existing = None

                if existing and existing.get("id"):
                    result = super().run(tmp, task_vars)
                else:
                    copied = manager.copy_resource(
                        self.MODULE_NAME,
                        copy_from,
                        self._task.args.get("name"),
                        _INVENTORY_BASE_PATH,
                    )

                    if copied and copied.get("id"):
                        # No need to inject an "id" into self._task.args here — "id" isn't a
                        # declared module option (would fail argspec validation on this second
                        # call), and the copy already has the target name, so a plain re-run
                        # finds it naturally via LOOKUP_FIELD (name) + organization.
                        result = super().run(tmp, task_vars)
                        # copy_resource() always creates a new resource — that's a change even
                        # if the follow-up update-with-remaining-params finds nothing left to
                        # change and would otherwise report changed=False on its own.
                        result["changed"] = True
                    else:
                        result.update(changed=True, failed=False, **{self.MODULE_NAME: copied or {}})

            except Exception as exc:
                result.update(changed=False, failed=True, msg=str(exc))
                return result
        else:
            result = super().run(tmp, task_vars)

        if result.get("failed"):
            return result

        inventory_id = result.get("id") or (result.get(self.MODULE_NAME, {}) or {}).get("id")

        # check_mode: base_action.py's own create/update short-circuit happens before
        # this point, but for an *update* to an already-existing resource it still
        # returns the real inventory_id — skip the association sync entirely so
        # check_mode never issues real associate/disassociate writes.
        if inventory_id and state not in ("absent", "deleted", "exists") and not self._task.check_mode:
            manager = self._client
            if manager:
                for field, (lookup_ep, lookup_field) in _ASSOCIATION_MAP.items():
                    desired = association_data.get(field)
                    if desired is not None:
                        changed = manager.manage_associations(
                            _INVENTORY_BASE_PATH,
                            inventory_id,
                            field,
                            desired,
                            lookup_ep,
                            lookup_field,
                        )
                        if changed:
                            result["changed"] = True

        return result
