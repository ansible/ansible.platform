#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.eda_credential module.

Supports standard CRUD (present/absent), credential connectivity testing
(state=test), copying existing credentials (copy_from), and renaming
(new_name).  Credential inputs are write-only and excluded from idempotency
comparison.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import traceback
from typing import Any, Optional

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.eda_credential import AnsibleEdaCredential
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.eda_credential import (
    BASE_PATH,
    EdaCredentialTransformMixin_v1,
    resolve_eda_credential_fk,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import build_endpoint_request


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for eda_credential module."""

    MODULE_NAME = "eda_credential"
    MODEL_CLASS = AnsibleEdaCredential
    LOOKUP_FIELD = "name"

    _ANSIBLE_DIRECTIVES = BaseResourceActionPlugin._ANSIBLE_DIRECTIVES | frozenset({"copy_from", "metadata", "update_secrets"})
    _WRITE_ONLY_FIELDS = frozenset({"inputs"})
    _NO_LOG_FIELDS = frozenset({"inputs"})

    def _prepare_action(self, tmp: Optional[object] = None, task_vars: Optional[dict] = None) -> dict:
        """Prepare validated input and retain intent for write-only fields.

        Args:
            tmp: Temporary directory passed through to the base helper.
            task_vars: Ansible variables used to initialize the manager.

        Returns:
            dict: Prepared action data returned by the base helper.
        """
        prepared = super()._prepare_action(tmp, task_vars)
        params = prepared["validated_params"]
        for alias in ("credential_type_name", "organization_name"):
            params.pop(alias, None)
            prepared["resource_data"].pop(alias, None)
        self._inputs_provided = params.get("inputs") is not None
        self._update_secrets = params.get("update_secrets", False)
        return prepared

    def _lookup_credential_id(self, manager: Any, name: str, organization: Optional[str] = None) -> Optional[int]:
        """Resolve a credential name uniquely within its organization when supplied.

        Args:
            manager: Platform client used for lookups.
            name: Credential name or ID.
            organization: Optional organization name or ID.
        Returns:
            Optional[int]: Credential ID, or ``None`` when it does not exist.

        Raises:
            ValueError: If a reference is invalid or ambiguous.
        """
        extra_query_params = {}
        if organization is not None:
            organization_id = resolve_eda_credential_fk(manager, "organizations", organization, "Organization")
            if organization_id is not None:
                extra_query_params["organization"] = organization_id

        try:
            return manager.lookup_resource_id(
                "eda-credentials",
                "name",
                name,
                service="eda",
                extra_query_params=extra_query_params,
                require_unique=True,
            )
        except ValueError as exc:
            # A missing destination is expected while copying or creating. Ambiguous
            # results and invalid organization references must still fail loudly.
            message = str(exc).lower()
            if "eda-credentials" in message and "not found" in message:
                return None
            raise

    def _resolve_lookup(self, resource: Any, resource_data: dict, validated_params: dict) -> None:
        """Preflight name lookups so ambiguity cannot target an arbitrary record.

        Args:
            resource: Constructed Ansible credential model.
            resource_data: Validated resource fields, updated with a resolved ID.
            validated_params: Full validated action arguments.

        Returns:
            None: This method updates the resource and resource data in place.
        """
        name = resource_data.get(self.LOOKUP_FIELD)
        if name is None or str(name).strip().isdigit():
            return

        resource_id = self._lookup_credential_id(self._client, name, validated_params.get("organization"))
        if resource_id is not None:
            resource.id = resource_id
            resource_data["id"] = resource_id

    def _should_update(self, desired_data: dict, current_data: dict) -> bool:
        """Compare references by ID and honor explicit updates to write-only inputs.

        Args:
            desired_data: Validated writable fields supplied by the task.
            current_data: Current credential data returned by the API.

        Returns:
            bool: Whether the credential should be updated.
        """
        normalized = dict(desired_data)
        for field, endpoint, label in (
            ("credential_type", "credential-types", "Credential type"),
            ("organization", "organizations", "Organization"),
        ):
            value = normalized.get(field)
            if value is not None:
                resource_id = resolve_eda_credential_fk(self._client, endpoint, value, label)
                normalized[field] = str(resource_id) if resource_id is not None else None

        if super()._should_update(normalized, current_data):
            return True
        return (getattr(self, "_update_secrets", False) or getattr(self, "_copied_credential", False)) and getattr(self, "_inputs_provided", False)

    def run(self, tmp: Optional[object] = None, task_vars: Optional[dict] = None) -> dict:
        """Run the eda_credential action plugin.

        Args:
            tmp: Temporary directory (deprecated, unused).
            task_vars: Task variables from Ansible.

        Returns:
            dict: Ansible result dictionary.
        """
        if task_vars is None:
            task_vars = {}

        state = self._task.args.get("state", "present")
        check_mode = self._task.check_mode
        self._copied_credential = False

        # Handle state=test — custom path, not part of base class CRUD
        if state == "test":
            return self._handle_test(tmp, task_vars)

        # Handle copy_from — copy credential before CRUD (like controller_credential)
        copy_from = self._task.args.get("copy_from")
        if copy_from and state not in ("absent", "exists") and not check_mode:
            try:
                prepared = self._prepare_action(tmp, task_vars)
                params = prepared["validated_params"]
                manager = prepared["manager"]
                name = params["name"]
                destination_id = self._lookup_credential_id(manager, name, params.get("organization"))
                if destination_id is None:
                    source_id = self._lookup_credential_id(manager, copy_from)
                    if source_id is None:
                        raise ValueError("Credential '%s' to copy from was not found" % copy_from)
                    manager.copy_resource(self.MODULE_NAME, source_id, name, BASE_PATH, service="eda")
                    self._copied_credential = True
            except Exception as exc:
                return {"changed": False, "failed": True, "msg": "Failed to copy from '%s': %s" % (copy_from, exc)}

        result = super().run(tmp, task_vars)
        if self._copied_credential:
            result["changed"] = True
        return result

    def _pre_execute_hook(self, ansible_data: dict, write_only_data: dict, validated_params: dict, operation: str) -> None:
        """Add write-only inputs back to ansible_data for create/update.

        Args:
            ansible_data: The dict about to be sent to manager.execute().
            write_only_data: Fields popped from resource_data (inputs).
            validated_params: Full validated input parameters.
            operation: The resolved operation string.
        """
        inputs = write_only_data.get("inputs")
        if inputs is not None and operation in ("create", "update"):
            ansible_data["inputs"] = inputs

    def _handle_test(self, tmp: Optional[object], task_vars: dict) -> dict:
        """Handle state=test: test credential connectivity.

        Args:
            tmp: Temporary directory passed through to the shared preparation helper.
            task_vars: Ansible variables used to initialize the manager.

        Returns:
            dict: Ansible result dictionary with test_result.
        """
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            params = prepared["validated_params"]
            manager = prepared["manager"]
            name = params["name"]
            credential_id = self._lookup_credential_id(manager, name, params.get("organization"))

            if credential_id is None:
                result["failed"] = True
                result["msg"] = "Credential '%s' not found" % name
                return result

            if self._task.check_mode:
                test_result = {
                    "success": True,
                    "message": "Check mode - test would be performed",
                    "details": {"check_mode": True},
                }
                result.update({"changed": False, "failed": False, "test_result": test_result})
                return result

            # POST to credential test endpoint
            metadata = params.get("metadata")
            test_request = EdaCredentialTransformMixin_v1.to_test_request(credential_id, metadata if metadata else None)
            test_operation = EdaCredentialTransformMixin_v1.get_endpoint_operations()["test"]
            test_path, test_data = build_endpoint_request(test_operation, test_request)
            test_response = manager.direct_request(
                test_operation.method,
                test_path,
                data=test_data,
            )

            # Parse test response
            if isinstance(test_response, dict) and test_response:
                test_result = test_response
            else:
                test_result = {"success": True, "message": "Credential test accepted"}

            result.update({"changed": False, "failed": False, "test_result": test_result})

        except Exception as e:
            self._display.vvv("Error in %s action plugin (test): %s" % (self.MODULE_NAME, e))
            result["failed"] = True
            result["msg"] = str(e)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result
