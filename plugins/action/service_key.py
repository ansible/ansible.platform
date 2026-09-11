#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
from dataclasses import asdict

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.service_key import AnsibleServiceKey


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "service_key"
    MODEL_CLASS = AnsibleServiceKey
    # mark_previous_inactive: operation-time directive; API never returns it.
    # secret: write-only; API returns null/hash, not the original value.
    _WRITE_ONLY_FIELDS = frozenset({"mark_previous_inactive", "secret"})
    _CREATE_ONLY_FIELDS = frozenset({"algorithm", "mark_previous_inactive", "secret", "secret_length", "service_cluster"})

    def run(self, tmp=None, task_vars=None):
        """Emit a deprecation warning when create-only fields are supplied."""
        supplied_fields = sorted(field for field in self._CREATE_ONLY_FIELDS if self._task.args.get(field) is not None)
        result = super().run(tmp, task_vars)
        if supplied_fields:
            result.setdefault("deprecations", []).append(
                {
                    "msg": "The service_key parameters %s are deprecated; newer AAP versions ignore them for existing service keys."
                    % ", ".join(supplied_fields),
                    "version": "4.0.0",
                    "collection_name": "ansible.platform",
                }
            )
        return result

    def _pre_execute_hook(self, ansible_data, write_only_data, validated_params, operation):
        """Re-inject write-only fields so they reach the API payload.

        Older AAP versions accept all fields on update. Newer versions
        advertise no POST action and only allow name/is_active changes.
        """
        if operation in ("create", "update"):
            for field in self._WRITE_ONLY_FIELDS:
                val = write_only_data.get(field)
                if val is not None:
                    ansible_data[field] = val

        if operation == "update" and not self._supports_create():
            for field in self._CREATE_ONLY_FIELDS:
                ansible_data.pop(field, None)

    def _supports_create(self):
        """Use OPTIONS to distinguish legacy and editable-only APIs."""
        return self._client.endpoint_supports_method("/api/gateway/v1/service_keys/", "POST")

    def _should_update(self, desired_data, current_data):
        """Compare all fields on legacy AAP, editable fields on newer AAP."""
        if self._supports_create():
            return super()._should_update(desired_data, current_data)

        ignored_fields = [field for field in self._CREATE_ONLY_FIELDS if self._task.args.get(field) is not None]
        if ignored_fields:
            self._display.warning("The AAP instance will ignore: %s when making this request." % ", ".join(sorted(ignored_fields)))
        editable_data = {key: value for key, value in desired_data.items() if key not in self._CREATE_ONLY_FIELDS}
        return super()._should_update(editable_data, current_data)

    def _skip_operation(self, operation, result):
        """Avoid POST when OPTIONS reports that the endpoint is read-only."""
        if operation == "create" and not self._supports_create():
            return self._warn_create_unsupported(result)
        return False

    def _handle_operation_error(self, error, operation, result):
        """Warn when newer AAP versions reject service-key creation."""
        error_text = str(error).lower()
        status_code = getattr(error, "status_code", None)
        if status_code is None:
            status_code = getattr(error, "details", {}).get("status_code")
        if operation != "create" or (status_code != 405 and "405" not in error_text):
            return False

        return self._warn_create_unsupported(result)

    def _warn_create_unsupported(self, result):
        """Return a stable no-op result for an editable-only AAP instance."""

        warning = "This version of AAP does not support creating service_keys through the API."
        # Match the normal resource result shape without implying that AAP
        # created the requested key.  ``state`` is an input directive, not a
        # returned resource attribute.
        service_key = asdict(AnsibleServiceKey(name=self._task.args.get("name")))
        service_key.pop("state")
        self._display.warning(warning)
        result.update(
            {
                "changed": False,
                "failed": False,
                self.MODULE_NAME: service_key,
                # Keep legacy flat result access stable for follow-up tasks.
                **service_key,
                "msg": warning,
                "warnings": [warning],
            }
        )
        return True
