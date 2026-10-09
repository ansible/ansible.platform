# (c) 2025 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the bulk_host_create action plugin."""

import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.ansible.platform.plugins.action.bulk_host_create import ActionModule


class TestBulkHostCreateAction(unittest.TestCase):
    def _make_action(self, check_mode=False):
        action = ActionModule.__new__(ActionModule)
        action._task = MagicMock()
        action._task.check_mode = check_mode
        action._display = MagicMock()
        action._display.verbosity = 0
        return action

    def test_successful_bulk_create(self):
        action = self._make_action()
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 42
        manager.bulk_host_create.return_value = {"id": 1}

        hosts = [
            {"name": "host1.example.com", "description": "First"},
            {"name": "host2.example.com"},
        ]
        prepared = {
            "result": {},
            "argspec": {"argument_spec": {"inventory": {}, "hosts": {}}},
            "validated_params": {"inventory": "My Inventory", "hosts": hosts},
            "resource_data": {"inventory": "My Inventory", "hosts": hosts},
            "write_only_data": {},
            "manager": manager,
        }

        with patch.object(action, "_prepare_action", return_value=prepared):
            result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertFalse(result.get("failed", False))
        manager.lookup_resource_id.assert_called_once_with("inventories", "name", "My Inventory", service="controller")
        manager.bulk_host_create.assert_called_once_with(
            inventory_id=42,
            hosts=[
                {"name": "host1.example.com", "description": "First"},
                {"name": "host2.example.com"},
            ],
            service="controller",
        )

    def test_check_mode_short_circuits(self):
        action = self._make_action(check_mode=True)
        manager = MagicMock()

        hosts = [{"name": "host1.example.com"}]
        prepared = {
            "result": {},
            "argspec": {"argument_spec": {"inventory": {}, "hosts": {}}},
            "validated_params": {"inventory": "TestInv", "hosts": hosts},
            "resource_data": {"inventory": "TestInv", "hosts": hosts},
            "write_only_data": {},
            "manager": manager,
        }

        with patch.object(action, "_prepare_action", return_value=prepared):
            result = action.run(task_vars={})

        self.assertTrue(result["changed"])
        self.assertFalse(result.get("failed", False))
        self.assertIn("Would create 1 host(s)", result["msg"])
        manager.lookup_resource_id.assert_not_called()
        manager.bulk_host_create.assert_not_called()

    def test_variables_serialized_to_json(self):
        action = self._make_action()
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 10
        manager.bulk_host_create.return_value = {}

        hosts = [
            {"name": "h1", "variables": {"ansible_host": "1.2.3.4", "foo": "bar"}},
            {"name": "h2"},
        ]
        prepared = {
            "result": {},
            "argspec": {"argument_spec": {"inventory": {}, "hosts": {}}},
            "validated_params": {"inventory": "inv1", "hosts": hosts},
            "resource_data": {"inventory": "inv1", "hosts": hosts},
            "write_only_data": {},
            "manager": manager,
        }

        with patch.object(action, "_prepare_action", return_value=prepared):
            action.run(task_vars={})

        call_args = manager.bulk_host_create.call_args
        submitted_hosts = call_args.kwargs["hosts"]
        self.assertIsInstance(submitted_hosts[0]["variables"], str)
        self.assertIn("ansible_host", submitted_hosts[0]["variables"])
        self.assertNotIn("variables", submitted_hosts[1])

    def test_inventory_by_id(self):
        action = self._make_action()
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 99
        manager.bulk_host_create.return_value = {}

        hosts = [{"name": "h1"}]
        prepared = {
            "result": {},
            "argspec": {"argument_spec": {"inventory": {}, "hosts": {}}},
            "validated_params": {"inventory": "99", "hosts": hosts},
            "resource_data": {"inventory": "99", "hosts": hosts},
            "write_only_data": {},
            "manager": manager,
        }

        with patch.object(action, "_prepare_action", return_value=prepared):
            result = action.run(task_vars={})

        self.assertFalse(result.get("failed", False))
        manager.lookup_resource_id.assert_called_once_with("inventories", "name", "99", service="controller")

    def test_api_error_reported(self):
        action = self._make_action()
        manager = MagicMock()
        manager.lookup_resource_id.return_value = 42
        manager.bulk_host_create.side_effect = ValueError("Bulk host create failed (HTTP 400): bad request")

        hosts = [{"name": "h1"}]
        prepared = {
            "result": {},
            "argspec": {"argument_spec": {"inventory": {}, "hosts": {}}},
            "validated_params": {"inventory": "inv1", "hosts": hosts},
            "resource_data": {"inventory": "inv1", "hosts": hosts},
            "write_only_data": {},
            "manager": manager,
        }

        with patch.object(action, "_prepare_action", return_value=prepared):
            result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("Bulk host create failed", result["msg"])

    def test_inventory_not_found_error(self):
        action = self._make_action()
        manager = MagicMock()
        manager.lookup_resource_id.side_effect = ValueError("Resource 'inventories' with name=nonexistent not found")

        hosts = [{"name": "h1"}]
        prepared = {
            "result": {},
            "argspec": {"argument_spec": {"inventory": {}, "hosts": {}}},
            "validated_params": {"inventory": "nonexistent", "hosts": hosts},
            "resource_data": {"inventory": "nonexistent", "hosts": hosts},
            "write_only_data": {},
            "manager": manager,
        }

        with patch.object(action, "_prepare_action", return_value=prepared):
            result = action.run(task_vars={})

        self.assertTrue(result["failed"])
        self.assertIn("not found", result["msg"])


if __name__ == "__main__":
    unittest.main()
