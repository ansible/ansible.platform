#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

from typing import Any, Dict, Optional

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.authenticator_user import AnsibleAuthenticatorUser


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "authenticator_user"
    MODEL_CLASS = AnsibleAuthenticatorUser
    LOOKUP_FIELD = "id"

    def run(self, tmp: Optional[object] = None, task_vars: Optional[Dict[str, Any]] = None) -> dict:
        """Check both the user and authenticator for the read-only exists state.

        Args:
            tmp: Temporary directory passed through to the base action.
            task_vars: Ansible variables used to initialize the API manager.

        Returns:
            dict: Ansible result for the requested authenticator user.
        """
        result = super().run(tmp, task_vars)
        if self._task.args.get("state", "present") != "exists" or result.get("failed"):
            return result

        user_id = self._task.args.get("authenticator_user_id")
        if not result.get("exists"):
            result.update(
                {
                    "failed": True,
                    "msg": "Authenticator user %s was not found" % user_id,
                }
            )
            return result

        authenticator_user = result.get(self.MODULE_NAME) or {}
        current_authenticator = authenticator_user.get("authenticator")
        requested_authenticator = self._task.args.get("authenticator")
        manager = self._client
        try:
            current_id = self._resolve_authenticator_id(manager, current_authenticator, "slug")
            requested_id = self._resolve_authenticator_id(manager, requested_authenticator, "name")
        except Exception as exc:
            result.update({"failed": True, "exists": False, "msg": str(exc)})
            return result

        if current_id != requested_id:
            result.update(
                {
                    "failed": True,
                    "exists": False,
                    "msg": "Authenticator user %s is associated with authenticator %s, not requested authenticator %s"
                    % (user_id, current_authenticator, requested_authenticator),
                }
            )
        return result

    @staticmethod
    def _resolve_authenticator_id(manager: Any, value: Any, lookup_field: str) -> Optional[int]:
        """Normalize an authenticator ID, name, or provider slug to its ID.

        Args:
            manager: API manager used for authenticator lookups.
            value: Authenticator identifier to resolve.
            lookup_field: Field used to search nonnumeric identifiers.

        Returns:
            Optional[int]: Numeric authenticator ID, or ``None`` for no value.
        """
        if value is None:
            return None
        if str(value).isdigit():
            return int(value)
        return manager.lookup_resource_id("authenticators", lookup_field, str(value), service="gateway")

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
