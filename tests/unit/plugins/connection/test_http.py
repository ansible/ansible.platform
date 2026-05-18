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

from unittest.mock import MagicMock, patch

from ansible_collections.ansible.platform.plugins.connection.http import Connection
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig


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


# ---- Dispatcher: routing to persistent vs direct ----


def test_get_client_default_uses_direct_mode():
    """When persistent option is not set (or False), get_client routes to _get_direct_client."""
    conn = _make_connection()
    task_vars = {"inventory_hostname": "localhost"}
    gateway_config = _make_gateway_config()
    mock_direct = MagicMock(return_value=(MagicMock(), None))
    mock_persistent = MagicMock()

    with patch.object(conn, "get_option", side_effect=KeyError("persistent")):
        with patch.object(conn, "_get_direct_client", mock_direct):
            with patch.object(conn, "_get_persistent_client", mock_persistent):
                client, facts = conn.get_client(task_vars, gateway_config)

    mock_direct.assert_called_once_with(task_vars, gateway_config, task_env=None)
    mock_persistent.assert_not_called()
    assert facts is None


def test_get_client_persistent_option_true_routes_to_persistent():
    """When connection option persistent=True, get_client routes to _get_persistent_client."""
    conn = _make_connection()
    task_vars = {"inventory_hostname": "localhost"}
    gateway_config = _make_gateway_config()
    mock_client = MagicMock()
    mock_facts = {"platform_manager_socket": "/tmp/sock", "platform_manager_authkey": "key"}
    mock_direct = MagicMock()
    mock_persistent = MagicMock(return_value=(mock_client, mock_facts))

    with patch.object(conn, "get_option", return_value=True):
        with patch.object(conn, "_get_direct_client", mock_direct):
            with patch.object(conn, "_get_persistent_client", mock_persistent):
                client, facts = conn.get_client(task_vars, gateway_config)

    mock_persistent.assert_called_once_with(task_vars, gateway_config)
    mock_direct.assert_not_called()
    assert client is mock_client
    assert facts == mock_facts


def test_get_client_persistent_option_false_routes_to_direct():
    """When connection option persistent=False, get_client routes to _get_direct_client."""
    conn = _make_connection()
    task_vars = {"inventory_hostname": "localhost"}
    gateway_config = _make_gateway_config()
    mock_direct = MagicMock(return_value=(MagicMock(), None))
    mock_persistent = MagicMock()

    with patch.object(conn, "get_option", return_value=False):
        with patch.object(conn, "_get_direct_client", mock_direct):
            with patch.object(conn, "_get_persistent_client", mock_persistent):
                client, facts = conn.get_client(task_vars, gateway_config)

    mock_direct.assert_called_once_with(task_vars, gateway_config, task_env=None)
    mock_persistent.assert_not_called()
    assert facts is None


def test_get_client_var_ansible_platform_use_persistent_connection_true():
    """When get_option is missing and task_vars has ansible_platform_use_persistent_connection=true, use persistent."""
    conn = _make_connection()
    task_vars = {
        "inventory_hostname": "localhost",
        "hostvars": {"localhost": {}},
        "ansible_platform_use_persistent_connection": True,
    }
    gateway_config = _make_gateway_config()
    mock_persistent = MagicMock(return_value=(MagicMock(), {"platform_manager_socket": "/tmp/s"}))

    with patch.object(conn, "get_option", side_effect=KeyError("persistent")):
        with patch.object(conn, "_get_direct_client", MagicMock()):
            with patch.object(conn, "_get_persistent_client", mock_persistent):
                conn.get_client(task_vars, gateway_config)

    mock_persistent.assert_called_once()


def test_get_client_var_ansible_platform_persistent_true():
    """When get_option is missing and task_vars has ansible_platform_persistent=true, use persistent."""
    conn = _make_connection()
    task_vars = {
        "inventory_hostname": "localhost",
        "hostvars": {"localhost": {}},
        "ansible_platform_persistent": "true",
    }
    gateway_config = _make_gateway_config()
    mock_persistent = MagicMock(return_value=(MagicMock(), {}))

    with patch.object(conn, "get_option", side_effect=KeyError("persistent")):
        with patch.object(conn, "_get_direct_client", MagicMock()):
            with patch.object(conn, "_get_persistent_client", mock_persistent):
                conn.get_client(task_vars, gateway_config)

    mock_persistent.assert_called_once()


def test_get_client_var_hostvars_ansible_platform_use_persistent_connection():
    """When hostvars[host] has ansible_platform_use_persistent_connection=yes, use persistent."""
    conn = _make_connection()
    task_vars = {
        "inventory_hostname": "myhost",
        "hostvars": {"myhost": {"ansible_platform_use_persistent_connection": "yes"}},
    }
    gateway_config = _make_gateway_config()
    mock_persistent = MagicMock(return_value=(MagicMock(), {}))

    with patch.object(conn, "get_option", side_effect=KeyError("persistent")):
        with patch.object(conn, "_get_direct_client", MagicMock()):
            with patch.object(conn, "_get_persistent_client", mock_persistent):
                conn.get_client(task_vars, gateway_config)

    mock_persistent.assert_called_once()


def test_get_client_var_falsy_uses_direct():
    """When vars set persistent to false/no/0, use direct mode."""
    conn = _make_connection()
    task_vars = {
        "inventory_hostname": "localhost",
        "hostvars": {"localhost": {}},
        "ansible_platform_persistent": "false",
    }
    gateway_config = _make_gateway_config()
    mock_direct = MagicMock(return_value=(MagicMock(), None))

    with patch.object(conn, "get_option", side_effect=KeyError("persistent")):
        with patch.object(conn, "_get_direct_client", mock_direct):
            with patch.object(conn, "_get_persistent_client", MagicMock()):
                conn.get_client(task_vars, gateway_config)

    mock_direct.assert_called_once()


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
            with patch.object(conn, "_get_persistent_client", MagicMock(return_value=(mock_client, facts_dict))):
                client, facts = conn.get_client(task_vars, gateway_config)

    assert client is mock_client
    assert facts == facts_dict
    assert "platform_manager_socket" in facts
    assert "platform_manager_authkey" in facts


# ---- Persistent connection failure scenarios ----


def test_persistent_reuse_fails_connection_raises_spawns_new():
    """When reuse is attempted but ManagerRPCClient raises (e.g. process dead), spawn new manager and return it."""
    import base64
    import json as _json
    from unittest.mock import mock_open

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

    # Fast path: socket + meta both "exist"; lock re-check: socket gone -> falls through to spawn.
    # Script path existence check uses the __truediv__ chain mock (set to True below).
    exists_side_effect = [True, True, False]

    meta_json = _json.dumps({"authkey_b64": authkey_b64, "gateway_url": "https://example.com"})

    with patch("ansible_collections.ansible.platform.plugins.connection.http.Path") as mock_path_cls:
        mock_path_cls.return_value.exists.side_effect = exists_side_effect
        mock_path_cls.return_value.is_socket.return_value = True
        # script_path.exists() in spawn path (built via __truediv__ chain)
        mock_path_cls.return_value.parent.parent.__truediv__.return_value.exists.return_value = True

        with patch("ansible_collections.ansible.platform.plugins.connection.http.ProcessManager") as mock_pm:
            mock_pm.generate_connection_info.return_value = conn_info
            mock_pm.is_socket_stale.return_value = False  # socket is live; attempt connection
            mock_pm.cleanup_old_socket.return_value = None
            mock_pm.spawn_manager_process.return_value = MagicMock(pid=9999)
            mock_pm.wait_for_process_startup.return_value = None

            # Provide a fake fcntl so open(lock_path, "w") + flock don't touch the real filesystem.
            fake_fcntl = MagicMock()
            fake_fcntl.LOCK_EX = 2
            fake_fcntl.LOCK_UN = 8

            with patch("builtins.open", mock_open(read_data=meta_json)):
                with patch.dict("sys.modules", {"fcntl": fake_fcntl}):
                    with patch("ansible_collections.ansible.platform.plugins.connection.http.ManagerRPCClient") as mock_rpc:
                        mock_rpc.side_effect = [ConnectionError("Connection refused"), mock_client]

                        client, facts = conn._get_persistent_client(task_vars, gateway_config)

    assert client is mock_client
    # Implementation stores manager info in a .meta file rather than ansible_facts.
    assert facts is None
    mock_pm.spawn_manager_process.assert_called_once()


def test_persistent_socket_file_missing_spawns_new():
    """When socket file does not exist, skip the fast-path reuse check and spawn a new manager."""
    import base64
    from unittest.mock import mock_open

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
        # Socket does not exist -> skip fast path and lock re-check; go straight to spawn.
        mock_path_cls.return_value.exists.return_value = False
        # script_path.exists() in spawn path (built via __truediv__ chain)
        mock_path_cls.return_value.parent.parent.__truediv__.return_value.exists.return_value = True

        with patch("ansible_collections.ansible.platform.plugins.connection.http.ProcessManager") as mock_pm:
            mock_pm.generate_connection_info.return_value = conn_info
            mock_pm.cleanup_old_socket.return_value = None
            mock_pm.spawn_manager_process.return_value = MagicMock(pid=9999)
            mock_pm.wait_for_process_startup.return_value = None

            fake_fcntl = MagicMock()
            fake_fcntl.LOCK_EX = 2
            fake_fcntl.LOCK_UN = 8

            with patch("builtins.open", mock_open()):
                with patch.dict("sys.modules", {"fcntl": fake_fcntl}):
                    with patch("ansible_collections.ansible.platform.plugins.connection.http.ManagerRPCClient", return_value=mock_client):
                        client, facts = conn._get_persistent_client(task_vars, gateway_config)

    assert client is mock_client
    # Implementation stores manager info in a .meta file rather than ansible_facts.
    assert facts is None
    mock_pm.spawn_manager_process.assert_called_once()
