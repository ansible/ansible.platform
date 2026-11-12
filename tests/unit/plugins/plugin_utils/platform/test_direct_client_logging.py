"""Direct-client operation logs omit request payload values."""

import threading
from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.subscriptions import APISubscriptions_v2
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import EndpointOperation, TransformContext


def test_operation_logging_omits_payload_values(caplog):
    """Send credentials to the API without including them in INFO logs."""
    client = DirectHTTPClient.__new__(DirectHTTPClient)
    client.base_url = "https://gateway.example"
    client.api_versions = {"controller": "2"}
    client._lock = threading.Lock()
    client._http_request_count = 0
    client._make_request = MagicMock()
    client._make_request.return_value.read.return_value = b'{"subscriptions": []}'
    client._invalidate_resource_lookup_cache = MagicMock()
    payload = APISubscriptions_v2(subscriptions_client_secret="dummy-subscription-secret")
    operations = {
        "get": EndpointOperation(path="/api/controller/v2/config/subscriptions/", method="POST", fields=["subscriptions_client_secret"], required_for="find")
    }
    context = TransformContext(manager=client, session=None, cache={}, service="controller", api_version="2")

    with caplog.at_level("INFO", logger=DirectHTTPClient.__module__):
        client._execute_operations(operations, payload, context, required_for="find")

    entry = next(record for record in caplog.records if "Executing operations" in record.getMessage())
    assert entry.args == (["get"],)
    assert "dummy-subscription-secret" not in caplog.text
    assert client._make_request.call_args.kwargs["json"] == {"subscriptions_client_secret": "dummy-subscription-secret"}
