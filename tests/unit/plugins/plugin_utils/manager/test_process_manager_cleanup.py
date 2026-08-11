# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for ProcessManager.terminate_manager_process() and the _process
attribute stored by spawn_ephemeral_client().

Run with pytest from collection root:
  pytest tests/unit/plugins/plugin_utils/manager/test_process_manager_cleanup.py -v
"""

from __future__ import absolute_import, division, print_function

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import ProcessManager

# ---------------------------------------------------------------------------
# terminate_manager_process
# ---------------------------------------------------------------------------


class TestTerminateManagerProcess(unittest.TestCase):

    def test_noop_when_process_is_none(self):
        """None process must not raise."""
        ProcessManager.terminate_manager_process(None)

    def test_noop_when_process_already_exited(self):
        """Process that has already exited must not send signals."""
        proc = MagicMock()
        proc.poll.return_value = 0  # already dead

        ProcessManager.terminate_manager_process(proc)

        proc.terminate.assert_not_called()
        proc.kill.assert_not_called()

    def test_graceful_sigterm_when_process_exits_in_time(self):
        """Running process that exits within timeout: only SIGTERM, no SIGKILL."""
        proc = MagicMock()
        proc.poll.return_value = None  # still running
        proc.wait.return_value = 0     # exits cleanly within timeout

        ProcessManager.terminate_manager_process(proc, timeout=5)

        proc.terminate.assert_called_once()
        proc.wait.assert_called_once_with(timeout=5)
        proc.kill.assert_not_called()

    def test_escalates_to_sigkill_on_timeout(self):
        """When SIGTERM doesn't work within timeout, SIGKILL is sent."""
        proc = MagicMock()
        proc.poll.return_value = None
        proc.wait.side_effect = [subprocess.TimeoutExpired([], 5), None]

        ProcessManager.terminate_manager_process(proc, timeout=5)

        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()
        assert proc.wait.call_count == 2

    def test_sigkill_fallback_on_unexpected_exception(self):
        """If terminate() raises an unexpected exception, kill() is still attempted."""
        proc = MagicMock()
        proc.poll.return_value = None
        proc.terminate.side_effect = OSError("unexpected")

        # Should not propagate — kill fallback runs instead
        ProcessManager.terminate_manager_process(proc, timeout=5)

        proc.kill.assert_called_once()

    def test_default_timeout_is_five_seconds(self):
        """Default timeout passed to wait() is 5."""
        proc = MagicMock()
        proc.poll.return_value = None
        proc.wait.return_value = 0

        ProcessManager.terminate_manager_process(proc)

        proc.wait.assert_called_once_with(timeout=5)


# ---------------------------------------------------------------------------
# spawn_ephemeral_client — _process attribute
# ---------------------------------------------------------------------------


class TestSpawnEphemeralClientStoresProcess(unittest.TestCase):

    def _make_gateway_config(self):
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig

        return GatewayConfig(base_url="https://gateway.test.invalid", username="admin", password="secret")

    def test_process_attribute_set_on_returned_client(self):
        """spawn_ephemeral_client must store the Popen handle as client._process."""
        fake_process = MagicMock()
        fake_process.pid = 99999
        fake_client = MagicMock()
        fake_client._ephemeral = True

        with patch(
            "ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager._af_unix_available",
            return_value=True,
        ), patch(
            "ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager.ProcessManager.generate_connection_info"
        ) as mock_conn_info, patch(
            "ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager.ProcessManager.cleanup_old_socket"
        ), patch(
            "ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager.ProcessManager.spawn_manager_process",
            return_value=fake_process,
        ), patch(
            "ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager.ProcessManager.wait_for_process_startup"
        ), patch(
            "ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client.ManagerRPCClient",
            return_value=fake_client,
        ):
            mock_conn_info.return_value = MagicMock(socket_path="/tmp/ap/test.sock", authkey=b"x" * 32, authkey_b64="abc")

            from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import spawn_ephemeral_client

            client, facts = spawn_ephemeral_client({}, self._make_gateway_config())

        assert facts is None
        assert hasattr(client, "_process"), "client._process must be set by spawn_ephemeral_client"
        assert client._process is fake_process

    def test_no_process_attribute_on_direct_http_fallback(self):
        """When AF_UNIX is unavailable, DirectHTTPClient is returned with no _process."""
        with patch(
            "ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager._af_unix_available",
            return_value=False,
        ), patch(
            "ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client.DirectHTTPClient"
        ) as MockDirect:
            fake_direct = MagicMock(spec=[])  # no attributes pre-defined
            MockDirect.return_value = fake_direct

            from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import spawn_ephemeral_client

            client, facts = spawn_ephemeral_client({}, self._make_gateway_config())

        assert not hasattr(client, "_process"), "DirectHTTPClient path must not set _process"


if __name__ == "__main__":
    unittest.main()
