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


if __name__ == "__main__":
    unittest.main()
