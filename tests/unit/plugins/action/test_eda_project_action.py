# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the eda_project action plugin."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ansible.plugins.action import ActionBase
from ansible_collections.ansible.platform.plugins.action.eda_project import ActionModule


class TestEdaProjectAction(unittest.TestCase):
    """Test eda_project action plugin CRUD and sync/wait behavior."""

    def _make_action(self, check_mode=False):
        action = ActionModule.__new__(ActionModule)
        action._task = MagicMock()
        action._task.check_mode = check_mode
        action._task.args = {}
        action._display = MagicMock()
        action._display.verbosity = 0
        return action

    def _make_manager(self, find_result=None, create_result=None, update_result=None, delete_error=None, organization_supported=False):
        manager = MagicMock()
        manager.cache = {}

        def lookup_resource_id(endpoint, lookup_field, lookup_value, service="gateway", extra_query_params=None, require_unique=False):
            if endpoint == "organizations":
                if service == "eda":
                    return {"Default": 901, "Other": 902}.get(str(lookup_value), 901)
                return 1
            if endpoint == "projects" and find_result and find_result.get("name") == lookup_value:
                return find_result["id"]
            raise ValueError("Resource '%s' with %s=%s not found" % (endpoint, lookup_field, lookup_value))

        manager.lookup_resource_id.side_effect = lookup_resource_id

        def search_api_side_effect(endpoint, service="gateway", **kwargs):
            if endpoint == "config" and service == "eda" and not organization_supported:
                raise ValueError("404 Not Found")
            return {}

        manager.search_api.side_effect = search_api_side_effect

        def execute_side_effect(operation, module_name, ansible_data):
            if operation == "find":
                if find_result:
                    return find_result
                raise ValueError("Not found")
            if operation == "delete":
                if delete_error:
                    raise delete_error
                return {}
            if operation == "create":
                return create_result or {"id": 100, "name": ansible_data.get("name", ""), "changed": True}
            if operation == "update":
                return update_result or {"id": ansible_data.get("id", 100), "name": ansible_data.get("name", ""), "changed": True}
            return {}

        manager.execute.side_effect = execute_side_effect
        manager.direct_request.return_value = {"id": 100, "import_state": "completed"}
        return manager

    def _run_action(self, action, manager, validated_params):
        doc = "module: eda_project"
        argspec = {
            "argument_spec": {
                "name": {},
                "new_name": {},
                "description": {},
                "url": {},
                "proxy": {},
                "credential": {},
                "organization_name": {"aliases": ["organization"]},
                "scm_branch": {},
                "state": {},
                "sync": {"type": "bool"},
                "wait": {"type": "bool"},
                "update_revision_on_launch": {"type": "bool"},
                "scm_update_cache_timeout": {"type": "int"},
            },
        }
        validation = SimpleNamespace(validated_parameters=validated_params)

        with patch.object(ActionBase, "run", return_value={}):
            with patch.object(action, "_get_documentation", return_value=doc):
                with patch.object(action, "_build_argspec_from_docs", return_value=argspec):
                    with patch.object(action, "_validate_data", return_value=validation):
                        with patch.object(action, "_get_or_spawn_manager", return_value=(manager, None)):
                            return action.run(task_vars={})

    # ---- Create tests ----

    def test_create_new_project(self):
        """Create project when none exists."""
        action = self._make_action()
        manager = self._make_manager(
            find_result=None,
            create_result={"id": 100, "name": "my-project", "changed": True},
            organization_supported=True,
        )
        result = self._run_action(
            action,
            manager,
            {
                "name": "my-project",
                "url": "https://example.com/repo.git",
                "organization_name": "Default",
                "state": "present",
                "sync": False,
                "wait": True,
                "update_revision_on_launch": False,
                "scm_update_cache_timeout": 0,
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        self.assertEqual(result["id"], 100)
        calls = [c.kwargs["operation"] for c in manager.execute.call_args_list]
        self.assertEqual(calls, ["create"])
        manager.lookup_resource_id.assert_any_call("organizations", "name", "Default", service="eda", require_unique=True)
        manager.lookup_resource_id.assert_any_call("projects", "name", "my-project", service="eda", require_unique=True)

    def test_create_without_url_fails(self):
        """Creating a project without url raises an error."""
        action = self._make_action()
        manager = self._make_manager(find_result=None)
        result = self._run_action(
            action,
            manager,
            {
                "name": "my-project",
                "state": "present",
                "sync": False,
                "wait": True,
                "update_revision_on_launch": False,
                "scm_update_cache_timeout": 0,
            },
        )

        self.assertTrue(result["failed"])
        self.assertIn("url", result["msg"].lower())

    def test_create_requires_organization_when_supported(self):
        """Newer EDA APIs require organization_name when creating a project."""
        action = self._make_action()
        manager = self._make_manager(find_result=None, organization_supported=True)

        result = self._run_action(
            action,
            manager,
            {
                "name": "my-project",
                "url": "https://example.com/repo.git",
                "state": "present",
                "sync": False,
                "wait": True,
            },
        )

        self.assertTrue(result["failed"])
        self.assertIn("organization_name", result["msg"])
        self.assertFalse(any(call.kwargs.get("operation") == "create" for call in manager.execute.call_args_list))

    def test_create_waits_for_import(self):
        """Create with wait=True polls import_state."""
        action = self._make_action()
        manager = self._make_manager(
            find_result=None,
            create_result={"id": 100, "name": "my-project", "changed": True},
        )
        manager.direct_request.return_value = {"id": 100, "import_state": "completed"}

        result = self._run_action(
            action,
            manager,
            {
                "name": "my-project",
                "url": "https://example.com/repo.git",
                "state": "present",
                "sync": False,
                "wait": True,
                "update_revision_on_launch": False,
                "scm_update_cache_timeout": 0,
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        # Verify import poll was called
        manager.direct_request.assert_called_with("GET", "/api/eda/v1/projects/100/")

    def test_create_no_wait(self):
        """Create with wait=False skips import polling."""
        action = self._make_action()
        manager = self._make_manager(
            find_result=None,
            create_result={"id": 100, "name": "my-project", "changed": True},
        )

        result = self._run_action(
            action,
            manager,
            {
                "name": "my-project",
                "url": "https://example.com/repo.git",
                "state": "present",
                "sync": False,
                "wait": False,
                "update_revision_on_launch": False,
                "scm_update_cache_timeout": 0,
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        # direct_request should NOT be called (no polling)
        manager.direct_request.assert_not_called()

    # ---- Update tests ----

    def test_update_existing_project(self):
        """Update project when it exists and has changes."""
        action = self._make_action()
        existing = {"id": 99, "name": "my-project", "description": "old desc", "organization_name": "Default"}
        manager = self._make_manager(
            find_result=existing,
            update_result={"id": 99, "name": "my-project", "description": "new desc", "changed": True},
            organization_supported=True,
        )

        result = self._run_action(
            action,
            manager,
            {
                "name": "my-project",
                "description": "new desc",
                "organization_name": "Default",
                "state": "present",
                "sync": False,
                "wait": True,
                "update_revision_on_launch": False,
                "scm_update_cache_timeout": 0,
            },
        )

        self.assertFalse(result.get("failed", False))
        calls = [c.kwargs["operation"] for c in manager.execute.call_args_list]
        self.assertIn("update", calls)

    def test_no_update_when_idempotent(self):
        """No update when existing project matches desired state."""
        action = self._make_action()
        existing = {"id": 99, "name": "my-project", "description": "same desc"}
        manager = self._make_manager(find_result=existing)

        result = self._run_action(
            action,
            manager,
            {
                "name": "my-project",
                "description": "same desc",
                "state": "present",
                "sync": False,
                "wait": True,
                "update_revision_on_launch": False,
                "scm_update_cache_timeout": 0,
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertFalse(result["changed"])
        calls = [c.kwargs["operation"] for c in manager.execute.call_args_list]
        self.assertNotIn("update", calls)

    def test_existing_present_without_organization_skips_capability_probe(self):
        """Do not probe organization support for an unscoped existing project update."""
        action = self._make_action()
        manager = self._make_manager(find_result={"id": 99, "name": "my-project", "description": "same"}, organization_supported=True)

        result = self._run_action(
            action,
            manager,
            {
                "name": "my-project",
                "description": "same",
                "state": "present",
                "sync": False,
                "wait": True,
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertFalse(result["changed"])
        manager.search_api.assert_not_called()

    # ---- Delete tests ----

    def test_delete_existing_project(self):
        """Delete project when it exists."""
        action = self._make_action()
        manager = self._make_manager(find_result={"id": 99, "name": "my-project"})
        result = self._run_action(
            action,
            manager,
            {
                "name": "my-project",
                "state": "absent",
                "sync": False,
                "wait": True,
                "update_revision_on_launch": False,
                "scm_update_cache_timeout": 0,
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        calls = [c.kwargs["operation"] for c in manager.execute.call_args_list]
        self.assertEqual(calls, ["find", "delete"])

    def test_delete_nonexistent_project(self):
        """No-op when deleting project that does not exist."""
        action = self._make_action()
        manager = self._make_manager(find_result=None)
        result = self._run_action(
            action,
            manager,
            {
                "name": "ghost-project",
                "state": "absent",
                "sync": False,
                "wait": True,
                "update_revision_on_launch": False,
                "scm_update_cache_timeout": 0,
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertFalse(result["changed"])
        self.assertIn("already absent", result["msg"])

    def test_delete_with_organization_skips_ownership_check_when_unsupported(self):
        """Older EDA versions still find and delete projects by their supported name filter."""
        action = self._make_action()
        manager = self._make_manager(find_result={"id": 99, "name": "my-project"}, organization_supported=False)

        result = self._run_action(
            action,
            manager,
            {
                "name": "my-project",
                "organization_name": "Default",
                "state": "absent",
                "sync": False,
                "wait": True,
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        manager.lookup_resource_id.assert_called_once_with("projects", "name", "my-project", service="eda", require_unique=True)
        manager.search_api.assert_called_once_with("config", service="eda")
        self.assertEqual([call.kwargs["operation"] for call in manager.execute.call_args_list], ["find", "delete"])

    def test_delete_rejects_project_from_different_organization(self):
        """Do not delete a same-named project owned by another organization."""
        action = self._make_action()
        manager = self._make_manager(find_result={"id": 99, "name": "my-project", "organization_name": "Other"}, organization_supported=True)

        result = self._run_action(
            action,
            manager,
            {
                "name": "my-project",
                "organization_name": "Default",
                "state": "absent",
                "sync": False,
                "wait": True,
            },
        )

        self.assertTrue(result["failed"])
        self.assertIn("not requested organization", result["msg"])
        self.assertEqual([call.kwargs["operation"] for call in manager.execute.call_args_list], ["find"])

    def test_present_rejects_new_name_match_from_different_organization(self):
        """The rename fallback must validate ownership before updating the target."""
        action = self._make_action()
        manager = self._make_manager(find_result={"id": 99, "name": "new-name", "organization_name": "Other"}, organization_supported=True)

        result = self._run_action(
            action,
            manager,
            {
                "name": "old-name",
                "new_name": "new-name",
                "organization_name": "Default",
                "url": "https://example.com/repo.git",
                "state": "present",
                "sync": False,
                "wait": False,
            },
        )

        self.assertTrue(result["failed"])
        self.assertIn("not requested organization", result["msg"])
        self.assertEqual([call.kwargs["operation"] for call in manager.execute.call_args_list], ["find"])

    def test_present_rejects_project_when_owner_is_missing(self):
        """Do not update a project when the supported API omits its owner."""
        action = self._make_action()
        manager = self._make_manager(find_result={"id": 99, "name": "my-project"}, organization_supported=True)

        result = self._run_action(
            action,
            manager,
            {
                "name": "my-project",
                "organization_name": "Default",
                "description": "updated",
                "url": "https://example.com/repo.git",
                "state": "present",
                "sync": False,
                "wait": False,
            },
        )

        self.assertTrue(result["failed"])
        self.assertIn("no organization", result["msg"])
        self.assertEqual([call.kwargs["operation"] for call in manager.execute.call_args_list], ["find"])

    def test_create_with_organization_omits_unsupported_relationship(self):
        """EDA versions without config/organizations endpoints create without organization resolution."""
        action = self._make_action()
        manager = self._make_manager(find_result=None, organization_supported=False)

        result = self._run_action(
            action,
            manager,
            {
                "name": "my-project",
                "url": "https://example.com/repo.git",
                "organization_name": "Default",
                "state": "present",
                "sync": False,
                "wait": True,
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        manager.lookup_resource_id.assert_called_once_with("projects", "name", "my-project", service="eda", require_unique=True)
        self.assertEqual([call.kwargs["operation"] for call in manager.execute.call_args_list], ["create"])

    def test_comparison_ignores_organization_when_endpoint_is_unsupported(self):
        action = self._make_action()
        manager = self._make_manager(organization_supported=False)
        action._client = manager
        action._resolved_fk_ids = {}

        self.assertFalse(action._should_update({"organization_name": "Default"}, {"name": "my-project"}))
        manager.search_api.assert_called_once_with("config", service="eda")
        manager.lookup_resource_id.assert_not_called()

    # ---- Check mode tests ----

    def test_check_mode_present_new(self):
        """Check mode for present with no existing project."""
        action = self._make_action(check_mode=True)
        manager = self._make_manager(find_result=None)
        result = self._run_action(
            action,
            manager,
            {
                "name": "my-project",
                "url": "https://example.com/repo.git",
                "state": "present",
                "sync": False,
                "wait": True,
                "update_revision_on_launch": False,
                "scm_update_cache_timeout": 0,
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        calls = [c.kwargs["operation"] for c in manager.execute.call_args_list]
        self.assertNotIn("create", calls)
        self.assertNotIn("update", calls)

    def test_check_mode_absent_existing(self):
        """Check mode for absent with existing project."""
        action = self._make_action(check_mode=True)
        manager = self._make_manager(find_result={"id": 99, "name": "my-project"})
        result = self._run_action(
            action,
            manager,
            {
                "name": "my-project",
                "state": "absent",
                "sync": False,
                "wait": True,
                "update_revision_on_launch": False,
                "scm_update_cache_timeout": 0,
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        calls = [c.kwargs["operation"] for c in manager.execute.call_args_list]
        self.assertNotIn("delete", calls)

    # ---- Sync tests ----

    def test_sync_existing_project(self):
        """Sync triggers POST to sync endpoint."""
        action = self._make_action()
        existing = {"id": 99, "name": "my-project", "description": "desc"}
        manager = self._make_manager(find_result=existing)

        result = self._run_action(
            action,
            manager,
            {
                "name": "my-project",
                "description": "desc",
                "state": "present",
                "sync": True,
                "wait": True,
                "update_revision_on_launch": False,
                "scm_update_cache_timeout": 0,
            },
        )

        self.assertFalse(result.get("failed", False))
        self.assertTrue(result["changed"])
        # Verify sync was triggered with retries disabled (sync is not idempotent)
        manager.launch_resource.assert_called_once_with(launch_url="/api/eda/v1/projects/99/sync/", payload={}, service="eda", retry=False)

    # ---- Validation tests ----

    def test_scm_cache_timeout_requires_update_on_launch(self):
        """scm_update_cache_timeout without update_revision_on_launch fails."""
        action = self._make_action()
        manager = self._make_manager(find_result=None)
        result = self._run_action(
            action,
            manager,
            {
                "name": "my-project",
                "url": "https://example.com/repo.git",
                "state": "present",
                "sync": False,
                "wait": True,
                "update_revision_on_launch": False,
                "scm_update_cache_timeout": 3600,
            },
        )

        self.assertTrue(result["failed"])
        self.assertIn("scm_update_cache_timeout", result["msg"])

    def test_rename_with_new_name(self):
        """Renaming a project with new_name triggers update."""
        action = self._make_action()
        existing = {"id": 99, "name": "old-name"}
        manager = self._make_manager(
            find_result=existing,
            update_result={"id": 99, "name": "new-name", "changed": True},
        )

        result = self._run_action(
            action,
            manager,
            {
                "name": "old-name",
                "new_name": "new-name",
                "state": "present",
                "sync": False,
                "wait": True,
                "update_revision_on_launch": False,
                "scm_update_cache_timeout": 0,
            },
        )

        self.assertFalse(result.get("failed", False))
        calls = [c.kwargs["operation"] for c in manager.execute.call_args_list]
        self.assertIn("update", calls)

    def test_find_reraises_non_not_found_errors(self):
        """ValueError not related to 'not found' is re-raised."""
        action = self._make_action()
        manager = MagicMock()
        manager.lookup_resource_id.side_effect = ValueError("Authentication failed")
        manager.execute.side_effect = ValueError("Authentication failed")
        result = self._run_action(
            action,
            manager,
            {
                "name": "my-project",
                "url": "https://example.com/repo.git",
                "state": "present",
                "sync": False,
                "wait": True,
                "update_revision_on_launch": False,
                "scm_update_cache_timeout": 0,
            },
        )

        self.assertTrue(result["failed"])
        self.assertIn("Authentication failed", result["msg"])

    def test_foreign_key_comparison_uses_canonical_ids(self):
        """Names and numeric ID strings identify the same related resources."""
        action = self._make_action()
        manager = MagicMock()
        manager.lookup_resource_id.side_effect = lambda endpoint, lookup_field, value, **kwargs: {
            "SCM Credential": 42,
            "Default": 7,
        }[value]
        action._client = manager
        action._resolved_fk_ids = {}

        self.assertFalse(
            action._should_update(
                {"credential": "SCM Credential", "organization_name": "Default"},
                {"credential": "42", "organization_name": 7},
            )
        )
        self.assertFalse(
            action._should_update(
                {"credential": "42", "organization_name": "7"},
                {"credential": "SCM Credential", "organization_name": "Default"},
            )
        )


if __name__ == "__main__":
    unittest.main()
