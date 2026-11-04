# (c) 2026 Ansible Platform Collection Contributors

from __future__ import absolute_import, division, print_function

import threading
import unittest
from dataclasses import asdict
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_settings import (
    AnsibleControllerSettings,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.controller_settings import (
    APIControllerSettings_v2,
    ControllerSettingsTransformMixin_v2,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext


class TestControllerSettingsModel(unittest.TestCase):
    def test_defaults(self):
        settings = AnsibleControllerSettings()
        self.assertIsNone(settings.settings)
        self.assertIsNone(settings.old_values)
        self.assertIsNone(settings.new_values)
        self.assertFalse(settings.changed)

    def test_asdict(self):
        settings = AnsibleControllerSettings(settings={"DEFAULT_JOB_TIMEOUT": 3600})
        self.assertEqual(asdict(settings)["settings"]["DEFAULT_JOB_TIMEOUT"], 3600)


class TestControllerSettingsTransformMixin(unittest.TestCase):
    def test_is_singleton_and_has_no_lookup_field(self):
        self.assertTrue(ControllerSettingsTransformMixin_v2.is_singleton)
        self.assertEqual(ControllerSettingsTransformMixin_v2.get_lookup_field(), "")

    def test_endpoint_operations(self):
        operations = ControllerSettingsTransformMixin_v2.get_endpoint_operations()
        self.assertEqual(operations["get"].path, "/api/controller/v2/settings/all/")
        self.assertEqual(operations["get"].method, "GET")
        self.assertEqual(operations["update"].path, "/api/controller/v2/settings/all/")
        self.assertEqual(operations["update"].method, "PATCH")
        self.assertTrue(operations["update"].flatten_body)

    def test_round_trip(self):
        ansible_data = AnsibleControllerSettings(settings={"DEFAULT_JOB_TIMEOUT": 3600})
        api_data = ControllerSettingsTransformMixin_v2.from_ansible_data(ansible_data, {})
        self.assertIsInstance(api_data, APIControllerSettings_v2)
        self.assertEqual(api_data.settings, {"DEFAULT_JOB_TIMEOUT": 3600})

        result = ControllerSettingsTransformMixin_v2.from_api({"DEFAULT_JOB_TIMEOUT": 3600}, {})
        self.assertIsInstance(result, AnsibleControllerSettings)
        self.assertEqual(result.settings, {"DEFAULT_JOB_TIMEOUT": 3600})

    def test_manager_singleton_find_uses_controller_endpoint(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.retry import RetryConfig

        service = PlatformService.__new__(PlatformService)
        service.record_activity = MagicMock()
        service.session = MagicMock()
        service.cache = {}
        service.base_url = "https://controller.example.com"
        service.request_timeout = 30
        service.config = None
        service.verify_ssl = True
        service.ca_bundle = None
        service.api_versions = {"controller": "2"}
        service.registry = MagicMock()
        service.registry.get_supported_versions.return_value = ["2"]
        service.retry_config = RetryConfig(max_attempts=1)
        service._lock = threading.Lock()
        service._http_request_count = 0

        response = MagicMock()
        response.json.return_value = {"DEFAULT_JOB_TIMEOUT": 3600}
        response.raise_for_status.return_value = None
        service._request_with_auth_recovery = MagicMock(return_value=response)

        context = TransformContext(
            manager=service,
            session=service.session,
            cache={},
            api_version="2",
            service="controller",
            operation="find",
        )
        result = service._find_resource(
            AnsibleControllerSettings(settings={}),
            ControllerSettingsTransformMixin_v2,
            context,
        )

        service._request_with_auth_recovery.assert_called_once_with(
            "GET",
            "https://controller.example.com/api/controller/v2/settings/all/",
            operation="find",
            resource="ControllerSettingsTransformMixin_v2",
        )
        self.assertEqual(result["settings"]["DEFAULT_JOB_TIMEOUT"], 3600)

    def test_manager_singleton_update_uses_partial_patch(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService

        service = PlatformService.__new__(PlatformService)
        service._find_resource = MagicMock(return_value={"settings": {"DEFAULT_JOB_TIMEOUT": 0}})
        service._execute_operations = MagicMock(return_value={"DEFAULT_JOB_TIMEOUT": 3600})

        context = TransformContext(
            manager=service,
            session=MagicMock(),
            cache={},
            api_version="2",
            service="controller",
            operation="update",
        )
        result = service._update_resource(
            AnsibleControllerSettings(settings={"DEFAULT_JOB_TIMEOUT": 3600}),
            ControllerSettingsTransformMixin_v2,
            context,
        )

        self.assertEqual(result["settings"]["DEFAULT_JOB_TIMEOUT"], 3600)
        args, kwargs = service._execute_operations.call_args
        self.assertEqual(kwargs["required_for"], "update")
        self.assertEqual(args[1].settings, {"DEFAULT_JOB_TIMEOUT": 3600})


if __name__ == "__main__":
    unittest.main()
