#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.settings module.

The SDK reads current settings, compares requested values, and updates only
changed keys. This action supplies Ansible check mode and formats the result.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import asdict

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.settings import AnsibleSettings


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for settings module."""

    MODULE_NAME = "settings"

    def run(self, tmp=None, task_vars=None):
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            manager = prepared["manager"]

            params = asdict(AnsibleSettings(settings=validated_params.get("settings") or {}))
            params["_platform_check_mode"] = self._task.check_mode
            sdk_result = manager.execute(operation="update", module_name=self.MODULE_NAME, ansible_data=params)
            result.update(
                {
                    "changed": sdk_result["changed"],
                    "failed": False,
                    self.MODULE_NAME: {key: sdk_result[key] for key in ("settings", "old_values", "new_values", "changed")},
                }
            )

        except Exception as e:
            import traceback

            self._display.vvv("Error in settings action plugin: %s" % e)
            result["failed"] = True
            result["msg"] = str(e)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result
