#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.eda_credential_type module.

Standard CRUD via the base class for state=present/absent.
Custom handling for state=test which POSTs to the credential-types/{id}/test/
sub-endpoint to validate credential type configuration.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from typing import Any, Optional

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.eda_credential_type import AnsibleEdaCredentialType
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.eda_credential_type import EDA_CREDENTIAL_TYPE_TEST_ENDPOINT


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for eda_credential_type module."""

    MODULE_NAME = "eda_credential_type"
    MODEL_CLASS = AnsibleEdaCredentialType
    # test_inputs and test_metadata are only used with state=test and must
    # be stripped before the base class builds MODEL_CLASS for CRUD states.
    _WRITE_ONLY_FIELDS = frozenset({"test_inputs", "test_metadata"})
    _NO_LOG_FIELDS = frozenset({"test_inputs"})
    _RENAME_IDENTITY_FIELDS = ("inputs", "injectors")

    def _find_existing_resource(self, manager: Any, resource_data: dict) -> dict:
        """Find credential types by name and recognize verified completed renames.

        Args:
            manager: Client used to query the EDA API.
            resource_data: Validated credential type fields.

        Returns:
            dict: The matching credential type, including a verified rename target.
        """
        try:
            existing = super()._find_existing_resource(manager, resource_data)
        except Exception as exc:
            new_name = resource_data.get("new_name")
            if not new_name or resource_data.get("state") in ("absent", "exists") or not self._is_resource_not_found(exc):
                raise

            renamed_data = dict(resource_data)
            renamed_data["name"] = new_name
            renamed_data.pop("new_name", None)
            try:
                rename_target = super()._find_existing_resource(manager, renamed_data)
            except Exception as target_exc:
                if self._is_resource_not_found(target_exc):
                    raise exc
                raise

            identity_is_supplied = all(field in resource_data for field in self._RENAME_IDENTITY_FIELDS)
            identity_is_returned = all(field in rename_target for field in self._RENAME_IDENTITY_FIELDS)
            requested_fields = set(resource_data) - {"name", "new_name", "state"}
            requested_fields_are_returned = requested_fields.issubset(rename_target)
            if not identity_is_supplied or not identity_is_returned or not requested_fields_are_returned:
                message = (
                    "Cannot verify credential type rename from '%s' to '%s': inputs, injectors, and requested fields "
                    "must be available to verify the existing target" % (resource_data.get("name"), new_name)
                )
                raise ValueError(message) from exc

            if self._should_update(resource_data, rename_target):
                raise ValueError(
                    "Cannot verify credential type rename from '%s' to '%s': the target does not match the requested state"
                    % (resource_data.get("name"), new_name)
                ) from exc
            return rename_target

        new_name = resource_data.get("new_name")
        if not new_name or new_name == resource_data.get("name") or resource_data.get("state") == "absent":
            return existing

        renamed_data = dict(resource_data)
        renamed_data["name"] = new_name
        renamed_data.pop("new_name", None)
        try:
            rename_target = super()._find_existing_resource(manager, renamed_data)
        except Exception as exc:
            if self._is_resource_not_found(exc):
                return existing
            raise

        existing_id = existing.get("id")
        target_id = rename_target.get("id")
        if existing_id is None or target_id is None or str(existing_id) != str(target_id):
            raise ValueError("Cannot rename credential type '%s': credential type '%s' already exists" % (resource_data.get("name"), new_name))

        return existing

    def _should_update(self, desired_data: dict, current_data: dict) -> bool:
        """Compare a rename target against the desired credential type state.

        Args:
            desired_data: Requested credential type fields.
            current_data: Credential type returned by the API.

        Returns:
            bool: True when the resource needs an update.
        """
        desired = dict(desired_data)
        new_name = desired.get("new_name")
        if new_name:
            if current_data.get("name") != new_name:
                return True
            desired["name"] = new_name
            desired.pop("new_name", None)
        return super()._should_update(desired, current_data)

    def run(self, tmp: object = None, task_vars: Optional[dict] = None) -> dict:
        """Route to test handler or delegate to base class for CRUD.

        Args:
            tmp: Temporary directory (deprecated, unused).
            task_vars: Task variables from Ansible.

        Returns:
            dict: Ansible result dictionary.
        """
        if task_vars is None:
            task_vars = dict()

        state = self._task.args.get("state", "present")

        if state == "test":
            return self._run_test(tmp, task_vars)

        return super().run(tmp, task_vars)

    def _run_test(self, tmp: object, task_vars: dict) -> dict:
        """Handle state=test: validate credential type via the test sub-endpoint.

        Finds the credential type by name, then POSTs test_inputs and
        test_metadata to /api/eda/v1/credential-types/{id}/test/ using the
        SDK launch_resource method.
        Always returns changed=False (read-like operation).

        Args:
            tmp: Temporary directory (deprecated, unused).
            task_vars: Task variables from Ansible.

        Returns:
            dict: Ansible result dictionary with test_result.
        """
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            write_only_data = prepared["write_only_data"]
            manager = prepared["manager"]

            name = validated_params.get("name")
            test_inputs = write_only_data.get("test_inputs")
            test_metadata = write_only_data.get("test_metadata")
            if not test_inputs:
                raise AnsibleError("test_inputs must be provided and non-empty when state=test")

            # Find the credential type by name
            try:
                find_result = manager.execute(
                    operation="find",
                    module_name=self.MODULE_NAME,
                    ansible_data={"name": name},
                )
            except (ValueError, Exception) as e:
                if "not found" in str(e).lower() or "404" in str(e):
                    raise AnsibleError("Credential type '%s' not found, cannot test" % name) from e
                raise

            if not find_result or not find_result.get("id"):
                raise AnsibleError("Credential type '%s' not found, cannot test" % name)

            credential_type_id = find_result["id"]

            if self._task.check_mode:
                result.update(
                    {
                        "changed": False,
                        "failed": False,
                        self.MODULE_NAME: find_result,
                        "test_result": {"msg": "check mode, test not executed"},
                    }
                )
                return result

            # Build test payload matching EDA API format
            test_payload = {}
            if test_inputs:
                test_payload["inputs"] = test_inputs
            if test_metadata:
                test_payload["metadata"] = test_metadata

            # POST to the test sub-endpoint via the SDK launch_resource method
            test_url = EDA_CREDENTIAL_TYPE_TEST_ENDPOINT.format(id=credential_type_id)
            test_response = manager.launch_resource(
                launch_url=test_url,
                payload=test_payload,
                service="eda",
                retry=False,
            )

            test_result = (
                test_response
                if test_response
                else {
                    "success": True,
                    "message": "Credential type test accepted",
                }
            )

            result.update(
                {
                    "changed": False,
                    "failed": False,
                    self.MODULE_NAME: find_result,
                    "test_result": test_result,
                }
            )

        except Exception as e:
            import traceback

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, e))
            result["failed"] = True
            result["msg"] = str(e)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result
