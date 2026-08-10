#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.ad_hoc_command module.

Launches an ad hoc command via Gateway. This is not a CRUD resource —
every invocation creates a new command execution.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import time

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.ad_hoc_command import AnsibleAdHocCommand


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for launching ad hoc commands."""

    MODULE_NAME = "ad_hoc_command"
    MODEL_CLASS = AnsibleAdHocCommand

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}
        self._task_vars = task_vars
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        try:
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                raise AnsibleError("Could not load DOCUMENTATION for ad_hoc_command module")

            validated_input = self._validate_data(self._task.args.copy(), argspec, "input")

            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager
            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            validated_params = validated_input.validated_parameters

            wait = validated_params.get("wait", False)
            interval = validated_params.get("interval", 2.0)
            timeout = validated_params.get("timeout")

            resource_data = {k: v for k, v in validated_params.items() if v is not None and k not in self._AUTH_PARAMS}
            resource = self.MODEL_CLASS(**{k: v for k, v in resource_data.items() if hasattr(self.MODEL_CLASS, k)})
            ansible_data = self._build_ansible_data(resource, validated_params, "create")

            launch_result = manager.execute(
                operation="create",
                module_name=self.MODULE_NAME,
                ansible_data=ansible_data,
            )

            command_id = launch_result.get("id")
            status = launch_result.get("status", "pending")

            if not wait:
                result.update(
                    {
                        "changed": True,
                        "id": command_id,
                        "status": status,
                    }
                )
                return result

            # Poll for completion
            status = self._wait_for_completion(
                manager,
                command_id,
                interval=interval,
                timeout=timeout,
            )

            result.update(
                {
                    "changed": True,
                    "id": command_id,
                    "status": status,
                }
            )

            if status in ("error", "failed", "canceled"):
                result["failed"] = True
                result["msg"] = "Ad hoc command %s finished with status: %s" % (command_id, status)

        except Exception as exc:
            import traceback as _tb

            self._display.vvv("Error in ad_hoc_command action plugin: %s" % exc)
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result

    def _wait_for_completion(self, manager: object, command_id: int, interval: float = 2.0, timeout: float = None) -> str:
        """Poll the gateway API until the ad hoc command finishes.

        Args:
            manager: The RPC client / manager instance.
            command_id: The ad hoc command ID to poll.
            interval: Seconds between polls.
            timeout: Maximum seconds to wait (None = no limit).

        Returns:
            str: Final status string of the command.

        Raises:
            AnsibleError: If the timeout is exceeded.
        """
        start = time.monotonic()

        while True:
            response = manager.execute(
                operation="find",
                module_name=self.MODULE_NAME,
                ansible_data={"id": command_id},
            )
            finished = response.get("finished") or response.get("event_processing_finished")
            if finished:
                return response.get("status", "unknown")

            elapsed = time.monotonic() - start
            if timeout is not None and elapsed >= timeout:
                raise AnsibleError(
                    "Timed out waiting for ad hoc command %s after %d seconds (status: %s)" % (command_id, timeout, response.get("status", "unknown"))
                )

            self._display.vvvv("Waiting for ad hoc command %s (status: %s, elapsed: %.0fs)" % (command_id, response.get("status", "unknown"), elapsed))
            time.sleep(interval)
