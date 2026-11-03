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
import traceback
from typing import Any, Optional

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.eda_project import AnsibleEdaProject
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.eda_project import (
    EDA_PROJECTS_DETAIL_ENDPOINT,
    EDA_PROJECTS_SYNC_ENDPOINT,
    resolve_foreign_key_id,
)

_SERVICE = "eda"
_IMPORT_POLL_INTERVAL = 2  # seconds between import_state polls
_IMPORT_POLL_TIMEOUT = 120  # max seconds to wait for import to finish


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for eda_project module."""

    MODULE_NAME = "eda_project"
    MODEL_CLASS = AnsibleEdaProject
    _WRITE_ONLY_FIELDS = frozenset({"sync", "wait"})
    _resolved_fk_ids: dict[tuple[str, str, str], Optional[int]]

    def _wait_for_import(self, manager: Any, project_id: int, timeout: int = _IMPORT_POLL_TIMEOUT) -> dict:
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
        last_exception = None

        while True:
            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                message = "Timeout waiting for project import to complete after %d seconds. Last import_state: %s" % (timeout, last_state)
                if last_exception is not None:
                    message += ". Last poll error: %s" % last_exception
                raise AnsibleError(message)

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
                last_exception = exc
                self._display.vvv("eda_project: transient error during import poll: %s" % exc)

            remaining = max(timeout - (time.monotonic() - start), 0)
            time.sleep(min(_IMPORT_POLL_INTERVAL, remaining))

    def _find_project(self, manager: Any, name: Optional[str], organization_name: Optional[str]) -> Optional[dict]:
        """Find exactly one project by name, scoped to an organization when given."""
        if not name:
            return None

        query_params: dict[str, Any] = {}
        if organization_name is not None:
            query_params["organization_id"] = self._resolve_foreign_key(manager, "organizations", organization_name, "gateway")

        find_data: dict[str, Any]
        if str(name).strip().isdigit():
            find_data = {"id": int(str(name).strip()), "name": str(name)}
            if organization_name is not None:
                find_data["organization_name"] = organization_name
            return self._execute_find(manager, find_data)

        try:
            project_id = manager.lookup_resource_id(
                "projects",
                "name",
                str(name),
                service=_SERVICE,
                extra_query_params=query_params,
                require_unique=True,
            )
        except ValueError as exc:
            if "not found" in str(exc).lower():
                return None
            raise

        if project_id is None:
            return None
        # The ID came from the organization-scoped list lookup above. Avoid
        # repeating the organization constraint on the detail GET: some EDA
        # project responses omit organization_id, which makes generic
        # composite-key validation reject a correctly scoped result.
        find_data = {"id": project_id, "name": str(name)}
        return self._execute_find(manager, find_data)

    def _execute_find(self, manager: Any, find_data: dict) -> Optional[dict]:
        """Return a project found by ID, treating only missing resources as absent."""
        try:
            return manager.execute(operation="find", module_name=self.MODULE_NAME, ansible_data=find_data)
        except Exception as exc:
            response = getattr(exc, "response", None)
            details = getattr(exc, "details", None)
            status_code = details.get("status_code") if isinstance(details, dict) else None
            status_code = status_code or getattr(response, "status_code", None) or getattr(exc, "status_code", None)
            if (isinstance(exc, ValueError) and ("not found" in str(exc).lower() or "404" in str(exc))) or status_code == 404:
                return None
            raise

    @staticmethod
    def _supports_organization(manager: Any) -> bool:
        """Check whether this EDA API exposes organization-aware project creation."""
        try:
            manager.search_api("config", service=_SERVICE)
        except Exception as exc:
            response = getattr(exc, "response", None)
            details = getattr(exc, "details", None)
            status_code = details.get("status_code") if isinstance(details, dict) else None
            status_code = status_code or getattr(response, "status_code", None) or getattr(exc, "status_code", None)
            if status_code == 404 or (isinstance(exc, ValueError) and "404" in str(exc)):
                return False
            raise
        return True

    def _resolve_foreign_key(self, manager: Any, endpoint: str, value: Any, service: str) -> Optional[int]:
        """Resolve a foreign key once per action run for validation and comparison."""
        cache: dict[tuple[str, str, str], Optional[int]] = getattr(self, "_resolved_fk_ids", {})
        self._resolved_fk_ids = cache
        cache_key = (endpoint, service, str(value).strip())
        if cache_key not in cache:
            cache[cache_key] = resolve_foreign_key_id(manager, endpoint, "name", value, service=service)
        return cache[cache_key]

    @staticmethod
    def _comparison_data(resource_data: dict, found_by_new_name: bool, new_name: Optional[str]) -> dict:
        """Normalize rename input for idempotency comparison after lookup by new name."""
        comparison_data = dict(resource_data)
        if found_by_new_name:
            comparison_data.pop("new_name", None)
            comparison_data["name"] = new_name
        return comparison_data

    def _should_update(self, desired_data, current_data):
        """Compare EDA foreign keys by ID so names and numeric IDs are equivalent."""
        if desired_data.get("new_name"):
            return True

        comparable_data = dict(desired_data)
        manager = getattr(self, "_client", None)
        fk_fields = {
            "credential": ("eda-credentials", "eda"),
            "organization_name": ("organizations", "gateway"),
        }
        for field, (endpoint, service) in fk_fields.items():
            desired_value = comparable_data.get(field)
            if desired_value is None or field not in current_data:
                continue
            current_value = current_data[field]
            desired_id = self._resolve_foreign_key(manager, endpoint, desired_value, service)
            current_id = self._resolve_foreign_key(manager, endpoint, current_value, service)
            if desired_id != current_id:
                return True
            comparable_data.pop(field, None)

        return super()._should_update(comparable_data, current_data)

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
            self._resolved_fk_ids = {}
            validated_params = prepared["validated_params"]
            resource_data = prepared["resource_data"]
            write_only_data = prepared["write_only_data"]
            manager = prepared["manager"]

            state = validated_params.get("state", "present")
            name = validated_params.get("name")
            new_name = validated_params.get("new_name")
            sync_enabled = write_only_data.get("sync", False)
            wait_for_completion = write_only_data.get("wait", True)

            # Find the current name first, then the requested new name so a
            # repeated rename remains idempotent rather than creating a copy.
            organization_name = validated_params.get("organization_name")
            existing = self._find_project(manager, name, organization_name)
            found_by_new_name = False
            if existing is None and new_name and new_name != name:
                existing = self._find_project(manager, new_name, organization_name)
                found_by_new_name = existing is not None

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
            if not existing and organization_name is None and self._supports_organization(manager):
                raise AnsibleError("Parameter 'organization_name' is required when state is present and project does not exist")

            # Defaults apply at creation. For updates, omitted values should
            # preserve the server's settings instead of resetting them.
            if existing:
                for field in ("update_revision_on_launch", "scm_update_cache_timeout"):
                    if field not in self._task.args:
                        resource_data.pop(field, None)

            update_revision_on_launch = validated_params.get("update_revision_on_launch", False)
            scm_update_cache_timeout = validated_params.get("scm_update_cache_timeout", 0)
            if existing and "update_revision_on_launch" not in self._task.args:
                update_revision_on_launch = existing.get("update_revision_on_launch", False)
            if existing and "scm_update_cache_timeout" not in self._task.args:
                scm_update_cache_timeout = existing.get("scm_update_cache_timeout", 0)
            if scm_update_cache_timeout and scm_update_cache_timeout > 0 and not update_revision_on_launch:
                raise AnsibleError("scm_update_cache_timeout requires update_revision_on_launch to be true")

            # Validate requested foreign keys even in check mode and on no-op
            # updates, where the manager would otherwise not run the transform.
            for field, (endpoint, service) in {
                "credential": ("eda-credentials", "eda"),
                "organization_name": ("organizations", "gateway"),
            }.items():
                value = validated_params.get(field)
                if value is not None:
                    self._resolve_foreign_key(manager, endpoint, value, service)

            if self._task.check_mode:
                comparison_data = self._comparison_data(resource_data, found_by_new_name, new_name)
                changed = not existing or self._should_update(comparison_data, existing) or sync_enabled
                result.update(
                    {
                        "changed": changed,
                        "failed": False,
                        self.MODULE_NAME: {"name": new_name or name, "state": "present", **({"id": existing["id"]} if existing else {})},
                    }
                )
                return result

            if existing:
                # Check if update is needed
                comparison_data = self._comparison_data(resource_data, found_by_new_name, new_name)
                if not self._should_update(comparison_data, existing):
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
            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result

    def _trigger_sync(self, manager: Any, project_id: int, name: str, wait: bool) -> None:
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
            # retry=False: sync is not idempotent -- retrying a lost response
            # could trigger a duplicate sync.
            manager.launch_resource(launch_url=sync_path, payload={}, service=_SERVICE, retry=False)
        except Exception as exc:
            raise AnsibleError("Failed to trigger project sync: %s" % exc) from exc

        if wait:
            self._wait_for_import(manager, project_id)
