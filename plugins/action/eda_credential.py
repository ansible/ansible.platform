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

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.eda_credential import AnsibleEdaCredential
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.eda_credential import BASE_PATH


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for eda_credential module."""

    MODULE_NAME = "eda_credential"
    MODEL_CLASS = AnsibleEdaCredential
    LOOKUP_FIELD = "name"

    _WRITE_ONLY_FIELDS = frozenset({"inputs"})
    _NO_LOG_FIELDS = frozenset({"inputs"})

    def run(self, tmp=None, task_vars=None):
        """Run the eda_credential action plugin.

        Args:
            tmp: Temporary directory (deprecated, unused).
            task_vars: Task variables from Ansible.

        Returns:
            dict: Ansible result dictionary.
        """
        if task_vars is None:
            task_vars = {}

        copy_from = self._task.args.pop("copy_from", None)
        metadata = self._task.args.pop("metadata", None)
        name = self._task.args.get("name")
        state = self._task.args.get("state", "present")
        check_mode = self._task.check_mode

        # Handle state=test — custom path, not part of base class CRUD
        if state == "test":
            return self._handle_test(tmp, task_vars, name, metadata, check_mode)

        # Handle copy_from — copy credential before CRUD (like controller_credential)
        copied = False
        if copy_from and state not in ("absent", "exists") and not check_mode:
            try:
                super(BaseResourceActionPlugin, self).run(tmp, task_vars)
                self._task_vars = task_vars
                manager, facts_to_set = self._get_or_spawn_manager(task_vars)
                self._client = manager
                existing = manager.search_api(BASE_PATH, query_params={"name": name}, service="eda")
                if not any(item.get("name") == name for item in existing.get("results", [])):
                    manager.copy_resource(self.MODULE_NAME, copy_from, name, BASE_PATH, service="eda")
                    copied = True
            except Exception as exc:
                return {"changed": False, "failed": True, "msg": "Failed to copy from '%s': %s" % (copy_from, exc)}

        result = super().run(tmp, task_vars)
        if copied:
            result["changed"] = True
        return result

    def _pre_execute_hook(self, ansible_data, write_only_data, validated_params, operation):
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

    def _handle_test(self, tmp, task_vars, name, metadata, check_mode):
        """Handle state=test: test credential connectivity.

        Args:
            tmp: Temporary directory (deprecated, unused).
            task_vars: Task variables from Ansible.
            name: Credential name to test.
            metadata: Optional metadata dict for the test request.
            check_mode: Whether check mode is enabled.

        Returns:
            dict: Ansible result dictionary with test_result.
        """
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        try:
            self._task_vars = task_vars
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                from ansible.errors import AnsibleError

                raise AnsibleError("Could not load DOCUMENTATION for %s module" % self.MODULE_NAME)

            module_args = self._task.args.copy()
            self._validate_data(module_args, argspec, "input")
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            # Find credential by name
            existing = None
            try:
                find_result = manager.execute(
                    operation="find",
                    module_name=self.MODULE_NAME,
                    ansible_data={"name": name},
                )
                if find_result and find_result.get("id"):
                    existing = find_result
            except ValueError as e:
                if "not found" not in str(e).lower() and "404" not in str(e):
                    raise

            if not existing:
                result["failed"] = True
                result["msg"] = "Credential '%s' not found" % name
                return result

            if check_mode:
                test_result = {
                    "success": True,
                    "message": "Check mode - test would be performed",
                    "details": {"check_mode": True},
                }
                result.update({"changed": False, "failed": False, "test_result": test_result})
                return result

            # POST to credential test endpoint
            test_data = {"metadata": metadata} if metadata else {}
            credential_id = existing["id"]
            test_response = manager.direct_request(
                "POST",
                "/api/eda/v1/eda-credentials/%s/test/" % credential_id,
                data=test_data,
            )

            # Parse test response
            if isinstance(test_response, dict):
                test_result = test_response
            else:
                test_result = {"success": True, "message": "Credential test accepted"}

            result.update({"changed": False, "failed": False, "test_result": test_result})

        except Exception as e:
            import traceback

            self._display.vvv("Error in %s action plugin (test): %s" % (self.MODULE_NAME, e))
            result["failed"] = True
            result["msg"] = str(e)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result
