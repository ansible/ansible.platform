#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.ad_hoc_command module.

Launches an ad hoc command via Controller. This is not a CRUD resource —
every invocation creates a new command execution. Waiting for completion is
handled by PlatformService/DirectHTTPClient.execute() (see platform_manager.py
and direct_client.py) so that non-Ansible SDK consumers get the same wait
semantics — this action plugin only launches and forwards the result.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import dataclasses

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.ad_hoc_command import AnsibleAdHocCommand
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_client import WaitTimeoutError


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for launching ad hoc commands."""

    MODULE_NAME = "ad_hoc_command"
    MODEL_CLASS = AnsibleAdHocCommand

    def _build_ansible_data(self, resource, validated_params, operation):
        """Forward wait/interval/timeout so manager.execute() can poll for us.

        These are not AnsibleAdHocCommand fields — PlatformService/DirectHTTPClient
        pop them off the dict before constructing the dataclass.
        """
        ansible_data = super()._build_ansible_data(resource, validated_params, operation)
        ansible_data["wait"] = validated_params.get("wait", False)
        ansible_data["interval"] = validated_params.get("interval", 2.0)
        ansible_data["timeout"] = validated_params.get("timeout")
        return ansible_data

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

            resource_data = {k: v for k, v in validated_params.items() if v is not None and k not in self._AUTH_PARAMS}
            model_fields = {f.name for f in dataclasses.fields(self.MODEL_CLASS)}
            resource = self.MODEL_CLASS(**{k: v for k, v in resource_data.items() if k in model_fields})
            ansible_data = self._build_ansible_data(resource, validated_params, "create")

            # Ad hoc commands are never idempotent — every real run launches a new
            # command — so check mode must not call manager.execute() at all.
            if self._task.check_mode:
                result.update(
                    {
                        "changed": True,
                        "failed": False,
                        "id": None,
                        "status": "pending",
                        "msg": "Check mode: ad hoc command would be launched.",
                    }
                )
                return result

            # manager.execute() launches the command and, when wait=True, polls
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
                result["msg"] = "Ad hoc command %s finished with status: %s" % (launch_result.get("id"), status)

        except WaitTimeoutError as exc:
            # The command was created and is still running on Controller even
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

            self._display.vvv("Error in ad_hoc_command action plugin: %s" % exc)
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result
