"""Tests for EDA credential type API request payloads."""

import threading
import unittest
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.eda_credential_type import (
    APIEdaCredentialType_v1,
    EdaCredentialTypeTransformMixin_v1,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext, build_endpoint_request


class TestEdaCredentialTypeDirectClientPayload(unittest.TestCase):
    """Ensure direct requests preserve explicitly supplied empty values."""

    def test_update_sends_all_explicit_empty_strings(self):
        client = DirectHTTPClient.__new__(DirectHTTPClient)
        client._build_url = MagicMock(return_value="https://gateway.example/api/eda/v1/credential-types/42/")
        client._lock = threading.Lock()
        client._http_request_count = 0
        response = MagicMock()
        response.read.return_value = b'{"id": 42}'
        client._make_request = MagicMock(return_value=response)
        context = TransformContext(
            manager=MagicMock(),
            session=MagicMock(),
            cache={},
            api_version="1",
            service="eda",
            operation="update",
        )
        api_data = APIEdaCredentialType_v1(name="", description="", id=42)

        client._execute_operations(EdaCredentialTypeTransformMixin_v1.get_endpoint_operations(), api_data, context, required_for="update")

        self.assertEqual(client._make_request.call_args.kwargs["json"], {"name": "", "description": ""})

    def test_test_operation_omits_empty_metadata_like_the_previous_action(self):
        test_request = EdaCredentialTypeTransformMixin_v1.to_test_request(42, {"username": "demo"}, {})
        operation = EdaCredentialTypeTransformMixin_v1.get_endpoint_operations()["test"]

        self.assertEqual(
            build_endpoint_request(operation, test_request),
            ("/api/eda/v1/credential-types/42/test/", {"inputs": {"username": "demo"}}),
        )

    def test_test_operation_omits_missing_inputs_like_the_legacy_action(self):
        test_request = EdaCredentialTypeTransformMixin_v1.to_test_request(42, None)
        operation = EdaCredentialTypeTransformMixin_v1.get_endpoint_operations()["test"]

        self.assertEqual(
            build_endpoint_request(operation, test_request),
            ("/api/eda/v1/credential-types/42/test/", {}),
        )


if __name__ == "__main__":
    unittest.main()
