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

    def _make_manager(self, find_result=None, create_result=None, update_result=None, delete_error=None):
        manager = MagicMock()

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
        self.assertEqual(calls, ["find", "create"])

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
        existing = {"id": 99, "name": "my-project", "description": "old desc"}
        manager = self._make_manager(
            find_result=existing,
            update_result={"id": 99, "name": "my-project", "description": "new desc", "changed": True},
        )

        result = self._run_action(
            action,
            manager,
            {
                "name": "my-project",
                "description": "new desc",
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
        # Verify sync POST was called
        direct_calls = manager.direct_request.call_args_list
        sync_calls = [c for c in direct_calls if c.args == ("POST", "/api/eda/v1/projects/99/sync/")]
        self.assertEqual(len(sync_calls), 1)

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


if __name__ == "__main__":
    unittest.main()
