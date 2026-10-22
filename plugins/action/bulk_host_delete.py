#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for bulk_host_delete module.

Deletes multiple hosts in a single POST to /api/controller/v2/bulk/host_delete/.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from typing import Optional

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.bulk_host_delete import AnsibleBulkHostDelete
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.bulk_host_delete import BULK_HOST_DELETE_ENDPOINT


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "bulk_host_delete"
    MODEL_CLASS = AnsibleBulkHostDelete
    LOOKUP_FIELD = "hosts"

    def run(self, tmp: object = None, task_vars: Optional[dict] = None) -> dict:
        """Bulk delete hosts via the Controller bulk API.

        Args:
            tmp: Deprecated parameter.
            task_vars: Task variables dictionary.

        Returns:
            dict: Result with changed key.
        """
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            manager = prepared["manager"]

            hosts = validated_params.get("hosts")

            if not hosts:
                raise AnsibleError("hosts is required and must be a non-empty list of host IDs")

            if self._task.check_mode:
                result.update(
                    {
                        "changed": True,
                        "msg": f"Would delete {len(hosts)} host(s) (check mode)",
                    }
                )
                return result

            manager.launch_resource(
                launch_url=BULK_HOST_DELETE_ENDPOINT,
                payload={"hosts": hosts},
                service="controller",
            )

            result["changed"] = True

        except Exception as exc:
            import traceback as _tb

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result
