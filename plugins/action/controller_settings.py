#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for the Controller settings singleton."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import asdict

import yaml
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_settings import AnsibleControllerSettings


class ActionModule(BaseResourceActionPlugin):
    """Manage Controller settings while retaining the legacy module interface."""

    MODULE_NAME = "controller_settings"
    _MUTUALLY_EXCLUSIVE = [["name", "settings"]]
    _REQUIRED_ONE_OF = [["name", "settings"]]

    @staticmethod
    def _coerce_type(value):
        """Convert legacy string values to common Controller setting types."""
        if value is None or not isinstance(value, str):
            return value

        if (value.startswith("{") and value.endswith("}")) or (value.startswith("[") and value.endswith("]")):
            try:
                return yaml.safe_load(value)
            except yaml.YAMLError as exc:
                raise ValueError(f"Unable to parse setting value as YAML: {exc}") from exc

        if value.lower() in ("true", "false", "t", "f"):
            return value.lower() in ("true", "t")

        try:
            return int(value)
        except ValueError:
            return value

    @staticmethod
    def _result_payload(current_settings, requested_settings, updated_settings, changed):
        """Build stable legacy-compatible output fields."""
        return {
            "changed": changed,
            "old_values": {key: current_settings.get(key) for key in requested_settings},
            "new_values": dict(requested_settings),
            "controller_settings": {
                "settings": updated_settings,
                "old_values": {key: current_settings.get(key) for key in requested_settings},
                "new_values": dict(requested_settings),
                "changed": changed,
            },
        }

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}

        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            manager = prepared["manager"]

            name = validated_params.get("name")
            requested_settings = validated_params.get("settings")
            if name is not None and validated_params.get("value") is None:
                raise ValueError("value is required when name is provided")
            if requested_settings is None:
                requested_settings = {name: self._coerce_type(validated_params.get("value"))}
            else:
                requested_settings = dict(requested_settings)

            current_result = manager.execute(
                operation="find",
                module_name=self.MODULE_NAME,
                ansible_data=asdict(AnsibleControllerSettings(settings={})),
            )
            current_settings = current_result.get("settings", {}) or {}
            to_update = {key: value for key, value in requested_settings.items() if key not in current_settings or current_settings[key] != value}

            if self._task.diff:
                result["diff"] = {
                    "before": {key: current_settings.get(key) for key in to_update},
                    "after": dict(to_update),
                }

            if not to_update:
                result.update(self._result_payload(current_settings, requested_settings, current_settings, False))
                result["failed"] = False
                if name is not None:
                    result["value"] = current_settings.get(name)
                else:
                    result["values"] = {key: current_settings.get(key) for key in requested_settings}
                return result

            if self._task.check_mode:
                result.update(self._result_payload(current_settings, requested_settings, current_settings, True))
                result["failed"] = False
                if name is not None:
                    result["value"] = to_update.get(name)
                else:
                    result["values"] = dict(to_update)
                return result

            update_result = manager.execute(
                operation="update",
                module_name=self.MODULE_NAME,
                ansible_data=asdict(AnsibleControllerSettings(settings=to_update)),
            )
            updated_settings = update_result.get("settings", {}) or {}
            result.update(self._result_payload(current_settings, requested_settings, updated_settings, True))
            result["failed"] = False
            if name is not None:
                result["value"] = updated_settings.get(name)
            else:
                result["values"] = {key: updated_settings.get(key) for key in requested_settings}

        except Exception as exc:
            self._display.vvv(f"Error in controller_settings action plugin: {exc}")
            result["failed"] = True
            result["msg"] = str(exc)

        return result
