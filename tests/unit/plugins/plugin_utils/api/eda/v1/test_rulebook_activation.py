# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for the EDA rulebook activation transform."""

import unittest
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.rulebook_activation import AnsibleRulebookActivation
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.rulebook_activation import RulebookActivationTransformMixin_v1


class TestRulebookActivationTransform(unittest.TestCase):
    """Verify rulebook activation API update field mappings."""

    def test_update_operation_includes_mutable_api_fields(self):
        fields = RulebookActivationTransformMixin_v1.get_endpoint_operations()["update"].fields

        self.assertIn("extra_var", fields)
        self.assertIn("awx_token_id", fields)
        self.assertIn("source_mappings", fields)

    def test_update_transforms_awx_token_and_event_streams(self):
        manager = MagicMock()
        manager.lookup_resource_id.side_effect = [13, 41]
        manager.search_api.return_value = {"results": [{"name": "source", "rulebook_hash": "hash"}]}
        activation = AnsibleRulebookActivation(
            name="activation",
            extra_vars="answer: 42",
            awx_token_name="controller-token",
            event_streams=[{"event_stream": "stream", "source_name": "source"}],
            rulebook_id=7,
        )

        api = RulebookActivationTransformMixin_v1.from_ansible_data(activation, {"manager": manager, "operation": "update"})

        self.assertEqual(api.extra_var, "answer: 42")
        self.assertEqual(api.awx_token_id, 13)
        self.assertIn("event_stream_id: 41", api.source_mappings)
        self.assertIn("source_name: source", api.source_mappings)

    def test_from_api_exposes_mutable_fields_for_idempotency_comparison(self):
        activation = RulebookActivationTransformMixin_v1.from_api(
            {
                "id": 42,
                "name": "activation",
                "rulebook_id": 7,
                "awx_token_id": 13,
                "source_mappings": "- event_stream_id: 41",
                "extra_var": "answer: 42",
            },
            {},
        )

        self.assertEqual(activation.rulebook_id, 7)
        self.assertEqual(activation.extra_var, "answer: 42")
        self.assertEqual(activation.extra_vars, "answer: 42")
        self.assertEqual(activation.awx_token_id, 13)
        self.assertEqual(activation.source_mappings, "- event_stream_id: 41")

    def test_missing_awx_token_fails_resolution(self):
        manager = MagicMock()
        manager.lookup_resource_id.return_value = None

        with self.assertRaisesRegex(ValueError, "AWX token 'missing-token' not found"):
            RulebookActivationTransformMixin_v1.from_ansible_data(
                AnsibleRulebookActivation(name="activation", awx_token_name="missing-token"),
                {"manager": manager},
            )

    def test_reference_fields_require_manager(self):
        with self.assertRaisesRegex(ValueError, "A manager is required to resolve rulebook activation references"):
            RulebookActivationTransformMixin_v1.from_ansible_data(
                AnsibleRulebookActivation(name="activation", awx_token_name="token"),
                {},
            )

    def test_missing_eda_credential_fails_resolution(self):
        manager = MagicMock()
        manager.lookup_resource_id.return_value = None

        with self.assertRaisesRegex(ValueError, "EDA credential 'missing-credential' not found"):
            RulebookActivationTransformMixin_v1.from_ansible_data(
                AnsibleRulebookActivation(name="activation", eda_credentials=["missing-credential"]),
                {"manager": manager},
            )

    def test_rulebook_name_requires_project(self):
        with self.assertRaisesRegex(ValueError, "Project is required when rulebook_name is provided"):
            RulebookActivationTransformMixin_v1.from_ansible_data(
                AnsibleRulebookActivation(name="activation", rulebook_name="rules.yml"),
                {"manager": MagicMock()},
            )

    def test_event_streams_require_resolved_rulebook(self):
        manager = MagicMock()

        with self.assertRaisesRegex(ValueError, "A resolved rulebook is required when event_streams are provided"):
            RulebookActivationTransformMixin_v1.from_ansible_data(
                AnsibleRulebookActivation(name="activation", event_streams=[{"event_stream": "stream", "source_name": "source"}]),
                {"manager": manager},
            )

        manager.search_api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
