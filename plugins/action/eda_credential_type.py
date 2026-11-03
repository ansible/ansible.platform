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

from typing import Optional

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
