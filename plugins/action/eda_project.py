#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.eda_project module.

Manages EDA projects with support for sync and wait-for-import behavior.
After creating or updating a project the plugin can optionally wait for the
EDA import to reach a terminal state (``completed`` or ``failed``).  An
explicit ``sync`` parameter triggers a project sync on an already-existing
project and, when combined with ``wait``, polls until that sync finishes.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import time
from typing import Optional

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.eda_project import AnsibleEdaProject
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.eda_project import (
    EDA_PROJECTS_DETAIL_ENDPOINT,
    EDA_PROJECTS_SYNC_ENDPOINT,
)

_SERVICE = "eda"
_IMPORT_POLL_INTERVAL = 2  # seconds between import_state polls
_IMPORT_POLL_TIMEOUT = 120  # max seconds to wait for import to finish


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for eda_project module."""

    MODULE_NAME = "eda_project"
    MODEL_CLASS = AnsibleEdaProject
    _WRITE_ONLY_FIELDS = frozenset({"sync", "wait"})

    def _wait_for_import(self, manager, project_id: int, timeout: int = _IMPORT_POLL_TIMEOUT) -> dict:
        """Poll a project's import_state until it reaches a terminal state.

        Args:
            manager: The platform manager / RPC client.
            project_id: Numeric ID of the project.
            timeout: Maximum seconds to wait.

        Returns:
            dict: The latest project data from the API.

        Raises:
            AnsibleError: If the import fails or times out.
        """
        detail_path = EDA_PROJECTS_DETAIL_ENDPOINT.format(id=project_id)
        start = time.monotonic()
        last_state = None

        while True:
            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                raise AnsibleError("Timeout waiting for project import to complete after %d seconds. Last import_state: %s" % (timeout, last_state))

            try:
                project_data = manager.direct_request("GET", detail_path)
                import_state = project_data.get("import_state", "")

                if import_state != last_state:
                    self._display.vvv("eda_project: import_state changed: %s -> %s" % (last_state, import_state))
                    last_state = import_state

                if import_state == "completed":
                    return project_data

                if import_state == "failed":
                    error_msg = project_data.get("import_error", "Unknown error")
                    raise AnsibleError("Project import failed: %s" % error_msg)

            except AnsibleError:
                raise
            except Exception as exc:
                self._display.vvv("eda_project: transient error during import poll: %s" % exc)

            time.sleep(_IMPORT_POLL_INTERVAL)

    def run(self, tmp: object = None, task_vars: Optional[dict] = None) -> dict:
        """Run the eda_project action plugin.

        Handles CRUD operations for EDA projects with additional sync and
        wait-for-import behavior.

        Args:
            tmp: Deprecated parameter.
            task_vars: Task variables dictionary.

        Returns:
            dict: Ansible result dictionary.
        """
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            resource_data = prepared["resource_data"]
            write_only_data = prepared["write_only_data"]
            manager = prepared["manager"]

            state = validated_params.get("state", "present")
            name = validated_params.get("name")
            new_name = validated_params.get("new_name")
            sync_enabled = write_only_data.get("sync", False)
            wait_for_completion = write_only_data.get("wait", True)

            # Validate scm_update_cache_timeout requires update_revision_on_launch
            scm_update_cache_timeout = validated_params.get("scm_update_cache_timeout", 0)
            update_revision_on_launch = validated_params.get("update_revision_on_launch", False)
            if scm_update_cache_timeout and scm_update_cache_timeout > 0 and not update_revision_on_launch:
                raise AnsibleError("scm_update_cache_timeout requires update_revision_on_launch to be true")

            # Find existing project by name
            existing = None
            try:
                find_result = manager.execute(
                    operation="find",
                    module_name=self.MODULE_NAME,
                    ansible_data={"name": name},
                )
                if find_result and find_result.get("id"):
                    existing = find_result
            except ValueError as exc:
                if "not found" not in str(exc).lower() and "404" not in str(exc):
                    raise

            # ---- state: absent ------------------------------------------------
            if state == "absent":
                if not existing:
                    result.update(
                        {
                            "changed": False,
                            "failed": False,
                            self.MODULE_NAME: {"state": "absent"},
                            "msg": "%s '%s' does not exist (already absent)" % (self.MODULE_NAME, name),
                        }
                    )
                    return result

                if self._task.check_mode:
                    result.update(
                        {
                            "changed": True,
                            "failed": False,
                            self.MODULE_NAME: {"state": "absent", "id": existing["id"]},
                        }
                    )
                    return result

                manager.execute(
                    operation="delete",
                    module_name=self.MODULE_NAME,
                    ansible_data={"id": existing["id"], "name": name},
                )
                result.update(
                    {
                        "changed": True,
                        "failed": False,
                        self.MODULE_NAME: {"state": "absent", "id": existing["id"]},
                    }
                )
                return result

            # ---- state: present -----------------------------------------------
            # Validate required fields for creation
            url = validated_params.get("url")
            if not existing and not url:
                raise AnsibleError("Parameter 'url' is required when state is present and project does not exist")

            if self._task.check_mode:
                result.update(
                    {
                        "changed": True,
                        "failed": False,
                        self.MODULE_NAME: {"name": new_name or name, "state": "present"},
                    }
                )
                return result

            if existing:
                # Check if update is needed
                if not self._should_update(resource_data, existing):
                    # No changes needed - but we may still need to sync
                    if sync_enabled:
                        self._trigger_sync(manager, existing["id"], name, wait_for_completion)
                        result.update(
                            {
                                "changed": True,
                                "failed": False,
                                self.MODULE_NAME: existing,
                                "id": existing.get("id"),
                                "msg": "Project synced",
                            }
                        )
                        return result

                    result.update(
                        {
                            "changed": False,
                            "failed": False,
                            self.MODULE_NAME: existing,
                            "id": existing.get("id"),
                        }
                    )
                    return result

                # Update existing project
                resource_data["id"] = existing["id"]
                update_result = manager.execute(
                    operation="update",
                    module_name=self.MODULE_NAME,
                    ansible_data=resource_data,
                )

                project_id = update_result.get("id", existing["id"])

                # Wait for import after update if enabled
                if wait_for_completion:
                    try:
                        self._wait_for_import(manager, project_id)
                    except AnsibleError as exc:
                        result.update({"changed": True, "failed": True, "msg": str(exc)})
                        return result

                # Sync if requested
                if sync_enabled:
                    self._trigger_sync(manager, project_id, name, wait_for_completion)

                result.update(
                    {
                        "changed": update_result.get("changed", True),
                        "failed": False,
                        self.MODULE_NAME: update_result,
                        "id": project_id,
                    }
                )
            else:
                # Create new project
                create_result = manager.execute(
                    operation="create",
                    module_name=self.MODULE_NAME,
                    ansible_data=resource_data,
                )

                project_id = create_result.get("id")
                if not project_id:
                    raise AnsibleError("Create response did not include a project ID")

                # Wait for initial import to complete
                if wait_for_completion:
                    try:
                        self._wait_for_import(manager, project_id)
                    except AnsibleError as exc:
                        result.update(
                            {
                                "changed": True,
                                "failed": True,
                                "msg": str(exc),
                                "id": project_id,
                            }
                        )
                        return result

                result.update(
                    {
                        "changed": True,
                        "failed": False,
                        self.MODULE_NAME: create_result,
                        "id": project_id,
                    }
                )

        except Exception as exc:
            import traceback

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result

    def _trigger_sync(self, manager, project_id: int, name: str, wait: bool) -> None:
        """Trigger a project sync and optionally wait for completion.

        Args:
            manager: The platform manager / RPC client.
            project_id: Numeric ID of the project.
            name: Project name (for logging).
            wait: Whether to wait for sync completion.

        Raises:
            AnsibleError: If the sync request fails or wait times out.
        """
        sync_path = EDA_PROJECTS_SYNC_ENDPOINT.format(id=project_id)
        self._display.vvv("eda_project: triggering sync for project '%s' (id=%s)" % (name, project_id))

        try:
            manager.direct_request("POST", sync_path)
        except Exception as exc:
            raise AnsibleError("Failed to trigger project sync: %s" % exc) from exc

        if wait:
            self._wait_for_import(manager, project_id)
