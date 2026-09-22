#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

from typing import Any

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.authenticator_user import AnsibleAuthenticatorUser


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "authenticator_user"
    MODEL_CLASS = AnsibleAuthenticatorUser
    LOOKUP_FIELD = "id"

    def _resolve_lookup(self, resource: Any, resource_data: dict, validated_params: dict) -> None:
        """Use ``authenticator_user_id`` as the resource ID for lookup.

        Args:
            resource: The authenticator-user resource built from task input.
            resource_data: The task input passed to the platform manager.
            validated_params: Full validated task parameters.
        """
        if str(resource.authenticator_user_id).isdigit():
            resource.id = int(resource.authenticator_user_id)
            resource_data["id"] = resource.id
