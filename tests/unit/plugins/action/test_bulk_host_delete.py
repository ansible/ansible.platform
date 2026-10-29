# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the bulk_host_delete action plugin."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import unittest
from unittest.mock import MagicMock, patch

from ansible.playbook.task import Task
from ansible_collections.ansible.platform.plugins.action.bulk_host_delete import ActionModule
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.bulk_host_delete import AnsibleBulkHostDelete
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.bulk_host_delete import (
    APIBulkHostDelete_v2,
    BulkHostDeleteTransformMixin_v2,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import APIError


def _make_module(args=None, check_mode=False):
    task = MagicMock(spec=Task)
    task.args = args or {}
    task.check_mode = check_mode
    task.async_val = 0
    task.environment = []
    module = ActionModule(
        task=task,
        connection=MagicMock(),
        play_context=MagicMock(),
        loader=MagicMock(),
        templar=MagicMock(),
        shared_loader_obj=MagicMock(),
    )
    module._display = MagicMock()
    module._display.verbosity = 0
    return module


class TestActionModuleAttributes(unittest.TestCase):
    def test_module_name(self):
        self.assertEqual(_make_module().MODULE_NAME, "bulk_host_delete")

    def test_model_class(self):
        self.assertEqual(_make_module().MODEL_CLASS, AnsibleBulkHostDelete)

    def test_lookup_field(self):
        self.assertEqual(_make_module().LOOKUP_FIELD, "hosts")


class TestCheckMode(unittest.TestCase):
    @patch.object(ActionModule, "_prepare_action")
    def test_check_mode_skips_delete(self, mock_prepare):
        module = _make_module(args={"hosts": [1, 2, 3]}, check_mode=True)
        manager = MagicMock()
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"hosts": [1, 2, 3]},
            "manager": manager,
        }
        result = module.run(task_vars={})
        self.assertTrue(result["changed"])
        self.assertIn("3 host(s)", result["msg"])
        self.assertIn("check mode", result["msg"])
        manager.launch_resource.assert_not_called()


class TestBulkDelete(unittest.TestCase):
    @patch.object(ActionModule, "_prepare_action")
    def test_delete_hosts(self, mock_prepare):
        module = _make_module(args={"hosts": [1, 2, 3]})
        manager = MagicMock()
        manager.launch_resource.return_value = {}
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"hosts": [1, 2, 3]},
            "manager": manager,
        }
        result = module.run(task_vars={})
        self.assertTrue(result["changed"])
        self.assertNotIn("failed", result)
        manager.launch_resource.assert_called_once_with(
            launch_url="/api/controller/v2/bulk/host_delete/",
            payload={"hosts": [1, 2, 3]},
            service="controller",
            retry=False,
        )

    @patch.object(BulkHostDeleteTransformMixin_v2, "from_ansible_data")
    @patch.object(ActionModule, "_prepare_action")
    def test_delete_uses_transform_payload(self, mock_prepare, mock_transform):
        module = _make_module(args={"hosts": [1, 2]})
        manager = MagicMock()
        mock_transform.return_value = APIBulkHostDelete_v2(hosts=[10, 20])
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"hosts": [1, 2]},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertTrue(result["changed"])
        mock_transform.assert_called_once_with(AnsibleBulkHostDelete(hosts=[1, 2]))
        manager.launch_resource.assert_called_once_with(
            launch_url="/api/controller/v2/bulk/host_delete/",
            payload={"hosts": [10, 20]},
            service="controller",
            retry=False,
        )

    @patch.object(ActionModule, "_prepare_action")
    def test_delete_single_host(self, mock_prepare):
        module = _make_module(args={"hosts": [42]})
        manager = MagicMock()
        manager.launch_resource.return_value = {}
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"hosts": [42]},
            "manager": manager,
        }
        result = module.run(task_vars={})
        self.assertTrue(result["changed"])

    @patch.object(ActionModule, "_prepare_action")
    def test_empty_hosts_list(self, mock_prepare):
        module = _make_module(args={"hosts": []})
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"hosts": []},
            "manager": MagicMock(),
        }
        result = module.run(task_vars={})
        self.assertTrue(result["failed"])
        self.assertIn("hosts is required", result["msg"])

    @patch.object(ActionModule, "_prepare_action")
    def test_missing_hosts(self, mock_prepare):
        module = _make_module(args={})
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"hosts": None},
            "manager": MagicMock(),
        }
        result = module.run(task_vars={})
        self.assertTrue(result["failed"])
        self.assertIn("hosts is required", result["msg"])

    @patch.object(ActionModule, "_prepare_action")
    def test_api_error(self, mock_prepare):
        module = _make_module(args={"hosts": [1, 2]})
        manager = MagicMock()
        manager.launch_resource.side_effect = Exception("403 Forbidden")
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"hosts": [1, 2]},
            "manager": manager,
        }
        result = module.run(task_vars={})
        self.assertTrue(result["failed"])
        self.assertIn("403", result["msg"])

    @patch.object(ActionModule, "_prepare_action")
    def test_api_error_includes_structured_response(self, mock_prepare):
        module = _make_module(args={"hosts": [1, 2]})
        manager = MagicMock()
        manager.launch_resource.side_effect = APIError(
            message="API request failed: HTTP 400",
            details={"status_code": 400, "response_body": b'{"hosts": ["Invalid host ID"]}'},
            status_code=400,
        )
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"hosts": [1, 2]},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertEqual(
            result,
            {
                "failed": True,
                "msg": "API request failed: HTTP 400",
                "response": {"status_code": 400, "json": {"hosts": ["Invalid host ID"]}},
            },
        )

    @patch.object(ActionModule, "_prepare_action")
    def test_api_error_preserves_plain_text_response(self, mock_prepare):
        module = _make_module(args={"hosts": [1]})
        manager = MagicMock()
        manager.launch_resource.side_effect = APIError(
            message="API request failed: HTTP 400",
            details={"status_code": 400, "response_body": "Invalid host ID"},
            status_code=400,
        )
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"hosts": [1]},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertEqual(
            result,
            {
                "failed": True,
                "msg": "API request failed: HTTP 400",
                "response": {"status_code": 400, "text": "Invalid host ID"},
            },
        )

    @patch.object(ActionModule, "_prepare_action")
    def test_http_error_includes_response_body(self, mock_prepare):
        module = _make_module(args={"hosts": [1]})
        manager = MagicMock()
        http_error = Exception("403 Forbidden")
        http_error.response = MagicMock(status_code=403)
        http_error.response.json.return_value = {"detail": "Permission denied"}
        manager.launch_resource.side_effect = http_error
        mock_prepare.return_value = {
            "result": {},
            "validated_params": {"hosts": [1]},
            "manager": manager,
        }

        result = module.run(task_vars={})

        self.assertEqual(
            result,
            {
                "failed": True,
                "msg": "403 Forbidden",
                "response": {"status_code": 403, "json": {"detail": "Permission denied"}},
            },
        )


class TestAnsibleModel(unittest.TestCase):
    def test_defaults(self):
        model = AnsibleBulkHostDelete()
        self.assertEqual(model.hosts, [])

    def test_construction(self):
        model = AnsibleBulkHostDelete(hosts=[1, 2, 3])
        self.assertEqual(model.hosts, [1, 2, 3])

    def test_round_trip(self):
        from dataclasses import asdict

        model = AnsibleBulkHostDelete(hosts=[10, 20, 30])
        d = asdict(model)
        reconstructed = AnsibleBulkHostDelete(**d)
        self.assertEqual(reconstructed, model)


class TestTransformMixin(unittest.TestCase):
    def test_from_ansible_data(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.bulk_host_delete import (
            APIBulkHostDelete_v2,
            BulkHostDeleteTransformMixin_v2,
        )

        ansible_data = AnsibleBulkHostDelete(hosts=[1, 2, 3])
        api_data = BulkHostDeleteTransformMixin_v2.from_ansible_data(ansible_data, MagicMock())
        self.assertIsInstance(api_data, APIBulkHostDelete_v2)
        self.assertEqual(api_data.hosts, [1, 2, 3])

    def test_from_api(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.bulk_host_delete import (
            BulkHostDeleteTransformMixin_v2,
        )

        ansible_data = BulkHostDeleteTransformMixin_v2.from_api({"hosts": [4, 5, 6]}, MagicMock())
        self.assertIsInstance(ansible_data, AnsibleBulkHostDelete)
        self.assertEqual(ansible_data.hosts, [4, 5, 6])

    def test_get_lookup_field(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.bulk_host_delete import (
            BulkHostDeleteTransformMixin_v2,
        )

        self.assertEqual(BulkHostDeleteTransformMixin_v2.get_lookup_field(), "hosts")

    def test_endpoint_operations(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.bulk_host_delete import (
            BulkHostDeleteTransformMixin_v2,
        )

        ops = BulkHostDeleteTransformMixin_v2.get_endpoint_operations()
        self.assertIn("create", ops)
        self.assertIn("bulk/host_delete", ops["create"].path)
        self.assertEqual(ops["create"].fields, ["hosts"])


if __name__ == "__main__":
    unittest.main()
