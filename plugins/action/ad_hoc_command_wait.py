#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ad_hoc_command_wait module.

Polls a Controller ad hoc command until it reaches a terminal status.
Uses the SDK wait_for_completion() method for consistent wait semantics.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from typing import Optional

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.ad_hoc_command_wait import AD_HOC_COMMANDS_DETAIL_ENDPOINT
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import WaitTimeoutError

FAILED_STATUSES = frozenset({"failed", "error", "canceled"})


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "ad_hoc_command_wait"

    def run(self, tmp: object = None, task_vars: Optional[dict] = None) -> dict:
        """Wait for a Controller ad hoc command to reach a terminal status.

        Args:
            tmp: Deprecated parameter.
            task_vars: Task variables dictionary.

        Returns:
            dict: Result with id, elapsed, started, finished, status keys.
        """
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            manager = prepared["manager"]

            command_id = validated_params.get("command_id")
            interval = validated_params.get("interval", 2.0)
            timeout = validated_params.get("timeout")
            wait_timeout = float(timeout) if timeout is not None else None
            if wait_timeout is None or wait_timeout == 0:
                wait_timeout = -1.0
            elif wait_timeout < 0:
                raise AnsibleError("timeout must be 0 or greater")

            if not command_id:
                raise AnsibleError("command_id is required")

            resource_url = AD_HOC_COMMANDS_DETAIL_ENDPOINT.format(id=command_id)

            wait_result = manager.wait_for_completion(
                resource_url=resource_url,
                timeout=wait_timeout,
                interval=float(interval),
                service="controller",
            )

            status = wait_result.get("status", "")
            result.update(
                {
                    "changed": False,
                    "id": wait_result.get("id", command_id),
                    "elapsed": wait_result.get("elapsed", 0.0),
                    "started": wait_result.get("started", ""),
                    "finished": wait_result.get("finished", ""),
                    "status": status,
                }
            )

            if status in FAILED_STATUSES:
                result["failed"] = True
                result["msg"] = f"Ad hoc command {command_id} finished with status: {status}"

        except WaitTimeoutError as exc:
            last = exc.last_result or {}
            result["failed"] = True
            result["msg"] = str(exc)
            result["id"] = last.get("id", command_id)
            result["status"] = last.get("status", "unknown")
            result["elapsed"] = last.get("elapsed", 0.0)

        except Exception as exc:
            import traceback as _tb

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result
