#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2025, Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for bulk host creation in Automation Controller."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.bulk_host_create import (
    AnsibleBulkHostCreate,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.bulk_host_create import BulkHostCreateTransformMixin_v2
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "bulk_host_create"
    MODEL_CLASS = AnsibleBulkHostCreate
    _WRITE_ONLY_FIELDS = frozenset({"organization"})

    def run(self, tmp=None, task_vars=None):
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            manager = prepared["manager"]

            hosts = validated_params.get("hosts", [])
            inventory = validated_params.get("inventory")
            ansible_data = AnsibleBulkHostCreate(
                hosts=hosts,
                inventory=inventory,
                organization=validated_params.get("organization"),
            )
            context = TransformContext(
                manager=manager,
                session=getattr(manager, "session", None),
                cache={},
                api_version="2",
                service="controller",
                operation="create",
            )
            api_data = BulkHostCreateTransformMixin_v2.from_ansible_data(ansible_data, context)
            create_operation = BulkHostCreateTransformMixin_v2.get_endpoint_operations()["create"]
            payload = BulkHostCreateTransformMixin_v2.to_operation_payload(api_data, create_operation)

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

            response = manager.launch_resource(create_operation.path, payload, service="controller", retry=False)

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
