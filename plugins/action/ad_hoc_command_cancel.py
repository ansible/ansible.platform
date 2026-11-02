#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ad_hoc_command_cancel module.

Cancels a Controller ad hoc command by POSTing to its /cancel/ sub-endpoint.
Already-finished commands are a safe no-op (changed=False) unless
fail_if_not_running is True.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from typing import Optional

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import WaitTimeoutError


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "ad_hoc_command_cancel"

    def run(self, tmp: object = None, task_vars: Optional[dict] = None) -> dict:
        """Cancel a Controller ad hoc command via the SDK client.

        Args:
            tmp: Deprecated parameter.
            task_vars: Task variables dictionary.

        Returns:
            dict: Result with id, changed, status keys.
        """
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            manager = prepared["manager"]

            command_id = validated_params.get("command_id")
            fail_if_not_running = validated_params.get("fail_if_not_running", False)
            interval = validated_params.get("interval", 1.0)
            timeout = validated_params.get("timeout", 0)

            if not command_id:
                raise AnsibleError("command_id is required")
            if interval <= 0:
                raise AnsibleError("interval must be greater than 0")
            if timeout < 0:
                raise AnsibleError("timeout must be 0 or greater")

            if self._task.check_mode:
                can_cancel = manager.can_cancel_resource(command_id, "ad_hoc_commands", service="controller")
                if not can_cancel:
                    if fail_if_not_running:
                        raise AnsibleError("Ad Hoc Command is not running")
                    result.update({"changed": False, "id": command_id, "status": "already finished"})
                    return result
                result.update(
                    {
                        "changed": True,
                        "id": command_id,
                        "status": "cancel would be attempted (check mode)",
                    }
                )
                return result

            cancel_result = manager.cancel_resource(
                resource_id=command_id,
                cancel_endpoint_path="ad_hoc_commands",
                fail_if_not_running=fail_if_not_running,
                timeout=timeout,
                interval=interval,
                service="controller",
                wait=True,
            )

            result.update(cancel_result)

        except WaitTimeoutError as exc:
            lr = exc.last_result or {}
            result.update(
                {
                    "changed": True,
                    "failed": True,
                    "msg": str(exc),
                    "id": lr.get("id", command_id),
                    "status": lr.get("status", "unknown"),
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
