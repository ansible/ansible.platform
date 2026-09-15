#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.notification_template module.

Migrated from awx.awx/ansible.controller notification_template module. Uses
Pattern C (custom run override) due to the copy_from operation.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import logging
from typing import Any

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.notification_template import AnsibleNotificationTemplate

logger = logging.getLogger(__name__)

_NOTIFICATION_TEMPLATE_BASE_PATH = "/api/controller/v2/notification_templates"


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for notification_template module."""

    MODULE_NAME = "notification_template"
    MODEL_CLASS = AnsibleNotificationTemplate
    LOOKUP_FIELD = "name"

    _WRITE_ONLY_FIELDS = frozenset({"copy_from"})

    def _build_ansible_data(self, resource: Any, validated_params: dict, operation: str) -> dict:
        """Build ansible_data from explicitly-provided task parameters only."""
        data = {k: getattr(resource, k) for k in validated_params if hasattr(resource, k)}
        if getattr(resource, "id", None) is not None:
            data["id"] = resource.id
        return data

    def run(self, tmp: object = None, task_vars: dict = None) -> dict:
        """Run the notification_template action plugin.

        Extends the base run() to handle copy_from: copy an existing
        notification_template before applying changes. All HTTP calls are
        delegated to the SDK layer (PlatformService / DirectHTTPClient).
        """
        copy_from = self._task.args.pop("copy_from", None)
        state = self._task.args.get("state", "present")

        if copy_from and state not in ("absent", "deleted"):
            result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
            self._task_vars = task_vars or {}

            try:
                manager, facts_to_set = self._get_or_spawn_manager(task_vars or {})
                self._client = manager
                if facts_to_set:
                    result["ansible_facts"] = facts_to_set
                    result["_ansible_facts_cacheable"] = True

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
                        _NOTIFICATION_TEMPLATE_BASE_PATH,
                    )

                    if copied and copied.get("id"):
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

        return result
