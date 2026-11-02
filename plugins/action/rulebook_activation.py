#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.rulebook_activation module.

Rulebook activations support create, update, delete, enable, disable, and
restart operations. Create/update/delete go through manager.execute() for
request transformation and API access. For existing activations, the action
uses the API transform to compare requested update fields before dispatch,
so unchanged inputs skip the update in normal and check mode.
Enable/disable/restart are custom sub-actions with no create/update/delete
shape, so they use manager.direct_request() against their sub-endpoints,
the same pattern plugins/action/workflow_approval.py uses for approve/deny.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from dataclasses import asdict
from dataclasses import fields as dataclass_fields
from typing import Any, Dict, Optional

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.rulebook_activation import AnsibleRulebookActivation
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.rulebook_activation import (
    ACTIVATION_DISABLE_ENDPOINT,
    ACTIVATION_ENABLE_ENDPOINT,
    ACTIVATION_RESTART_ENDPOINT,
    RulebookActivationTransformMixin_v1,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.retry import RetryConfig

# Restart/enable/disable are non-idempotent POSTs: retrying a lost response
# could double-execute the action, so they disable the manager's default
# transient-failure retries.
_NO_RETRY = RetryConfig(max_attempts=1)

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
        manager.direct_request("POST", ACTIVATION_RESTART_ENDPOINT.format(id=existing["id"]), retry_config=_NO_RETRY)
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
            manager.direct_request("POST", endpoint.format(id=existing["id"]), retry_config=_NO_RETRY)
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

        This method translates the Ansible-level 'state' into the API's
        'is_enabled' field, decides create vs. update, and skips an update
        when the transformed API fields already match the existing activation.
        Creation-only references are omitted on update. AWX tokens and event
        streams remain supported update fields; event-stream mappings are
        resolved against the activation's current rulebook.

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
            ):
                ansible_data.pop(create_only_field, None)

            # These defaults are needed when creating an activation, but
            # applying them to every PATCH would overwrite values the caller
            # did not ask to change.
            for defaulted_field in ("restart_policy", "log_level", "enable_persistence", "restart_on_project_update"):
                if defaulted_field not in self._task.args:
                    ansible_data.pop(defaulted_field, None)

            if params.get("event_streams") is not None:
                # event_streams are converted to source_mappings by the
                # transform, which needs a rulebook ID even when the caller
                # only changes the stream mapping.
                rulebook_id = existing.get("rulebook_id")
                if rulebook_id is None:
                    raise AnsibleError("Cannot update event_streams because the existing activation has no rulebook ID")
                ansible_data["rulebook_id"] = rulebook_id

            if not self._activation_update_differs(manager, ansible_data, existing):
                result.update(
                    {
                        "changed": False,
                        "failed": False,
                        self.MODULE_NAME: existing,
                        "id": existing["id"],
                    }
                )
                return result

        if self._task.check_mode:
            result.update(
                {
                    "changed": True,
                    "failed": False,
                    self.MODULE_NAME: {"name": check_name},
                }
            )
            return result

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

    @staticmethod
    def _activation_update_differs(manager: Any, ansible_data: dict, existing: dict) -> bool:
        """Compare the requested API update fields with the existing activation.

        Transforming first makes references comparable as IDs and applies API
        field aliases such as ``extra_vars`` to ``extra_var``.
        """
        ansible_instance = AnsibleRulebookActivation(**ansible_data)
        api_data = RulebookActivationTransformMixin_v1.from_ansible_data(ansible_instance, {"manager": manager, "operation": "update"})
        desired = asdict(api_data)
        update_fields = RulebookActivationTransformMixin_v1.get_endpoint_operations()["update"].fields

        for field in update_fields:
            desired_value = desired.get(field)
            if desired_value is None:
                continue
            if ActionModule._normalize_for_update_comparison(desired_value) != ActionModule._normalize_for_update_comparison(existing.get(field)):
                return True
        return False

    @staticmethod
    def _normalize_for_update_comparison(value: Any) -> Any:
        """Normalize ID representations before comparing API and Ansible data."""
        if isinstance(value, dict):
            return {key: ActionModule._normalize_for_update_comparison(item) for key, item in value.items()}
        if isinstance(value, list):
            return [ActionModule._normalize_for_update_comparison(item) for item in value]
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return value
