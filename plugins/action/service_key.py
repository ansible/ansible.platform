#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.service_key import AnsibleServiceKey


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "service_key"
    MODEL_CLASS = AnsibleServiceKey
    # mark_previous_inactive: operation-time directive; API never returns it.
    # secret: write-only; API returns null/hash, not the original value.
    # secret_length: write-only; API returns null on GET requests.
    _WRITE_ONLY_FIELDS = frozenset({"mark_previous_inactive", "secret", "secret_length"})

    def _should_update(self, desired_data, current_data):
        """Override to strictly ignore write-only fields during idempotency checks.

        This prevents the API's 'null' responses for hidden fields from falsely
        triggering a changed: true state against the user's playbook values.
        """
        res_data = {k: v for k, v in desired_data.items() if k not in self._WRITE_ONLY_FIELDS}
        fnd_data = {k: v for k, v in current_data.items() if k not in self._WRITE_ONLY_FIELDS}
        return super(ActionModule, self)._should_update(res_data, fnd_data)

    def _pre_execute_hook(self, ansible_data, write_only_data, validated_params, operation):
        """Re-inject write-only fields so they reach the API payload.

        ``secret`` is strictly non-editable after creation, so we only inject
        it for "create" operations, never for "update" (PATCH) requests.
        """
        if operation == "create":
            for field in ("mark_previous_inactive", "secret", "secret_length"):
                val = write_only_data.get(field)
                if val is not None:
                    ansible_data[field] = val
        elif operation == "update":
            # Secret is non-editable, do not inject it for PATCH
            for field in ("mark_previous_inactive", "secret_length"):
                val = write_only_data.get(field)
                if val is not None:
                    ansible_data[field] = val
