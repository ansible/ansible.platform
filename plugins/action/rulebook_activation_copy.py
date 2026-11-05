#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.rulebook_activation_copy module.

Copies an existing rulebook activation by finding the source activation by
name and POSTing to the copy endpoint.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from typing import Any, Dict, Optional

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.rulebook_activation_copy import AnsibleRulebookActivationCopy
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.rulebook_activation_copy import (
    RulebookActivationCopyTransformMixin_v1,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.retry import RetryConfig
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import build_endpoint_request

# Copy is a non-idempotent POST: retrying a lost response could create a
# duplicate activation, so it disables the manager's default retries.
_NO_RETRY = RetryConfig(max_attempts=1)


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for rulebook_activation_copy module."""

    MODULE_NAME = "rulebook_activation_copy"

    def run(self, tmp: object = None, task_vars: Optional[Dict[str, Any]] = None) -> dict:
        """Copy an existing rulebook activation.

        Args:
            tmp: Deprecated parameter.
            task_vars: Task variables dictionary.

        Returns:
            dict: Ansible result dictionary.
        """
        if task_vars is None:
            task_vars = dict()

        self._task_vars = task_vars
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        try:
            _, params = self._validate_action_input()
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            name = params.get("name")
            copy_from = params.get("copy_from")

            # Find source activation by name
            existing = self._find_source_activation(manager, copy_from)
            if not existing:
                raise AnsibleError("Source activation '%s' not found -- cannot copy" % copy_from)

            if self._task.check_mode:
                result.update(
                    {
                        "changed": True,
                        "failed": False,
                        self.MODULE_NAME: {"name": name},
                    }
                )
                return result

            copy_api_data = RulebookActivationCopyTransformMixin_v1.from_ansible_data(AnsibleRulebookActivationCopy(name=name), {"operation": "copy"})
            copy_operation = RulebookActivationCopyTransformMixin_v1.get_endpoint_operations()["copy"]
            if copy_operation.method != "POST":
                raise AnsibleError("Rulebook activation copy endpoint operation must use POST")
            copy_url, copy_payload = build_endpoint_request(copy_operation, copy_api_data, path_values={"id": existing["id"]})
            copy_result = manager.direct_request(copy_operation.method, copy_url, data=copy_payload, retry_config=_NO_RETRY)

            result.update(
                {
                    "changed": True,
                    "failed": False,
                    self.MODULE_NAME: copy_result,
                    "id": copy_result.get("id"),
                }
            )

        except Exception as e:
            import traceback

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, e))
            result["failed"] = True
            result["msg"] = str(e)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result

    def _find_source_activation(self, manager: Any, name: Optional[str]) -> Optional[dict]:
        """Find the source activation to copy from.

        Args:
            manager: Platform manager/client instance.
            name: Name of the source activation.

        Returns:
            Optional[dict]: Activation data if found, None otherwise.
        """
        try:
            find_result = manager.execute(
                operation="find",
                module_name="rulebook_activation",
                ansible_data={"name": name},
            )
            if find_result and find_result.get("id"):
                return find_result
        except Exception as exc:
            if not self._is_resource_not_found(exc):
                raise
        return None
