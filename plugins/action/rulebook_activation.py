#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.rulebook_activation module.

Rulebook activations support create, update, delete, enable, disable, and
restart operations.  Create/update/delete go through manager.execute() so
FK resolution (project, rulebook, decision environment, organization, AWX
token, EDA credentials, event streams) and update idempotency diffing both
live in RulebookActivationTransformMixin_v1 / PlatformService, exactly like
every other full-CRUD resource (see plugins/action/eda_controller_token.py).
Enable/disable/restart are custom sub-actions with no create/update/delete
shape, so they use manager.direct_request() against their sub-endpoints,
the same pattern plugins/action/workflow_approval.py uses for approve/deny.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import fields as dataclass_fields
from typing import Any, Dict, Optional

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.rulebook_activation import AnsibleRulebookActivation
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.rulebook_activation import (
    ACTIVATION_DISABLE_ENDPOINT,
    ACTIVATION_ENABLE_ENDPOINT,
    ACTIVATION_RESTART_ENDPOINT,
)

_ANSIBLE_MODEL_FIELDS = frozenset(f.name for f in dataclass_fields(AnsibleRulebookActivation))


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for rulebook_activation module."""

    MODULE_NAME = "rulebook_activation"
    MODEL_CLASS = AnsibleRulebookActivation

    def run(self, tmp: object = None, task_vars: Optional[Dict[str, Any]] = None) -> dict:
        """Execute rulebook activation management.

        Handles the full lifecycle: create, update, delete, enable,
        disable, and restart operations.

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
            new_name = params.get("new_name")
            state = params.get("state", "present")
            restart = params.get("restart", False)

            if restart:
                return self._handle_restart(manager, name, result)

            existing = self._find_activation(manager, name)

            if state == "absent":
                return self._handle_absent(manager, name, existing, result)

            if state in ("enabled", "disabled") and existing:
                return self._handle_state_transition(manager, state, existing, result)

            return self._handle_create_or_update(manager, params, state, name, new_name, existing, result)

        except Exception as e:
            import traceback

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, e))
            result["failed"] = True
            result["msg"] = str(e)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result

    def _find_activation(self, manager: Any, name: Optional[str]) -> Optional[dict]:
        """Find an existing activation by name.

        Args:
            manager: The platform manager client.
            name: Name of the activation to find.

        Returns:
            Optional[dict]: The activation data if found, None otherwise.
        """
        try:
            find_result = manager.execute(
                operation="find",
                module_name=self.MODULE_NAME,
                ansible_data={"name": name},
            )
            if find_result and find_result.get("id"):
                return find_result
        except ValueError as e:
            if "not found" not in str(e).lower() and "404" not in str(e):
                raise
        return None

    def _handle_restart(self, manager: Any, name: Optional[str], result: dict) -> dict:
        """Handle restart operation.

        Args:
            manager: The platform manager client.
            name: Activation name.
            result: Result dict to update.

        Returns:
            dict: Updated result.
        """
        existing = self._find_activation(manager, name)
        if not existing:
            raise AnsibleError("Cannot restart activation that does not exist: %s" % name)
        if self._task.check_mode:
            result.update({"changed": True, "failed": False, self.MODULE_NAME: existing})
            return result
        manager.direct_request("POST", ACTIVATION_RESTART_ENDPOINT.format(id=existing["id"]))
        result.update(
            {
                "changed": True,
                "failed": False,
                self.MODULE_NAME: existing,
                "id": existing["id"],
            }
        )
        return result

    def _handle_absent(self, manager: Any, name: Optional[str], existing: Optional[dict], result: dict) -> dict:
        """Handle state=absent (delete) via the generic delete operation.

        Args:
            manager: The platform manager client.
            name: Activation name.
            existing: Existing activation data or None.
            result: Result dict to update.

        Returns:
            dict: Updated result.
        """
        if not existing:
            result.update(
                {
                    "changed": False,
                    "failed": False,
                    self.MODULE_NAME: {"state": "absent"},
                    "msg": "%s '%s' does not exist (already absent)" % (self.MODULE_NAME, name),
                }
            )
            return result
        if self._task.check_mode:
            result.update(
                {
                    "changed": True,
                    "failed": False,
                    self.MODULE_NAME: {"state": "absent", "id": existing["id"]},
                }
            )
            return result
        manager.execute(
            operation="delete",
            module_name=self.MODULE_NAME,
            ansible_data={"id": existing["id"], "name": name},
        )
        result.update(
            {
                "changed": True,
                "failed": False,
                self.MODULE_NAME: {"state": "absent", "id": existing["id"]},
            }
        )
        return result

    def _handle_state_transition(self, manager: Any, state: str, existing: dict, result: dict) -> dict:
        """Handle enable/disable state transition on existing activation.

        These are custom sub-actions (POST .../enable/ or .../disable/) with
        no create/update shape, so they call the API directly the same way
        plugins/action/workflow_approval.py handles approve/deny.

        Args:
            manager: The platform manager client.
            state: Desired state ('enabled' or 'disabled').
            existing: Existing activation data.
            result: Result dict to update.

        Returns:
            dict: Updated result.
        """
        is_enabled = existing.get("is_enabled", False)
        need_enable = state == "enabled" and not is_enabled
        need_disable = state == "disabled" and is_enabled

        if need_enable or need_disable:
            if self._task.check_mode:
                result.update({"changed": True, "failed": False, self.MODULE_NAME: existing})
                return result
            endpoint = ACTIVATION_ENABLE_ENDPOINT if need_enable else ACTIVATION_DISABLE_ENDPOINT
            manager.direct_request("POST", endpoint.format(id=existing["id"]))
            result.update(
                {
                    "changed": True,
                    "failed": False,
                    self.MODULE_NAME: existing,
                    "id": existing["id"],
                }
            )
            return result

        result.update(
            {
                "changed": False,
                "failed": False,
                self.MODULE_NAME: existing,
                "id": existing["id"],
            }
        )
        return result

    def _handle_create_or_update(
        self,
        manager: Any,
        params: dict,
        state: str,
        name: Optional[str],
        new_name: Optional[str],
        existing: Optional[dict],
        result: dict,
    ) -> dict:
        """Create or update an activation via manager.execute().

        FK resolution and update idempotency diffing both live in the
        transform mixin / PlatformService._update_resource; this method
        translates the Ansible-level 'state' into the API's 'is_enabled'
        field and decides create vs. update. 'restart', and on update only
        the create-only reference fields (project_name, rulebook_name,
        decision_environment_name, organization_name, awx_token_name,
        event_streams), are stripped from ansible_data first: the API never
        echoes them back, so leaving them in makes the idempotency diff see
        them as missing on the server and always report changed=True.

        Args:
            manager: The platform manager client.
            params: Validated module parameters.
            state: Desired state.
            name: Current activation name.
            new_name: New name for rename (or None).
            existing: Existing activation data or None.
            result: Result dict to update.

        Returns:
            dict: Updated result.
        """
        check_name = new_name if new_name else name

        if self._task.check_mode:
            result.update(
                {
                    "changed": True,
                    "failed": False,
                    self.MODULE_NAME: {"name": check_name},
                }
            )
            return result

        # validated_params also carries auth options (gateway_hostname, ...)
        # that must never reach AnsibleRulebookActivation(**ansible_data).
        ansible_data = {k: v for k, v in params.items() if k in _ANSIBLE_MODEL_FIELDS}
        ansible_data["is_enabled"] = state != "disabled"
        ansible_data.pop("restart", None)

        operation = "create"
        if existing:
            ansible_data["id"] = existing["id"]
            operation = "update"
            for create_only_field in (
                "project_name",
                "rulebook_name",
                "decision_environment_name",
                "organization_name",
                "awx_token_name",
                "event_streams",
            ):
                ansible_data.pop(create_only_field, None)

        api_result = manager.execute(
            operation=operation,
            module_name=self.MODULE_NAME,
            ansible_data=ansible_data,
        )

        changed = api_result.pop("changed", True)
        result.update(
            {
                "changed": changed,
                "failed": False,
                self.MODULE_NAME: api_result,
                "id": api_result.get("id"),
            }
        )
        return result
