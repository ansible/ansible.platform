#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.decision_environment import (
    AnsibleDecisionEnvironment,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.decision_environment import (
    DecisionEnvironmentTransformMixin_v1,
)


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "decision_environment"
    MODEL_CLASS = AnsibleDecisionEnvironment
    _REQUIRED_IF = [["state", "present", ["image_url"]]]

    _REFERENCE_FIELDS = (
        ("credential", "eda-credentials", "eda"),
        ("organization_name", "organizations", "gateway"),
    )

    def _should_update(self, desired_data: dict, current_data: dict) -> bool:
        """Compare credential and organization references by their resource IDs."""
        comparable = dict(desired_data)
        manager = getattr(self, "_client", None)

        for field, endpoint, service in self._REFERENCE_FIELDS:
            desired_value = desired_data.get(field)
            if desired_value is None or field not in current_data:
                continue

            desired_id = DecisionEnvironmentTransformMixin_v1.resolve_reference_id(manager, endpoint, desired_value, service)
            current_id = DecisionEnvironmentTransformMixin_v1.resolve_reference_id(manager, endpoint, current_data[field], service)
            if desired_id != current_id:
                return True
            comparable.pop(field, None)

        return super()._should_update(comparable, current_data)
