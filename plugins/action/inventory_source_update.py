#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.inventory_source_update module.

Launches an inventory source update (sync) via Controller. This is not a CRUD
resource — every invocation launches a new update. Waiting for completion is
handled by PlatformService/DirectHTTPClient.execute() (see platform_manager.py
and direct_client.py) so that non-Ansible SDK consumers get the same wait
semantics — this action plugin only launches and forwards the result.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import dataclasses

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.inventory_source_update import AnsibleInventorySourceUpdate
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_client import WaitTimeoutError


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for launching inventory source updates."""

    MODULE_NAME = "inventory_source_update"
    MODEL_CLASS = AnsibleInventorySourceUpdate

    def _build_resource(self, resource_data: dict):
        """Filter resource_data to AnsibleInventorySourceUpdate fields.

        The launch argspec includes control params (wait/interval/timeout)
        that are not AnsibleInventorySourceUpdate fields.
        """
        model_fields = {f.name for f in dataclasses.fields(self.MODEL_CLASS)}
        return self.MODEL_CLASS(**{k: v for k, v in resource_data.items() if k in model_fields})

    def _build_ansible_data(self, resource, validated_params, operation):
        """Forward wait/interval/timeout so manager.execute() can poll for us.

        These are not AnsibleInventorySourceUpdate fields — PlatformService/
        DirectHTTPClient pop them off the dict before constructing the dataclass.
        """
        ansible_data = super()._build_ansible_data(resource, validated_params, operation)
        ansible_data["wait"] = validated_params.get("wait", False)
        ansible_data["interval"] = validated_params.get("interval", 2.0)
        ansible_data["timeout"] = validated_params.get("timeout")
        return ansible_data

    def run(self, tmp=None, task_vars=None):
        # Preparation can fail before _prepare_action() returns a result; keep
        # a valid Ansible result available so the exception handler below does
        # not mask the original validation, documentation, or connection error.
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            resource_data = prepared["resource_data"]
            manager = prepared["manager"]

            resource = self._build_resource(resource_data)
            ansible_data = self._build_ansible_data(resource, validated_params, "create")

            # Inventory source updates are never idempotent — every real run
            # launches a new update — so check mode must not call manager.execute().
            if self._task.check_mode:
                result.update(
                    {
                        "changed": True,
                        "failed": False,
                        "id": None,
                        "status": "pending",
                        "msg": "Check mode: inventory source update would be launched.",
                    }
                )
                return result

            # manager.execute() launches the update and, when wait=True, polls
            # for completion itself (PlatformService/DirectHTTPClient) — this
            # action plugin never polls or sleeps.
            launch_result = manager.execute(
                operation="create",
                module_name=self.MODULE_NAME,
                ansible_data=ansible_data,
            )

            status = launch_result.get("status", "pending")
            result.update(
                {
                    "changed": True,
                    "id": launch_result.get("id"),
                    "status": status,
                }
            )

            if status in ("error", "failed", "canceled"):
                result["failed"] = True
                result["msg"] = "Inventory source update %s finished with status: %s" % (launch_result.get("id"), status)

        except WaitTimeoutError as exc:
            # The update was launched and is still running on Controller even
            # though waiting for it gave up — preserve id/status so operators can
            # still register/poll/cancel it from the task result.
            last = exc.last_result
            result.update(
                {
                    "changed": True,
                    "failed": True,
                    "id": last.get("id"),
                    "status": last.get("status", "unknown"),
                    "msg": str(exc),
                }
            )

        except Exception as exc:
            import traceback as _tb

            self._display.vvv("Error in inventory_source_update action plugin: %s" % exc)
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result
