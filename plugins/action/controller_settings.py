#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for the Controller settings singleton."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import asdict

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_settings import AnsibleControllerSettings


class ActionModule(BaseResourceActionPlugin):
    """Manage Controller settings while retaining the legacy module interface."""

    MODULE_NAME = "controller_settings"
    _MUTUALLY_EXCLUSIVE = [["name", "settings"]]
    _REQUIRED_ONE_OF = [["name", "settings"]]
    _NO_LOG_FIELDS = frozenset({"value", "settings"})

    _ENCRYPTED_VALUE = "$encrypted$"
    _REDACTED_VALUE = "$redacted$"
    _SENSITIVE_SETTING_MARKERS = (
        "PASSWORD",
        "SECRET",
        "TOKEN",
        "PRIVATE_KEY",
        "CLIENT_KEY",
        "CLIENT_CERT",
        "CA_CERT",
        "KEY_PEM",
        "CERT_PEM",
    )

    @classmethod
    def _is_sensitive_setting(cls, name):
        """Return whether a dynamic Controller setting may contain a secret."""
        upper_name = str(name).upper()
        return any(marker in upper_name for marker in cls._SENSITIVE_SETTING_MARKERS)

    @classmethod
    def _redact_setting_value(cls, name, value):
        """Redact secret setting values while preserving API placeholders."""
        if cls._is_sensitive_setting(name):
            if value is None or value == cls._ENCRYPTED_VALUE:
                return value
            return cls._REDACTED_VALUE
        if isinstance(value, dict):
            return cls._redact_settings(value)
        if isinstance(value, list):
            return [cls._redact_setting_value(name, item) for item in value]
        return value

    @classmethod
    def _redact_settings(cls, settings):
        """Redact sensitive values in a settings mapping, including nested maps."""
        if not isinstance(settings, dict):
            return settings
        return {key: cls._redact_setting_value(key, value) for key, value in settings.items()}

    @classmethod
    def _redact_requested_settings(cls, settings):
        """Redact user-supplied settings before returning them in results."""
        return cls._redact_settings(settings)

    @staticmethod
    def _result_payload(current_settings, requested_settings, updated_settings, changed):
        """Build stable legacy-compatible output fields."""
        old_values = {key: current_settings.get(key) for key in requested_settings}
        return {
            "changed": changed,
            "old_values": ActionModule._redact_settings(old_values),
            "new_values": ActionModule._redact_requested_settings(requested_settings),
            "controller_settings": {
                "settings": ActionModule._redact_settings(updated_settings),
                "old_values": ActionModule._redact_settings(old_values),
                "new_values": ActionModule._redact_requested_settings(requested_settings),
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
            params = asdict(
                AnsibleControllerSettings(
                    settings=validated_params.get("settings"),
                    name=name,
                    value=validated_params.get("value"),
                )
            )
            params["_platform_check_mode"] = self._task.check_mode
            sdk_result = manager.execute(operation="update", module_name=self.MODULE_NAME, ansible_data=params)
            requested = sdk_result["new_values"]
            updated = sdk_result["settings"]
            changed = sdk_result["changed"]
            result.update(self._result_payload(sdk_result["old_values"], requested, updated, changed))
            result["failed"] = False

            if self._task.diff:
                result["diff"] = {
                    "before": self._redact_settings(sdk_result["diff"]["before"]),
                    "after": self._redact_requested_settings(sdk_result["diff"]["after"]),
                }

            # Check mode displays the proposed values while settings still
            # contains the current server state. The SDK supplies both views.
            values = sdk_result["diff"]["after"] if self._task.check_mode and changed else {key: updated.get(key) for key in requested}
            if name is not None:
                result["value"] = self._redact_setting_value(name, values.get(name))
            else:
                result["values"] = self._redact_settings(values)

        except Exception as exc:
            self._display.vvv(f"Error in controller_settings action plugin: {exc}")
            result["failed"] = True
            result["msg"] = str(exc)

        return result
