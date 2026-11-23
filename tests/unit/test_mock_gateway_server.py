# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for the mock Gateway HTTP server."""

from __future__ import annotations

import unittest
import uuid
from unittest.mock import MagicMock

from tools.mock_gateway_server import MockGatewayHandler


class TestMockSubscriptionsRequest(unittest.TestCase):
    """Validate payloads accepted by the mock subscriptions endpoint."""

    @staticmethod
    def _handler(payload):
        handler = MockGatewayHandler.__new__(MockGatewayHandler)
        handler.path = "/api/controller/v2/config/subscriptions/"
        handler.command = "POST"
        handler._require_auth = MagicMock(return_value=True)
        handler._parse_json_body = MagicMock(return_value=payload)
        handler._send_json = MagicMock()
        return handler

    def test_non_object_json_payload_returns_bad_request(self):
        for payload in ([], "value", 42, None):
            with self.subTest(payload=payload):
                handler = self._handler(payload)

                handler._route()

                handler._send_json.assert_called_once_with(400, {"detail": "Expected a JSON object"})

    def test_json_parse_error_still_returns_bad_request(self):
        handler = self._handler({})
        handler._parse_json_body.side_effect = ValueError("Invalid JSON")

        handler._route()

        handler._send_json.assert_called_once_with(400, {"detail": "Invalid JSON"})

    def test_client_credentials_require_a_nonempty_secret_and_exact_keys(self):
        valid_credentials = {
            "subscriptions_client_id": "mock-subscription-client",
            "subscriptions_client_secret": uuid.uuid4().hex,
        }
        handler = self._handler(valid_credentials)

        handler._route()

        self.assertEqual(handler._send_json.call_args.args[0], 200)

        invalid_payloads = (
            {**valid_credentials, "subscriptions_client_secret": ""},
            {**valid_credentials, "subscriptions_client_secret": True},
            {**valid_credentials, "unexpected": "extra"},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                handler = self._handler(payload)

                handler._route()

                handler._send_json.assert_called_once_with(400, {"detail": "Unexpected mock subscription credentials"})

    def test_username_credentials_require_a_valid_user_a_nonempty_password_and_exact_keys(self):
        valid_credentials = {
            "subscriptions_username": "mock-subscription-user",
            "subscriptions_password": uuid.uuid4().hex,
        }
        handler = self._handler(valid_credentials)

        handler._route()

        self.assertEqual(handler._send_json.call_args.args[0], 200)

        invalid_payloads = (
            {**valid_credentials, "subscriptions_username": "invalid-subscription-user"},
            {**valid_credentials, "subscriptions_password": ""},
            {**valid_credentials, "unexpected": "extra"},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                handler = self._handler(payload)

                handler._route()

                handler._send_json.assert_called_once_with(400, {"detail": "Unexpected mock subscription credentials"})


if __name__ == "__main__":
    unittest.main()
