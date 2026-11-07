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


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for eda_credential_input_source module."""

    MODULE_NAME = "eda_credential_input_source"
    MODEL_CLASS = AnsibleEdaCredentialInputSource
    _NO_LOG_FIELDS = BaseResourceActionPlugin._NO_LOG_FIELDS | frozenset({"metadata"})
    _PRESERVE_OUTPUT_FIELDS = frozenset({"target_credential", "source_credential"})
    # The organization is used to scope creation and lookup, but the API does
    # not return organization_name and the field is not mutable after creation.
    _READ_ONLY_FIELDS = BaseResourceActionPlugin._READ_ONLY_FIELDS | frozenset({"organization_name"})

    def _should_update(self, desired_data: dict, current_data: dict) -> bool:
        """Compare mutable fields after find has matched the composite identity."""
        comparable = {key: value for key, value in desired_data.items() if key not in {"input_field_name", "target_credential", "source_credential"}}
        return super()._should_update(comparable, current_data)
