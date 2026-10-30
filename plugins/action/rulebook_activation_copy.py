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

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.rulebook_activation_copy import AnsibleRulebookActivationCopy
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.rulebook_activation import (
    ACTIVATION_COPY_ENDPOINT,
)

_SERVICE = "eda"


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for rulebook_activation_copy module."""

    MODULE_NAME = "rulebook_activation_copy"
    MODEL_CLASS = AnsibleRulebookActivationCopy

    def run(self, tmp=None, task_vars=None):
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
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                raise AnsibleError("Could not load DOCUMENTATION for %s module" % self.MODULE_NAME)

            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, "input")
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            params = validated_input.validated_parameters
            name = params.get("name")
            copy_from = params.get("copy_from")

            if not copy_from:
                raise AnsibleError("Parameter 'copy_from' is required for rulebook_activation_copy")

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

            # POST to activations/{id}/copy/ with the new name
            copy_url = ACTIVATION_COPY_ENDPOINT.format(id=existing["id"])
            copy_result = manager.direct_request("POST", copy_url, data={"name": name})

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

    def _find_source_activation(self, manager, name):
        """Find the source activation to copy from.

        Args:
            manager: Platform manager/client instance.
            name: Name of the source activation.

        Returns:
            dict with activation data if found, None otherwise.
        """
        try:
            find_result = manager.execute(
                operation="find",
                module_name="rulebook_activation",
                ansible_data={"name": name},
            )
            if find_result and find_result.get("id"):
                return find_result
        except (ValueError, Exception) as exc:
            if "not found" not in str(exc).lower() and "404" not in str(exc):
                raise
        return None
