# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for structured platform error classification."""

import requests
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import APIError, classify_exception


def test_http_error_preserves_status_code_for_action_plugins():
    response = requests.Response()
    response.status_code = 404
    response.url = "https://gateway.example.com/api/controller/v2/jobs/42/"
    response._content = b"not found"
    error = requests.exceptions.HTTPError("404 Client Error", response=response)

    classified = classify_exception(error, operation="find", resource="job_wait")

    assert isinstance(classified, APIError)
    assert classified.status_code == 404
    assert classified.details["status_code"] == 404


def test_http_error_without_response_returns_api_error_with_no_status():
    error = requests.exceptions.HTTPError("request failed without a response")

    classified = classify_exception(error, operation="find", resource="job_wait")

    assert isinstance(classified, APIError)
    assert classified.status_code is None
    assert classified.details["status_code"] is None
