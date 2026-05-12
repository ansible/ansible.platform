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

# Name of the Platform Auditor role definition in the Gateway API.
_PLATFORM_AUDITOR_ROLE = "Platform Auditor"


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

    def _handle_platform_auditor(self, result: dict, is_platform_auditor_desired: bool) -> None:
        """Manage the Platform Auditor role assignment for a user.

        ``is_platform_auditor`` is a computed, read-only field on the user
        object — it reflects whether the user has a role_user_assignment for
        the "Platform Auditor" role definition.  Direct PATCH to the user
        endpoint cannot change it; role assignments must be created or deleted
        instead.  This mirrors the stable-2.6 module behaviour.

        Args:
            result: The result dict from the main user CRUD (modified in-place).
            is_platform_auditor_desired: True to grant auditor, False to revoke.
        """
        manager = self._client
        if manager is None:
            return

        user_id = result.get("id")
        if not user_id:
            return

        try:
            # Resolve the Platform Auditor role definition ID.
            role_def_id = manager.lookup_resource_id("role_definitions", "name", _PLATFORM_AUDITOR_ROLE)
            if not role_def_id:
                return

            # Check whether a role_user_assignment already exists for this
            # user + role_definition by searching the list endpoint.
            # A ValueError is raised when no matching assignment is found.
            has_assignment = False
            assignment_id = None
            try:
                find_result = manager.execute(
                    operation="find",
                    module_name="role_user_assignment",
                    ansible_data={
                        "role_definition": str(role_def_id),
                        "user": str(user_id),
                    },
                )
                has_assignment = bool(find_result and find_result.get("id"))
                assignment_id = find_result.get("id") if has_assignment else None
            except ValueError:
                # No matching assignment found — has_assignment stays False.
                has_assignment = False

            if is_platform_auditor_desired and not has_assignment:
                # Grant auditor: create a role_user_assignment.
                manager.execute(
                    operation="create",
                    module_name="role_user_assignment",
                    ansible_data={
                        "role_definition": str(role_def_id),
                        "user": str(user_id),
                        "state": "present",
                    },
                )
                result["changed"] = True

            elif not is_platform_auditor_desired and has_assignment and assignment_id:
                # Revoke auditor: delete the existing role_user_assignment.
                manager.execute(
                    operation="delete",
                    module_name="role_user_assignment",
                    ansible_data={
                        "id": assignment_id,
                        "role_definition": str(role_def_id),
                        "user": str(user_id),
                        "state": "absent",
                    },
                )
                result["changed"] = True

        except Exception as exc:
            result["failed"] = True
            result["msg"] = "Failed to manage platform auditor role assignment: %s" % str(exc)

    def run(self, tmp: object = None, task_vars: dict = None) -> dict:
        """Run the user action plugin.

        Extends the base run() to handle ``is_platform_auditor`` via
        role_user_assignment CRUD rather than a direct user PATCH.
        The field is a computed, read-only value on the user object, so it
        cannot be set via PATCH — the underlying role assignment must be
        created or deleted instead (identical to the stable-2.6 behaviour).

        Args:
            tmp: Temporary path (unused, kept for API compatibility).
            task_vars: Task variables from Ansible.

        Returns:
            dict: Result dict with ``changed``, ``failed``, and user resource fields.
        """
        # Capture the desired auditor state *before* super().run() processes args.
        is_platform_auditor_desired = self._task.args.get("is_platform_auditor")

        # Remove is_platform_auditor from the task args before the base run()
        # processes them.  The field is read-only/computed from role assignments;
        # PATCHing the user object directly has no effect on the API side.
        # We manage auditor status below via role_user_assignment CRUD.
        if "is_platform_auditor" in self._task.args:
            self._task.args.pop("is_platform_auditor")

        result = super().run(tmp, task_vars)

        if result.get("failed"):
            return result

        # Handle is_platform_auditor via role_user_assignment (stable-2.6 parity).
        if is_platform_auditor_desired is not None:
            state = self._task.args.get("state", "present")
            if state not in ("absent", "deleted"):
                self._handle_platform_auditor(result, bool(is_platform_auditor_desired))

        return result
