#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.schedule import AnsibleSchedule
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.schedule import BASE_PATH
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import ResourceNotFoundError

_ASSOC_MAP = {
    "credentials": ("credentials", "name"),
    "labels": ("labels", "name"),
    "instance_groups": ("instance_groups", "name"),
}

_SERVICE = "controller"


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "schedule"
    MODEL_CLASS = AnsibleSchedule
    LOOKUP_FIELD = "name"

    _WRITE_ONLY_FIELDS = frozenset(_ASSOC_MAP)
    _NULLABLE_FK_FIELDS = frozenset({"inventory", "execution_environment"})

    def _should_update(self, desired_data, current_data):
        """Compare schedule fields, excluding organization used only to scope template lookup."""
        desired_data = {key: value for key, value in desired_data.items() if key != "organization"}
        return super()._should_update(desired_data, current_data)

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}

        association_data = {field: self._task.args.get(field) for field in _ASSOC_MAP}

        result = super().run(tmp, task_vars)

        state = self._task.args.get("state", "present")
        if result.get("failed") or state in ("absent", "exists"):
            return result

        sched_id = result.get("id") or (result.get(self.MODULE_NAME) or {}).get("id")
        if not sched_id:
            return result

        try:
            manager = self._client
            changed = False
            for field, (lookup_endpoint, lookup_field) in _ASSOC_MAP.items():
                desired = association_data.get(field)
                if desired is None:
                    continue
                try:
                    if manager.manage_associations(
                        BASE_PATH, sched_id, field, desired, lookup_endpoint, lookup_field, service=_SERVICE, check_mode=self._task.check_mode
                    ):
                        changed = True
                except ResourceNotFoundError as exc:
                    missing_association = (exc.endpoint, exc.lookup_field, exc.service) == (lookup_endpoint, lookup_field, _SERVICE)
                    missing_credential_organization = (
                        field == "credentials"
                        and (exc.endpoint, exc.lookup_field, exc.service) == ("organizations", "name", _SERVICE)
                        and any(
                            isinstance(value, str)
                            and value.count("++") == 1
                            and all(part.strip() for part in value.split("++"))
                            and str(exc.lookup_value) == value.partition("++")[2].strip()
                            for value in desired
                        )
                    )
                    if self._task.check_mode and (missing_association or missing_credential_organization):
                        changed = True
                    else:
                        raise
        except Exception as exc:
            result["failed"] = True
            result["msg"] = "Failed to reconcile associations: %s" % exc
            return result

        if changed:
            result["changed"] = True
        return result
