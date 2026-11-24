# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Verify transient retry settings at both HTTP transports."""

from io import BytesIO
from unittest.mock import Mock
from urllib.error import HTTPError

import pytest
import requests
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformService
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import APIError
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.retry import RetryConfig

URL = "https://gateway.example/api/controller/v2/job_templates/42/launch/"


@pytest.fixture(params=["manager", "direct"])
def client_and_transport(request, monkeypatch):
    """Construct the client and replace only its startup and wire I/O."""
    monkeypatch.setattr(PlatformService, "_authenticate", lambda self: None)
    monkeypatch.setattr(PlatformService, "get_api_version", lambda self, service: "2")

    def create(config, status):
        if request.param == "manager":
            client = PlatformService(config)
            response = requests.Response()
            response.url = URL
            response.status_code = status
            response._content = b"{}"
            transport = Mock(return_value=response)
            for method in ("get", "post"):
                monkeypatch.setattr(client.session, method, transport)
        else:
            client = DirectHTTPClient(config)
            transport = Mock(side_effect=HTTPError(URL, status, "test error", {}, BytesIO(b"{}")))
            monkeypatch.setattr(client.session, "open", transport)
        return client, transport, request.param

    return create


@pytest.mark.parametrize(
    ("retries", "status", "method", "attempts"),
    [(0, 503, "GET", 1), (2, 503, "GET", 3), (2, 404, "GET", 1), (2, 503, "POST", 1)],
)
def test_configured_request_attempts(client_and_transport, monkeypatch, retries, status, method, attempts):
    config = GatewayConfig(base_url=URL, max_retries=retries, retry_backoff_factor=3)
    client, transport, _ = client_and_transport(config, status)
    sleep = Mock()
    monkeypatch.setattr("time.sleep", sleep)
    monkeypatch.setattr("random.uniform", lambda *_: 0)

    with pytest.raises(APIError):
        client._make_request(method, URL)

    assert transport.call_count == attempts
    assert [call.args[0] for call in sleep.call_args_list] == [1.0, 3.0][: attempts - 1]


def test_unconfigured_attempts_keep_transport_defaults(client_and_transport, monkeypatch):
    client, transport, mode = client_and_transport(GatewayConfig(base_url=URL), 503)
    monkeypatch.setattr("time.sleep", lambda _: None)

    with pytest.raises(APIError):
        client._make_request("GET", URL)

    assert transport.call_count == {"manager": 3, "direct": 1}[mode]


def test_request_override_takes_precedence(client_and_transport):
    client, transport, _ = client_and_transport(GatewayConfig(base_url=URL, max_retries=2), 503)

    with pytest.raises(APIError):
        client._make_request("GET", URL, retry_config=RetryConfig(max_attempts=1))

    assert transport.call_count == 1
