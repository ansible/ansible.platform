#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.schedule module.

Migrated from awx.awx/ansible.controller schedule module. Uses Pattern C
(custom run override) due to association fields (credentials, labels,
instance_groups).
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
from typing import Any

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.schedule import AnsibleSchedule

logger = logging.getLogger(__name__)

_ASSOCIATION_FIELDS = (
    "credentials",
    "labels",
    "instance_groups",
)

_SCHEDULE_BASE_PATH = "/api/controller/v2/schedules"

_ASSOCIATION_MAP = {
    "credentials": ("/api/controller/v2/credentials/", "name"),
    "labels": ("/api/controller/v2/labels/", "name"),
    "instance_groups": ("/api/controller/v2/instance_groups/", "name"),
}


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for schedule module."""

    MODULE_NAME = "schedule"
    MODEL_CLASS = AnsibleSchedule
    LOOKUP_FIELD = "name"

    _WRITE_ONLY_FIELDS = frozenset(_ASSOCIATION_FIELDS)

    def _build_ansible_data(self, resource: Any, validated_params: dict, operation: str) -> dict:
        """Build ansible_data from explicitly-provided task parameters only."""
        data = {k: getattr(resource, k) for k in validated_params if hasattr(resource, k)}
        if getattr(resource, "id", None) is not None:
            data["id"] = resource.id
        return data

    def run(self, tmp: object = None, task_vars: dict = None) -> dict:
        """Run the schedule action plugin.

        Extends the base run() to sync credentials/labels/instance_groups
        association fields after standard CRUD. All HTTP calls are delegated to
        the SDK layer (PlatformService / DirectHTTPClient).
        """
        state = self._task.args.get("state", "present")

        association_data = {}
        for field in _ASSOCIATION_FIELDS:
            val = self._task.args.pop(field, None)
            if val is not None:
                association_data[field] = val

        result = super().run(tmp, task_vars)

        if result.get("failed"):
            return result

        schedule_id = result.get("id") or (result.get(self.MODULE_NAME, {}) or {}).get("id")

        if schedule_id and state not in ("absent", "deleted", "exists"):
            manager = self._client
            if manager:
                for field, (lookup_ep, lookup_field) in _ASSOCIATION_MAP.items():
                    desired = association_data.get(field)
                    if desired is not None:
                        changed = manager.manage_associations(
                            _SCHEDULE_BASE_PATH,
                            schedule_id,
                            field,
                            desired,
                            lookup_ep,
                            lookup_field,
                        )
                        if changed:
                            result["changed"] = True

        return result
