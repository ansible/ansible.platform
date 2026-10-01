# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the service_key action plugin."""

import unittest

from ansible_collections.ansible.platform.plugins.action.service_key import ActionModule


class TestServiceKeyAction(unittest.TestCase):
    def test_deprecated_creation_fields_are_declared(self):
        action = ActionModule.__new__(ActionModule)

        self.assertEqual(
            set(action._DEPRECATED_FIELDS),
            {"service_cluster", "secret", "secret_length", "mark_previous_inactive", "algorithm"},
        )
        for message, version in action._DEPRECATED_FIELDS.values():
            self.assertIn("Gateway no longer permits creating service keys", message)
            self.assertEqual(version, "4.0.0")

    def test_pre_execute_hook_does_not_reinsert_deprecated_creation_fields(self):
        action = ActionModule.__new__(ActionModule)
        ansible_data = {"name": "existing-key", "is_active": True}
        validated_params = {
            "name": "existing-key",
            "is_active": True,
            "service_cluster": "gateway",
            "secret": "secret-value",
            "secret_length": 32,
            "mark_previous_inactive": True,
            "algorithm": "HS256",
        }
        action._pre_execute_hook(ansible_data, {}, validated_params, "create")

        self.assertEqual(ansible_data, {"name": "existing-key", "is_active": True})


if __name__ == "__main__":
    unittest.main()
