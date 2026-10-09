#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2025, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for bulk host creation in Automation Controller."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_bulk_host_create import (
    AnsibleControllerBulkHostCreate,
)


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "controller_bulk_host_create"
    MODEL_CLASS = AnsibleControllerBulkHostCreate

    def run(self, tmp=None, task_vars=None):
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            manager = prepared["manager"]

            hosts = validated_params.get("hosts", [])
            inventory = validated_params.get("inventory")

            if self._task.check_mode:
                result.update(
                    {
                        "changed": True,
                        "failed": False,
                        "msg": "Would create %d host(s) in inventory '%s'" % (len(hosts), inventory),
                        "hosts": hosts,
                    }
                )
                return result

            inv_id = manager.lookup_resource_id("inventories", "name", inventory, service="controller")

            prepared_hosts = []
            for h in hosts:
                host_entry = dict(h)
                if "variables" in host_entry and host_entry["variables"] is not None:
                    host_entry["variables"] = json.dumps(host_entry["variables"])
                prepared_hosts.append(host_entry)

            response = manager.bulk_host_create(
                inventory_id=inv_id,
                hosts=prepared_hosts,
                service="controller",
            )

            result.update(
                {
                    "changed": True,
                    "failed": False,
                    "response": response,
                    "hosts": hosts,
                }
            )

        except Exception as exc:
            import traceback as _tb

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result
