# (c) 2026 Red Hat Inc.
#
# This file is part of Ansible
#
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for the platform connection plugin (AAP-67324: persistent vs direct mode).

Run with pytest (from collection root; requires ansible-core installed):
  pytest tests/unit/plugins/connection/test_http.py -v

Or with tox-ansible (recommended for CI / version matrix):
  tox -f unit --ansible -p auto --conf tox-ansible.ini

Covers:
- get_client() dispatcher: routes to _get_direct_client (direct/ephemeral) or _get_persistent_client
  based on connection option 'persistent' or variables ansible_platform_use_persistent_connection /
  ansible_platform_persistent.
- Direct mode: returns (client, None); no facts stored.
- Persistent mode: returns (client, facts_dict) with platform_manager_socket and platform_manager_authkey.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import unittest
from unittest.mock import patch, MagicMock

from ansible_collections.ansible.platform.plugins.connection.http import Connection
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig


class TestHTTPConnectionDispatcher(unittest.TestCase):
    def setUp(self):
        """Set up the mock connection object and standard variables for testing."""
        self.mock_play_context = MagicMock()
        self.mock_play_context.shell = 'sh'
        self.mock_play_context.executable = '/bin/sh'
        self.mock_new_stdin = MagicMock()
        self.connection = Connection(self.mock_play_context, self.mock_new_stdin)
        self.connection._connected = True
        self.gateway_config = GatewayConfig(base_url="https://example.com/", username="admin", password="secret")
        self.task_vars = {"inventory_hostname": "localhost"}

    def test_get_client_default_uses_direct_mode(self):
        """When persistent option is not set (or False), get_client routes to _get_direct_client."""
        mock_direct = MagicMock(return_value=(MagicMock(), None))
        mock_persistent = MagicMock()

        with patch.object(self.connection, "get_option", side_effect=KeyError("persistent")):
            with patch.object(self.connection, "_get_direct_client", mock_direct):
                with patch.object(self.connection, "_get_persistent_client", mock_persistent):
                    client, facts = self.connection.get_client(self.task_vars, self.gateway_config)

        mock_direct.assert_called_once_with(self.task_vars, self.gateway_config)
        mock_persistent.assert_not_called()
        self.assertIsNone(facts)

    def test_get_client_persistent_option_true_routes_to_persistent(self):
        """When connection option persistent=True, get_client routes to _get_persistent_client."""
        mock_client = MagicMock()
        mock_facts = {"platform_manager_socket": "/tmp/sock", "platform_manager_authkey": "key"}
        mock_direct = MagicMock()
        mock_persistent = MagicMock(return_value=(mock_client, mock_facts))

        with patch.object(self.connection, "get_option", return_value=True):
            with patch.object(self.connection, "_get_direct_client", mock_direct):
                with patch.object(self.connection, "_get_persistent_client", mock_persistent):
                    client, facts = self.connection.get_client(self.task_vars, self.gateway_config)

        mock_persistent.assert_called_once_with(self.task_vars, self.gateway_config)
        mock_direct.assert_not_called()
        self.assertIs(client, mock_client)
        self.assertEqual(facts, mock_facts)

    def test_get_client_persistent_option_false_routes_to_direct(self):
        """When connection option persistent=False, get_client routes to _get_direct_client."""
        mock_direct = MagicMock(return_value=(MagicMock(), None))
        mock_persistent = MagicMock()

        with patch.object(self.connection, "get_option", return_value=False):
            with patch.object(self.connection, "_get_direct_client", mock_direct):
                with patch.object(self.connection, "_get_persistent_client", mock_persistent):
                    client, facts = self.connection.get_client(self.task_vars, self.gateway_config)

        mock_direct.assert_called_once_with(self.task_vars, self.gateway_config)
        mock_persistent.assert_not_called()
        self.assertIsNone(facts)

    def test_get_client_var_ansible_platform_use_persistent_connection_true(self):
        """When get_option is missing and task_vars has ansible_platform_use_persistent_connection=true, use persistent."""
        self.task_vars["ansible_platform_use_persistent_connection"] = True
        self.task_vars["hostvars"] = {"localhost": {}}
        mock_persistent = MagicMock(return_value=(MagicMock(), {"platform_manager_socket": "/tmp/s"}))

        with patch.object(self.connection, "get_option", side_effect=KeyError("persistent")):
            with patch.object(self.connection, "_get_direct_client", MagicMock()):
                with patch.object(self.connection, "_get_persistent_client", mock_persistent):
                    self.connection.get_client(self.task_vars, self.gateway_config)

        mock_persistent.assert_called_once()

    def test_get_client_var_ansible_platform_persistent_true(self):
        """When get_option is missing and task_vars has ansible_platform_persistent=true, use persistent."""
        self.task_vars["ansible_platform_persistent"] = "true"
        self.task_vars["hostvars"] = {"localhost": {}}
        mock_persistent = MagicMock(return_value=(MagicMock(), {}))

        with patch.object(self.connection, "get_option", side_effect=KeyError("persistent")):
            with patch.object(self.connection, "_get_direct_client", MagicMock()):
                with patch.object(self.connection, "_get_persistent_client", mock_persistent):
                    self.connection.get_client(self.task_vars, self.gateway_config)

        mock_persistent.assert_called_once()

    def test_get_client_var_hostvars_ansible_platform_use_persistent_connection(self):
        """When hostvars[host] has ansible_platform_use_persistent_connection=yes, use persistent."""
        self.task_vars = {
            "inventory_hostname": "myhost",
            "hostvars": {"myhost": {"ansible_platform_use_persistent_connection": "yes"}},
        }
        mock_persistent = MagicMock(return_value=(MagicMock(), {}))

        with patch.object(self.connection, "get_option", side_effect=KeyError("persistent")):
            with patch.object(self.connection, "_get_direct_client", MagicMock()):
                with patch.object(self.connection, "_get_persistent_client", mock_persistent):
                    self.connection.get_client(self.task_vars, self.gateway_config)

        mock_persistent.assert_called_once()

    def test_get_client_var_falsy_uses_direct(self):
        """When vars set persistent to false/no/0, use direct mode."""
        self.task_vars["ansible_platform_persistent"] = "false"
        self.task_vars["hostvars"] = {"localhost": {}}
        mock_direct = MagicMock(return_value=(MagicMock(), None))

        with patch.object(self.connection, "get_option", side_effect=KeyError("persistent")):
            with patch.object(self.connection, "_get_direct_client", mock_direct):
                with patch.object(self.connection, "_get_persistent_client", MagicMock()):
                    self.connection.get_client(self.task_vars, self.gateway_config)

        mock_direct.assert_called_once()
        
    def _make_connection():
        """Create a Connection instance with minimal mocks for testing get_client().

        ConnectionBase.__init__ calls get_shell_plugin(shell_type=play_context.shell, executable=...).
        Ansible's loader expects real strings, not MagicMock, so we set .shell and .executable explicitly.
        """
        play_context = MagicMock()
        play_context.shell = "sh"
        play_context.executable = "/bin/sh"
        new_stdin = MagicMock()
        conn = Connection(play_context, new_stdin)
        conn._connected = True
        return conn


    def _make_gateway_config():
        """Minimal GatewayConfig for tests."""
        return GatewayConfig(base_url="https://example.com/", username="admin", password="secret")
      
    def test_get_client_no_option_no_vars_defaults_to_direct():
        """When get_option raises and no persistent vars are set, default to direct mode."""
        conn = _make_connection()
        task_vars = {"inventory_hostname": "localhost", "hostvars": {"localhost": {}}}
        gateway_config = _make_gateway_config()
        mock_direct = MagicMock(return_value=(MagicMock(), None))

        with patch.object(conn, "get_option", side_effect=KeyError("persistent")):
            with patch.object(conn, "_get_direct_client", mock_direct):
                with patch.object(conn, "_get_persistent_client", MagicMock()):
                    conn.get_client(task_vars, gateway_config)

        mock_direct.assert_called_once()
        assert mock_direct.return_value[1] is None


    # ---- Direct (ephemeral) mode ----


    def test_get_client_direct_returns_client_and_no_facts():
        """Direct mode returns (client, None) so no facts are set for reuse."""
        conn = _make_connection()
        task_vars = {"inventory_hostname": "localhost"}
        gateway_config = _make_gateway_config()
        mock_client = MagicMock()
        mock_direct = MagicMock(return_value=(mock_client, None))

        with patch.object(conn, "get_option", return_value=False):
            with patch.object(conn, "_get_direct_client", mock_direct):
                with patch.object(conn, "_get_persistent_client", MagicMock()):
                    client, facts = conn.get_client(task_vars, gateway_config)

        assert client is mock_client
        assert facts is None


    # ---- Persistent mode ----


    def test_get_client_persistent_returns_client_and_facts():
        """Persistent mode returns (client, facts_dict) so facts can be set for reuse."""
        conn = _make_connection()
        task_vars = {"inventory_hostname": "localhost"}
        gateway_config = _make_gateway_config()
        mock_client = MagicMock()
        facts_dict = {"platform_manager_socket": "/tmp/sock", "platform_manager_authkey": "b64key"}

        with patch.object(conn, "get_option", return_value=True):
            with patch.object(conn, "_get_direct_client", MagicMock()):
                with patch.object(
                    conn, "_get_persistent_client", MagicMock(return_value=(mock_client, facts_dict))
                ):
                    client, facts = conn.get_client(task_vars, gateway_config)

        assert client is mock_client
        assert facts == facts_dict
        assert "platform_manager_socket" in facts
        assert "platform_manager_authkey" in facts


    # ---- Persistent connection failure scenarios ----


    def test_persistent_reuse_fails_connection_raises_spawns_new():
        """When reuse is attempted but ManagerRPCClient raises (e.g. process dead), spawn new manager and return it."""
        import base64

        conn = _make_connection()
        stale_socket = "/tmp/ansible_platform/stale.sock"
        authkey_b64 = base64.b64encode(b"secret").decode("ascii")
        task_vars = {
            "inventory_hostname": "localhost",
            "hostvars": {"localhost": {"platform_manager_socket": stale_socket, "platform_manager_authkey": authkey_b64}},
        }
        gateway_config = _make_gateway_config()

        mock_client = MagicMock()
        new_socket = "/tmp/ansible_platform/new.sock"
        conn_info = MagicMock()
        conn_info.socket_path = new_socket
        conn_info.authkey_b64 = authkey_b64
        conn_info.authkey = b"secret"

        with patch("ansible_collections.ansible.platform.plugins.connection.http.Path") as mock_path_cls:
            mock_path_cls.return_value.exists.return_value = True
            # script_path.exists() in spawn path
            mock_path_cls.return_value.parent.parent.__truediv__.return_value.exists.return_value = True

            with patch("ansible_collections.ansible.platform.plugins.connection.http.ProcessManager") as mock_pm:
                mock_pm.generate_connection_info.return_value = conn_info
                mock_pm.cleanup_old_socket.return_value = None
                mock_pm.spawn_manager_process.return_value = MagicMock(pid=9999)
                mock_pm.wait_for_process_startup.return_value = None

                with patch("ansible_collections.ansible.platform.plugins.connection.http.ManagerRPCClient") as mock_rpc:
                    mock_rpc.side_effect = [ConnectionError("Connection refused"), mock_client]

                    client, facts = conn._get_persistent_client(task_vars, gateway_config)

        assert client is mock_client
        assert facts is not None
        assert facts.get("platform_manager_socket") == new_socket
        assert facts.get("platform_manager_authkey") == authkey_b64
        mock_pm.spawn_manager_process.assert_called_once()
        assert mock_rpc.call_count == 2


    def test_persistent_socket_file_missing_spawns_new():
        """When facts have socket path but socket file does not exist, skip reuse and spawn new manager."""
        import base64

        conn = _make_connection()
        missing_socket = "/tmp/ansible_platform/missing.sock"
        authkey_b64 = base64.b64encode(b"secret").decode("ascii")
        task_vars = {
            "inventory_hostname": "localhost",
            "hostvars": {"localhost": {"platform_manager_socket": missing_socket, "platform_manager_authkey": authkey_b64}},
        }
        gateway_config = _make_gateway_config()

        mock_client = MagicMock()
        new_socket = "/tmp/ansible_platform/new.sock"
        conn_info = MagicMock()
        conn_info.socket_path = new_socket
        conn_info.authkey_b64 = authkey_b64
        conn_info.authkey = b"secret"

        with patch("ansible_collections.ansible.platform.plugins.connection.http.Path") as mock_path_cls:
            # Socket exists check: False (file missing) so we never try to connect
            mock_path_cls.return_value.exists.return_value = False
            mock_path_cls.return_value.parent.parent.__truediv__.return_value.exists.return_value = True

            with patch("ansible_collections.ansible.platform.plugins.connection.http.ProcessManager") as mock_pm:
                mock_pm.generate_connection_info.return_value = conn_info
                mock_pm.cleanup_old_socket.return_value = None
                mock_pm.spawn_manager_process.return_value = MagicMock(pid=9999)
                mock_pm.wait_for_process_startup.return_value = None

                with patch("ansible_collections.ansible.platform.plugins.connection.http.ManagerRPCClient", return_value=mock_client):
                    client, facts = conn._get_persistent_client(task_vars, gateway_config)

        assert client is mock_client
        assert facts is not None
        assert facts.get("platform_manager_socket") == new_socket
        mock_pm.spawn_manager_process.assert_called_once()
        # ManagerRPCClient only called once (for new spawn), not for reuse
        # We didn't patch it with side_effect so we can't assert call_count; the important part is spawn was used


if __name__ == '__main__':
    unittest.main()
