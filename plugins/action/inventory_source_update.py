#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.inventory_source_update import (
    CONTROLLER_INVENTORIES_ENDPOINT,
    CONTROLLER_INVENTORY_SOURCE_UPDATE_ENDPOINT,
    CONTROLLER_INVENTORY_SOURCES_ENDPOINT,
    CONTROLLER_INVENTORY_UPDATES_ENDPOINT,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_client import WaitTimeoutError

_SERVICE = "controller"


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "inventory_source_update"
    MODEL_CLASS = None

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp
        self._task_vars = task_vars

        doc = self._get_documentation()
        argspec = self._build_argspec_from_docs(doc) if doc else None
        if not argspec:
            raise AnsibleError("Could not load DOCUMENTATION for inventory_source_update module")

        validated_input = self._validate_data(self._task.args.copy(), argspec, "input")
        manager, facts_to_set = self._get_or_spawn_manager(task_vars)
        self._client = manager
        if facts_to_set:
            result["ansible_facts"] = facts_to_set
            result["_ansible_facts_cacheable"] = True

        params = validated_input.validated_parameters

        name = params.get("name")
        inventory = params.get("inventory")
        organization = params.get("organization")
        wait = params.get("wait", False)
        interval = params.get("interval", 2.0)
        timeout = params.get("timeout")

        if self._task.check_mode:
            result.update({"changed": True, "failed": False, "msg": "Inventory source update skipped (check mode)"})
            return result

        try:
            inventory_id = self._resolve_inventory(manager, inventory, organization)
            source_id = self._resolve_inventory_source(manager, name, inventory_id)

            update_url = CONTROLLER_INVENTORY_SOURCE_UPDATE_ENDPOINT.format(id=source_id)
            launch_result = manager.launch_resource(update_url, {}, service=_SERVICE)
        except Exception as exc:
            result.update({"changed": False, "failed": True, "msg": str(exc)})
            return result

        job_id = launch_result.get("id") or launch_result.get("inventory_update")
        job_status = launch_result.get("status", "unknown")
        job_url = launch_result.get("url", CONTROLLER_INVENTORY_UPDATES_ENDPOINT.format(id=job_id))

        if not wait:
            result.update({"changed": True, "failed": False, "id": job_id, "status": job_status})
            return result

        try:
            wait_result = manager.wait_for_completion(
                job_url,
                timeout=float(timeout) if timeout else None,
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
            result.update({
                "changed": True,
                "failed": True,
                "msg": str(exc),
                "id": lr.get("id", job_id),
                "status": lr.get("status", "unknown"),
            })
        except Exception as exc:
            result.update({
                "changed": True,
                "failed": True,
                "msg": "Failed to poll inventory source update %s: %s" % (job_id, exc),
                "id": job_id,
                "status": "unknown",
            })

        return result

    def _resolve_inventory(self, manager, inventory, organization):
        if str(inventory).isdigit():
            return int(inventory)
        if organization:
            org_id = manager.lookup_resource_id("organizations", "name", organization)
            data = manager.search_api(
                CONTROLLER_INVENTORIES_ENDPOINT,
                query_params={"name": inventory, "organization": org_id},
            )
            results = data.get("results", [])
            if not results:
                raise AnsibleError("Inventory '%s' not found in organization '%s'" % (inventory, organization))
            return results[0]["id"]
        return manager.lookup_resource_id("inventories", "name", inventory, service=_SERVICE)

    def _resolve_inventory_source(self, manager, name, inventory_id):
        if str(name).isdigit():
            return int(name)
        data = manager.search_api(
            CONTROLLER_INVENTORY_SOURCES_ENDPOINT,
            query_params={"name": name, "inventory": inventory_id},
        )
        results = data.get("results", [])
        if not results:
            raise AnsibleError("Inventory source '%s' not found in inventory %s" % (name, inventory_id))
        return results[0]["id"]
