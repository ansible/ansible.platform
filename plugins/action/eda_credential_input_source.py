#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.eda_credential_input_source import (
    AnsibleEdaCredentialInputSource,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.eda_credential_input_source import (
    EdaCredentialInputSourceTransformMixin_v1,
)


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for eda_credential_input_source module."""

    MODULE_NAME = "eda_credential_input_source"
    MODEL_CLASS = AnsibleEdaCredentialInputSource
    # The organization is used to scope creation and lookup, but the API does
    # not return organization_name and the field is not mutable after creation.
    _READ_ONLY_FIELDS = BaseResourceActionPlugin._READ_ONLY_FIELDS | frozenset({"organization_name"})

    def _should_update(self, desired_data: dict, current_data: dict) -> bool:
        """Compare credential references by ID before checking mutable fields."""
        comparable = dict(desired_data)
        manager = getattr(self, "_client", None)

        credential_fields = ("target_credential", "source_credential")
        needs_reference_comparison = any(desired_data.get(field) is not None and field in current_data for field in credential_fields)
        organization_name = desired_data.get("organization_name") if needs_reference_comparison else None
        organization_id = (
            EdaCredentialInputSourceTransformMixin_v1.resolve_reference_id(
                manager,
                "organizations",
                organization_name,
                "organization",
                service="gateway",
            )
            if organization_name is not None
            else None
        )
        credential_scope = {"organization_id": organization_id} if organization_id is not None else None

        for field, label in (("target_credential", "target credential"), ("source_credential", "source credential")):
            desired_value = desired_data.get(field)
            if desired_value is None or field not in current_data:
                continue

            desired_id = EdaCredentialInputSourceTransformMixin_v1.resolve_reference_id(manager, "eda-credentials", desired_value, label, credential_scope)
            current_id = EdaCredentialInputSourceTransformMixin_v1.resolve_reference_id(
                manager, "eda-credentials", current_data[field], label, credential_scope
            )
            if desired_id != current_id:
                return True
            comparable.pop(field, None)

        return super()._should_update(comparable, current_data)
