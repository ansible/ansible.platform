#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.inventory import InventoryTransformMixin_v2
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.inventory_source import InventorySourceTransformMixin_v2
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import WaitTimeoutError
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import build_endpoint_request

_SERVICE = "controller"


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "inventory_source_update"

    def run(self, tmp=None, task_vars=None):
        prepared = self._prepare_action(tmp, task_vars)
        result = prepared["result"]
        params = prepared["validated_params"]
        manager = prepared["manager"]

        name = params.get("name")
        inventory = params.get("inventory")
        organization = params.get("organization")
        wait = params.get("wait", False)
        interval = params.get("interval", 2.0)
        timeout = params.get("timeout")

        try:
            inventory_id = self._resolve_inventory(manager, inventory, organization)
            source_id = self._resolve_inventory_source(manager, name, inventory_id)
        except Exception as exc:
            result.update({"changed": False, "failed": True, "msg": str(exc)})
            return result

        if self._task.check_mode:
            result.update({"changed": True, "failed": False, "msg": "Inventory source update skipped (check mode)"})
            return result

        if wait and interval <= 0:
            result.update({"changed": False, "failed": True, "msg": "Polling interval must be positive, got %s" % interval})
            return result

        try:
            sync_operation = InventorySourceTransformMixin_v2.get_endpoint_operations()["sync"]
            if sync_operation.method != "POST":
                raise AnsibleError("Inventory source sync endpoint operation must use POST")
            sync_path, sync_payload = build_endpoint_request(sync_operation, {"id": source_id})
            launch_result = manager.launch_resource(sync_path, sync_payload, service=_SERVICE, retry=False)
        except Exception as exc:
            result.update({"changed": False, "failed": True, "msg": str(exc)})
            return result

        job_id = launch_result.get("id") or launch_result.get("inventory_update")
        if not job_id:
            result.update({"changed": True, "failed": True, "msg": "Launch response did not include a job ID"})
            return result
        job_status = launch_result.get("status", "unknown")
        job_url = launch_result.get("url") or "inventory_updates/%d" % job_id

        if not wait:
            result.update({"changed": True, "failed": False, "id": job_id, "status": job_status})
            return result

        try:
            wait_result = manager.wait_for_completion(
                job_url,
                timeout=float(timeout) if timeout is not None else None,
                interval=float(interval),
                service=_SERVICE,
            )
            final_status = wait_result.get("status", "unknown")
            failed = final_status in ("failed", "error", "canceled")

            result.update({"changed": True, "failed": failed, "id": wait_result.get("id", job_id), "status": final_status})
            if failed:
                result["msg"] = "Inventory source update %s finished with status: %s" % (job_id, final_status)
        except WaitTimeoutError as exc:
            lr = exc.last_result or {}
            result.update(
                {
                    "changed": True,
                    "failed": True,
                    "msg": str(exc),
                    "id": lr.get("id", job_id),
                    "status": lr.get("status", "unknown"),
                }
            )
        except Exception as exc:
            result.update(
                {
                    "changed": True,
                    "failed": True,
                    "msg": "Failed to poll inventory source update %s: %s" % (job_id, exc),
                    "id": job_id,
                    "status": "unknown",
                }
            )

        return result

    def _resolve_inventory(self, manager, inventory, organization):
        if str(inventory).isdigit():
            return int(inventory)
        if organization:
            org_id = manager.lookup_resource_id("organizations", "name", organization, service=_SERVICE)
            inventory_list_operation = InventoryTransformMixin_v2.get_endpoint_operations()["list"]
            data = manager.search_api(
                inventory_list_operation.path,
                query_params={"name": inventory, "organization": org_id},
            )
            results = data.get("results", [])
            if not results:
                raise AnsibleError("Inventory '%s' not found in organization '%s'" % (inventory, organization))
            return results[0]["id"]
        return manager.lookup_resource_id("inventories", "name", inventory, service=_SERVICE, require_unique=True)

    def _resolve_inventory_source(self, manager, name, inventory_id):
        query_params = {"inventory": inventory_id}
        if str(name).isdigit():
            query_params["id"] = int(name)
        else:
            query_params["name"] = name
        list_operation = InventorySourceTransformMixin_v2.get_endpoint_operations()["list"]
        data = manager.search_api(
            list_operation.path,
            query_params=query_params,
        )
        results = data.get("results", [])
        if not results:
            raise AnsibleError("Inventory source '%s' not found in inventory %s" % (name, inventory_id))
        return results[0]["id"]
