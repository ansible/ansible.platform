#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.user module."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from typing import Any

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.user import AnsibleUser


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for the user module."""

    MODULE_NAME = "user"
    MODEL_CLASS = AnsibleUser
    LOOKUP_FIELD = "username"

    # Fields that are in the argspec but not in AnsibleUser; popped before
    # MODEL_CLASS instantiation and passed to _pre_execute_hook.
    _WRITE_ONLY_FIELDS = frozenset({"update_secrets"})

    # Deprecated argspec fields: emit a warning and strip before processing.
    _DEPRECATED_FIELDS = {
        "authenticators": (
            "The 'authenticators' parameter is deprecated. Use 'associated_authenticators' instead.",
            "4.0.0",
        ),
        "authenticator_uid": (
            "The 'authenticator_uid' parameter is deprecated. Use 'associated_authenticators' instead.",
            "4.0.0",
        ),
    }

    def _resolve_lookup(self, resource: Any, resource_data: dict, validated_params: dict) -> None:
        """Treat a numeric username string as an ID-based lookup.

        When ``username`` is a digit string (e.g. ``username: "{{ user.id }}"``),
        set ``resource.id`` so the manager can find the user by primary key
        and restore the real username from the API response afterwards.

        Args:
            resource: The AnsibleUser instance just built.
            resource_data: The filtered dict used to build *resource*.
            validated_params: Full validated input parameters.
        """
        if str(getattr(resource, "username", "")).isdigit():
            resource.id = int(resource.username)
            resource_data["id"] = resource.id

    def _build_ansible_data(self, resource: Any, validated_params: dict, operation: str) -> dict:
        """Build ansible_data from explicitly-provided task parameters only.

        AnsibleUser.__post_init__ sets ``organizations=[]`` for any instance
        where organizations was not supplied.  Using ``asdict(resource)`` would
        therefore send ``organizations: []`` on every task, silently clearing
        the user's organization memberships.  This override sends only the
        fields the operator actually specified in the task, preventing
        unintended side-effects from default values in the dataclass.

        Args:
            resource: The AnsibleUser instance.
            validated_params: Full validated input parameters.
            operation: The resolved operation string.

        Returns:
            dict: Only the fields present in the task args, plus ``id`` if set.
        """
        data = {k: getattr(resource, k) for k in validated_params if hasattr(resource, k)}
        if getattr(resource, "id", None) is not None:
            data["id"] = resource.id
        return data

    def _pre_execute_hook(self, ansible_data: dict, write_only_data: dict, validated_params: dict, operation: str) -> None:
        """Strip the password field on updates when update_secrets is False.

        Args:
            ansible_data: The dict about to be sent to manager.execute().
            write_only_data: Contains ``update_secrets`` (default True).
            validated_params: Full validated input parameters.
            operation: The resolved operation string.
        """
        if not write_only_data.get("update_secrets", True) and operation == "update":
            ansible_data.pop("password", None)
