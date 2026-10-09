"""Unit tests for controller_job_wait transform mixin and SDK wait_for_resource."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest.mock import MagicMock

from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.controller_job_wait import AnsibleControllerJobWait
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.controller_job_wait import (
    APIControllerJobWait_v2,
    ControllerJobWaitTransformMixin_v2,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.exceptions import (
    DEFAULT_WAIT_INTERVAL,
    DEFAULT_WAIT_TIMEOUT,
    FAILURE_STATUSES,
    TERMINAL_STATUSES,
    WaitTimeoutError,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import TransformContext


class TestAnsibleControllerJobWait:
    """Verify the AnsibleControllerJobWait dataclass."""

    def test_defaults(self):
        instance = AnsibleControllerJobWait()
        assert instance.job_id == 0
        assert instance.job_type == "jobs"
        assert instance.interval == 2.0
        assert instance.timeout is None

    def test_custom(self):
        instance = AnsibleControllerJobWait(job_id=42, job_type="workflow_jobs", timeout=300, interval=5.0)
        assert instance.job_id == 42
        assert instance.job_type == "workflow_jobs"
        assert instance.timeout == 300
        assert instance.interval == 5.0


class TestTransformMixin:
    """Verify from_ansible_data and from_api round-trip."""

    def test_from_ansible_data(self):
        ansible_instance = AnsibleControllerJobWait(job_id=99, id=99)
        context = MagicMock(spec=TransformContext)
        api = ControllerJobWaitTransformMixin_v2.from_ansible_data(ansible_instance, context)
        assert isinstance(api, APIControllerJobWait_v2)
        assert api.id == 99

    def test_from_api(self):
        api_data = {
            "id": 99,
            "status": "successful",
            "elapsed": 10.5,
            "started": "2025-01-01T00:00:00Z",
            "finished": "2025-01-01T00:00:10Z",
        }
        context = MagicMock(spec=TransformContext)
        result = ControllerJobWaitTransformMixin_v2.from_api(api_data, context)
        assert isinstance(result, AnsibleControllerJobWait)
        assert result.id == 99
        assert result.status == "successful"
        assert result.elapsed == 10.5

    def test_get_lookup_field(self):
        assert ControllerJobWaitTransformMixin_v2.get_lookup_field() == "job_id"

    def test_endpoint_operations(self):
        ops = ControllerJobWaitTransformMixin_v2.get_endpoint_operations()
        assert "get" in ops
        assert ops["get"].path == "/api/controller/v2/jobs/{id}/"
        assert ops["get"].method == "GET"


class TestWaitTimeoutError:
    """Verify WaitTimeoutError carries last_result."""

    def test_basic(self):
        exc = WaitTimeoutError(
            message="timed out",
            last_result={"id": 1, "status": "running"},
            timeout_seconds=60,
        )
        assert exc.last_result == {"id": 1, "status": "running"}
        assert exc.timeout_seconds == 60
        assert "timed out" in str(exc)

    def test_empty_last_result(self):
        exc = WaitTimeoutError(message="timed out")
        assert exc.last_result == {}


class TestExceptionConstants:
    """Verify shared constants."""

    def test_terminal_statuses(self):
        assert "successful" in TERMINAL_STATUSES
        assert "failed" in TERMINAL_STATUSES
        assert "error" in TERMINAL_STATUSES
        assert "canceled" in TERMINAL_STATUSES

    def test_failure_statuses_subset_of_terminal(self):
        assert FAILURE_STATUSES.issubset(TERMINAL_STATUSES)

    def test_defaults(self):
        assert DEFAULT_WAIT_TIMEOUT == 3600.0
        assert DEFAULT_WAIT_INTERVAL == 2.0
