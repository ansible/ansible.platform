# (c) 2025 Ansible Platform Collection Contributors
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import unittest
from dataclasses import asdict

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.subscriptions import (
    AnsibleSubscriptions,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.subscriptions import (
    APISubscriptions_v2,
    SubscriptionsTransformMixin_v2,
)


class TestAnsibleSubscriptions(unittest.TestCase):
    """Tests for the AnsibleSubscriptions dataclass."""

    def test_defaults(self):
        obj = AnsibleSubscriptions()
        self.assertIsNone(obj.username)
        self.assertIsNone(obj.password)
        self.assertIsNone(obj.client_id)
        self.assertIsNone(obj.client_secret)
        self.assertEqual(obj.filters, {})
        self.assertEqual(obj.subscriptions, [])

    def test_with_username_password(self):
        obj = AnsibleSubscriptions(username="admin", password="secret")
        self.assertEqual(obj.username, "admin")
        self.assertEqual(obj.password, "secret")

    def test_with_client_credentials(self):
        obj = AnsibleSubscriptions(client_id="my-id", client_secret="my-secret")
        self.assertEqual(obj.client_id, "my-id")
        self.assertEqual(obj.client_secret, "my-secret")

    def test_asdict(self):
        obj = AnsibleSubscriptions(username="admin", password="secret", filters={"product_name": "AAP"})
        d = asdict(obj)
        self.assertEqual(d["username"], "admin")
        self.assertEqual(d["password"], "secret")
        self.assertEqual(d["filters"], {"product_name": "AAP"})
        self.assertIsNone(d["client_id"])
        self.assertEqual(d["subscriptions"], [])


class TestAPISubscriptions(unittest.TestCase):
    """Tests for the API dataclass."""

    def test_defaults(self):
        obj = APISubscriptions_v2()
        self.assertIsNone(obj.subscriptions_username)
        self.assertIsNone(obj.subscriptions_password)
        self.assertIsNone(obj.subscriptions_client_id)
        self.assertIsNone(obj.subscriptions_client_secret)

    def test_with_username(self):
        obj = APISubscriptions_v2(
            subscriptions_username="admin",
            subscriptions_password="secret",
        )
        self.assertEqual(obj.subscriptions_username, "admin")
        self.assertEqual(obj.subscriptions_password, "secret")


class TestSubscriptionsTransformMixin(unittest.TestCase):
    """Tests for the transform mixin."""

    def test_is_singleton(self):
        self.assertTrue(SubscriptionsTransformMixin_v2.is_singleton)

    def test_get_lookup_field_empty(self):
        self.assertEqual(SubscriptionsTransformMixin_v2.get_lookup_field(), "")

    def test_endpoint_operations(self):
        ops = SubscriptionsTransformMixin_v2.get_endpoint_operations()
        self.assertIn("get", ops)
        get_op = ops["get"]
        self.assertEqual(get_op.path, "/api/controller/v2/config/subscriptions/")
        self.assertEqual(get_op.method, "POST")
        self.assertEqual(get_op.required_for, "find")

    def test_from_ansible_data_username(self):
        ansible_obj = AnsibleSubscriptions(username="admin", password="secret")
        api_obj = SubscriptionsTransformMixin_v2.from_ansible_data(ansible_obj, {})
        self.assertIsInstance(api_obj, APISubscriptions_v2)
        self.assertEqual(api_obj.subscriptions_username, "admin")
        self.assertEqual(api_obj.subscriptions_password, "secret")
        self.assertIsNone(api_obj.subscriptions_client_id)

    def test_from_ansible_data_client_id(self):
        ansible_obj = AnsibleSubscriptions(client_id="cid", client_secret="csec")
        api_obj = SubscriptionsTransformMixin_v2.from_ansible_data(ansible_obj, {})
        self.assertIsInstance(api_obj, APISubscriptions_v2)
        self.assertEqual(api_obj.subscriptions_client_id, "cid")
        self.assertEqual(api_obj.subscriptions_client_secret, "csec")
        self.assertIsNone(api_obj.subscriptions_username)

    def test_from_api_list(self):
        api_data = [
            {"id": 1, "product_name": "AAP", "support_level": "Premium"},
            {"id": 2, "product_name": "AAP", "support_level": "Self-Support"},
        ]
        result = SubscriptionsTransformMixin_v2.from_api(api_data, {})
        self.assertIsInstance(result, AnsibleSubscriptions)
        self.assertEqual(len(result.subscriptions), 2)
        self.assertEqual(result.subscriptions[0]["product_name"], "AAP")

    def test_from_api_dict(self):
        api_data = {"id": 1, "product_name": "AAP"}
        result = SubscriptionsTransformMixin_v2.from_api(api_data, {})
        self.assertIsInstance(result, AnsibleSubscriptions)
        self.assertEqual(len(result.subscriptions), 1)

    def test_from_api_empty(self):
        result = SubscriptionsTransformMixin_v2.from_api([], {})
        self.assertIsInstance(result, AnsibleSubscriptions)
        self.assertEqual(result.subscriptions, [])


class TestSubscriptionsSingletonFind(unittest.TestCase):
    """Test that the singleton find path sends POST with credentials."""

    def test_platform_service_singleton_find_posts_credentials(self):
        import threading

        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.retry import RetryConfig

        svc = PlatformService.__new__(PlatformService)
        svc.record_activity = unittest.mock.MagicMock()
        svc.session = unittest.mock.MagicMock()
        svc.cache = {}
        svc.base_url = "https://gw.example.com"
        svc.request_timeout = 30
        svc.config = None
        svc.verify_ssl = True
        svc.ca_bundle = None
        svc.api_versions = {"controller": "2"}
        svc.registry = unittest.mock.MagicMock()
        svc.registry.get_supported_versions.return_value = ["2"]
        svc.retry_config = RetryConfig(max_attempts=1)
        svc._lock = threading.Lock()
        svc._http_request_count = 0
        svc._handle_auth_error = unittest.mock.MagicMock(return_value=False)

        mock_resp = unittest.mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"id": 1, "product_name": "AAP"}]
        svc.session.post.return_value = mock_resp

        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext

        context = TransformContext(manager=svc, session=svc.session, cache={}, api_version="2", service="controller", operation="find")
        ansible_data = AnsibleSubscriptions(username="admin", password="secret")
        result = svc._find_resource(ansible_data, SubscriptionsTransformMixin_v2, context)

        svc.session.post.assert_called_once()
        call_kwargs = svc.session.post.call_args
        self.assertIn("json", call_kwargs.kwargs)
        payload = call_kwargs.kwargs["json"]
        self.assertEqual(payload["subscriptions_username"], "admin")
        self.assertEqual(payload["subscriptions_password"], "secret")
        self.assertIn("subscriptions", result)

    def test_direct_client_singleton_find_posts_credentials(self):
        import json as json_mod
        import threading

        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient

        client = DirectHTTPClient.__new__(DirectHTTPClient)
        client._authenticated = True
        client.base_url = "https://gw.example.com"
        client.cache = {}
        client.api_versions = {"controller": "2"}
        client.api_version = "2"
        client.session = unittest.mock.MagicMock()
        client.session.headers = {}
        client._lock = threading.Lock()
        client._http_request_count = 0

        mock_resp = unittest.mock.MagicMock()
        mock_resp.read.return_value = json_mod.dumps([{"id": 1, "product_name": "AAP"}]).encode()
        client._make_request = unittest.mock.MagicMock(return_value=mock_resp)

        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext

        context = TransformContext(manager=client, session=client.session, cache={}, api_version="2", service="controller", operation="find")
        ansible_data = AnsibleSubscriptions(client_id="cid", client_secret="csec")
        result = client._find_resource(ansible_data, SubscriptionsTransformMixin_v2, context)

        client._make_request.assert_called_once()
        call_kwargs = client._make_request.call_args
        self.assertEqual(call_kwargs.args[0], "POST")
        self.assertIn("json", call_kwargs.kwargs)
        payload = call_kwargs.kwargs["json"]
        self.assertEqual(payload["subscriptions_client_id"], "cid")
        self.assertEqual(payload["subscriptions_client_secret"], "csec")
        self.assertIn("subscriptions", result)


class TestSubscriptionsActionValidation(unittest.TestCase):
    """Test action plugin argspec constraints via real docs-based validation."""

    def _build_argspec(self):
        from ansible_collections.ansible.platform.plugins.action.subscriptions import ActionModule

        action = ActionModule.__new__(ActionModule)
        action._display = unittest.mock.MagicMock()
        doc = action._get_documentation()
        return action._build_argspec_from_docs(doc)

    def test_no_log_applied_to_password_and_client_secret(self):
        argspec = self._build_argspec()
        opts = argspec["argument_spec"]
        self.assertTrue(opts["password"].get("no_log"), "password should have no_log=True")
        self.assertTrue(opts["client_secret"].get("no_log"), "client_secret should have no_log=True")

    def test_mutually_exclusive_username_client_id(self):
        argspec = self._build_argspec()
        self.assertIn(["username", "client_id"], argspec["mutually_exclusive"])

    def test_required_together_pairs(self):
        argspec = self._build_argspec()
        self.assertIn(["username", "password"], argspec["required_together"])
        self.assertIn(["client_id", "client_secret"], argspec["required_together"])

    def test_required_one_of_credential_type(self):
        argspec = self._build_argspec()
        self.assertIn(["username", "client_id"], argspec["required_one_of"])


if __name__ == "__main__":
    unittest.main()
