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
    def _coerce_type(value):
        """Convert legacy string values to common Controller setting types."""
        if value is None or not isinstance(value, str):
            return value

        if (value.startswith("{") and value.endswith("}")) or (value.startswith("[") and value.endswith("]")):
            try:
                return yaml.safe_load(value)
            except yaml.YAMLError as exc:
                mark = getattr(exc, "problem_mark", None)
                if mark is not None:
                    error_message = "Unable to parse setting value as YAML at line %d, column %d" % (mark.line + 1, mark.column + 1)
                else:
                    error_message = "Unable to parse setting value as YAML"

            # Raise outside the except block so the parser exception is not
            # retained as an exception context or exposed in the task result.
            raise ValueError(error_message)

        if value.lower() in ("true", "false", "t", "f"):
            return value.lower() in ("true", "t")

        try:
            return int(value)
        except ValueError:
            return value

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
            requested_settings = validated_params.get("settings")
            has_name = name is not None
            has_settings = requested_settings is not None
            if has_name == has_settings:
                raise ValueError("Exactly one of 'name' or 'settings' must be provided")
            if has_name and validated_params.get("value") is None:
                raise ValueError("value is required when name is provided")
            if has_name:
                requested_settings = {name: self._coerce_type(validated_params.get("value"))}
            else:
                requested_settings = dict(requested_settings)

            current_result = manager.execute(
                operation="find",
                module_name=self.MODULE_NAME,
                ansible_data=asdict(AnsibleControllerSettings(settings={})),
            )
            current_settings = current_result.get("settings", {}) or {}
            unknown_settings = sorted(set(requested_settings) - set(current_settings))
            if unknown_settings:
                raise ValueError("Unknown Controller setting(s): %s" % ", ".join(unknown_settings))
            to_update = {key: value for key, value in requested_settings.items() if current_settings[key] != value}

            if self._task.diff:
                result["diff"] = {
                    "before": self._redact_settings({key: current_settings.get(key) for key in to_update}),
                    "after": self._redact_requested_settings(to_update),
                }

            if not to_update:
                result.update(self._result_payload(current_settings, requested_settings, current_settings, False))
                result["failed"] = False
                if name is not None:
                    result["value"] = self._redact_setting_value(name, current_settings.get(name))
                else:
                    result["values"] = self._redact_settings({key: current_settings.get(key) for key in requested_settings})
                return result

            if self._task.check_mode:
                result.update(self._result_payload(current_settings, requested_settings, current_settings, True))
                result["failed"] = False
                if name is not None:
                    result["value"] = self._redact_setting_value(name, to_update.get(name))
                else:
                    result["values"] = self._redact_requested_settings(to_update)
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
                result["value"] = self._redact_setting_value(name, updated_settings.get(name))
            else:
                result["values"] = self._redact_settings({key: updated_settings.get(key) for key in requested_settings})

        except Exception as exc:
            self._display.vvv(f"Error in controller_settings action plugin: {exc}")
            result["failed"] = True
            result["msg"] = str(exc)

        return result
