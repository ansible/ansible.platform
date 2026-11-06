#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.notification_template import AnsibleNotificationTemplate
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.notification_template import BASE_PATH

_SERVICE = "controller"


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "notification_template"
    MODEL_CLASS = AnsibleNotificationTemplate
    LOOKUP_FIELD = "name"

    _WRITE_ONLY_FIELDS = frozenset({"copy_from"})
    _NO_LOG_FIELDS = frozenset({"notification_configuration"})

    def _resolve_lookup(self, resource, resource_data, validated_params):
        organization = getattr(resource, "organization", None)
        if organization is not None and str(organization).strip().isdigit():
            names = self._client.lookup_organization_names([int(organization)], service=_SERVICE)
            if names:
                resource.organization = names[0]
                resource_data["organization"] = names[0]

    @classmethod
    def _notification_values_could_match(cls, desired, current):
        """Compare notification configuration values with API normalization tolerance."""
        if desired == "$encrypted$":
            return True
        if current == "$encrypted$":
            return False
        if isinstance(desired, dict):
            if not isinstance(current, dict):
                return False
            return all(key in current and cls._notification_values_could_match(value, current[key]) for key, value in desired.items())
        if isinstance(desired, list):
            return (
                isinstance(current, list)
                and len(desired) == len(current)
                and all(cls._notification_values_could_match(expected, actual) for expected, actual in zip(desired, current))
            )
        return desired == current or str(desired) == str(current)

    def _should_update(self, desired_data, current_data):
        desired_configuration = desired_data.get("notification_configuration")
        desired_without_configuration = dict(desired_data)
        desired_without_configuration.pop("notification_configuration", None)

        if super()._should_update(desired_without_configuration, current_data):
            return True
        if desired_configuration is None:
            return False
        return not self._notification_values_could_match(desired_configuration, current_data.get("notification_configuration"))

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}

        copy_from = self._task.args.get("copy_from")
        name = self._task.args.get("name")
        organization = self._task.args.get("organization")
        state = self._task.args.get("state", "present")
        check_mode = self._task.check_mode

        copied = False
        if copy_from and state not in ("absent", "exists") and not check_mode:
            try:
                self._validate_action_input()
            except Exception as exc:
                return {"changed": False, "failed": True, "msg": str(exc)}
            try:
                super(BaseResourceActionPlugin, self).run(tmp, task_vars)
                self._task_vars = task_vars
                manager, facts_to_set = self._get_or_spawn_manager(task_vars)
                self._client = manager
                query_params = {"name": name}
                if organization is not None:
                    if str(organization).strip().isdigit():
                        query_params["organization"] = int(organization)
                    else:
                        query_params["organization"] = manager.lookup_resource_id("organizations", "name", organization, service=_SERVICE)
                existing = manager.search_api(BASE_PATH, query_params=query_params)
                if not any(item.get("name") == name for item in existing.get("results", [])):
                    if not str(copy_from).strip().isdigit():
                        source_params = {"name": copy_from}
                        if organization is not None:
                            source_params["organization"] = query_params.get("organization")
                        source_results = manager.search_api(BASE_PATH, query_params=source_params).get("results", [])
                        if len(source_results) == 1:
                            copy_from = str(source_results[0]["id"])
                        elif len(source_results) > 1:
                            raise ValueError("Multiple notification templates named '%s' found — specify organization to disambiguate" % copy_from)
                    manager.copy_resource(self.MODULE_NAME, copy_from, name, BASE_PATH, service=_SERVICE)
                    copied = True
            except Exception as exc:
                return {"changed": False, "failed": True, "msg": "Failed to copy from '%s': %s" % (copy_from, exc)}

        result = super().run(tmp, task_vars)
        if copied:
            result["changed"] = True
        return result
