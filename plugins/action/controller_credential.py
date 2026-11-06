#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_credential import (
    AnsibleControllerCredential,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.controller_credential import BASE_PATH

_SERVICE = "controller"


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "controller_credential"
    MODEL_CLASS = AnsibleControllerCredential
    LOOKUP_FIELD = "name"

    _WRITE_ONLY_FIELDS = frozenset({"copy_from", "inputs"})
    # update_secrets controls whether write-only credential inputs are sent on
    # update; it is not an API field and must not participate in idempotency.
    _ANSIBLE_DIRECTIVES = BaseResourceActionPlugin._ANSIBLE_DIRECTIVES | frozenset({"update_secrets"})
    _MUTUALLY_EXCLUSIVE = [["organization", "user"], ["organization", "team"], ["user", "team"]]

    def _resolve_relationship_ids(self, desired_data):
        """Resolve named credential relationships using the platform manager."""
        manager = getattr(self, "_client", None)
        if manager is None:
            return

        def resolve(field, endpoint, lookup_field="name", extra_query_params=None):
            value = desired_data.get(field)
            if value is None or str(value).isdigit():
                return
            kwargs = {"service": _SERVICE}
            if extra_query_params:
                kwargs["extra_query_params"] = extra_query_params
            desired_data[field] = manager.lookup_resource_id(endpoint, lookup_field, str(value), **kwargs)

        resolve("credential_type", "credential_types")
        resolve("organization", "organizations")
        organization_id = desired_data.get("organization")
        team_scope = {"organization": organization_id} if organization_id is not None else None
        resolve("user", "users", lookup_field="username")
        resolve("team", "teams", extra_query_params=team_scope)

    def _should_update(self, desired_data, current_data):
        """Determine whether non-secret credential fields require an update."""
        raw_update_secrets = self._task.args.get("update_secrets", True)
        update_secrets = raw_update_secrets if isinstance(raw_update_secrets, bool) else str(raw_update_secrets).lower() not in ("false", "no", "0")
        desired_data = dict(desired_data)
        self._resolve_relationship_ids(desired_data)
        if update_secrets and self._task.args.get("inputs") is not None:
            # Legacy behavior: update encrypted values on every update when
            # update_secrets is true and inputs were supplied.
            return True
        return super()._should_update(desired_data, current_data)

    def _pre_execute_hook(self, ansible_data, write_only_data, validated_params, operation):
        """Send credential inputs only when the operation requires them."""
        inputs = write_only_data.get("inputs")
        if inputs is None:
            return
        raw_update_secrets = validated_params.get("update_secrets", True)
        update_secrets = raw_update_secrets if isinstance(raw_update_secrets, bool) else str(raw_update_secrets).lower() not in ("false", "no", "0")
        if operation == "create" or update_secrets:
            ansible_data["inputs"] = inputs

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}

        copy_from = self._task.args.pop("copy_from", None)
        name = self._task.args.get("name")
        state = self._task.args.get("state", "present")
        check_mode = self._task.check_mode

        copied = False
        if copy_from and state not in ("absent", "exists") and not check_mode:
            try:
                super(BaseResourceActionPlugin, self).run(tmp, task_vars)
                self._task_vars = task_vars
                manager, facts_to_set = self._get_or_spawn_manager(task_vars)
                self._client = manager
                existing = manager.search_api(BASE_PATH, query_params={"name": name})
                if not any(item.get("name") == name for item in existing.get("results", [])):
                    manager.copy_resource(self.MODULE_NAME, copy_from, name, BASE_PATH, service=_SERVICE)
                    copied = True
            except Exception as exc:
                return {"changed": False, "failed": True, "msg": "Failed to copy from '%s': %s" % (copy_from, exc)}

        result = super().run(tmp, task_vars)
        if copied:
            result["changed"] = True
        return result
