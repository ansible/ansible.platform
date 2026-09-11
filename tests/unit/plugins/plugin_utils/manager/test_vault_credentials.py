# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for Ansible Vault credential handling in process_manager.py"""

from __future__ import absolute_import, division, print_function

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import ProcessManager
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig


class MockAnsibleVaultEncryptedUnicode(str):
    """Mock Ansible Vault encrypted string object.

    Ansible Vault values are wrapped in AnsibleVaultEncryptedUnicode which
    inherits from str but subprocess.Popen doesn't accept them directly.
    """

    def __new__(cls, value):
        """Create a new vault-encrypted string."""
        instance = str.__new__(cls, value)
        instance._ansible_vault = True
        return instance

    def __str__(self):
        """Convert to string - this is what str() does."""
        return super().__str__()

    def __repr__(self):
        """Represent as vault object."""
        return f"AnsibleVaultEncryptedUnicode({super().__repr__()})"


def test_vault_credentials_converted_to_strings():
    """
    Test that vaulted credentials are converted to strings before subprocess.Popen.

    Reproduces the issue from AAP-XXXXX where:
    - aap_username and aap_password are Ansible Vault values in group_vars
    - spawn_manager_process() fails with:
      TypeError: expected str, bytes or os.PathLike object, not AnsibleVaultEncryptedUnicode
    """
    # Create vaulted credentials
    vaulted_username = MockAnsibleVaultEncryptedUnicode("admin")
    vaulted_password = MockAnsibleVaultEncryptedUnicode("secret123")

    # Verify they're not plain strings
    assert type(vaulted_username).__name__ == "MockAnsibleVaultEncryptedUnicode"
    assert type(vaulted_password).__name__ == "MockAnsibleVaultEncryptedUnicode"

    # Create config with vaulted credentials
    gateway_config = GatewayConfig(
        base_url="https://gateway.example.com",
        username=vaulted_username,
        password=vaulted_password,
        verify_ssl=True,
    )

    script_path = Path(__file__).parent.parent.parent.parent / "plugin_utils" / "manager" / "manager_process.py"
    socket_path = "/tmp/test_socket.sock"

    # Mock subprocess.Popen to capture the cmd argument
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        try:
            ProcessManager.spawn_manager_process(
                script_path=script_path,
                socket_path=socket_path,
                socket_dir="/tmp",
                identifier="test_vault",
                gateway_config=gateway_config,
                authkey_b64="dGVzdGF1dGhrZXk=",
                sys_path=["/fake/path"],
            )
        except Exception as e:
            # We expect it might fail for other reasons (missing files, etc)
            # but NOT with the Vault type error
            assert "AnsibleVaultEncryptedUnicode" not in str(e), f"Vault credentials not converted to strings: {e}"

        # Verify Popen was called
        assert mock_popen.called, "subprocess.Popen should have been called"

        # Get the cmd argument
        call_args = mock_popen.call_args
        cmd = call_args[0][0] if call_args[0] else call_args.kwargs.get("args")

        # Verify all cmd elements are proper types (str, not Vault objects)
        for i, arg in enumerate(cmd):
            # subprocess.Popen requires each arg to be str, bytes, or PathLike
            assert isinstance(arg, (str, bytes)) or hasattr(arg, "__fspath__"), f"cmd[{i}] = {arg!r} (type: {type(arg)}) is not a valid subprocess argument"

        # Specifically verify credentials are plain strings
        username_arg = cmd[6]  # gateway_config.username
        password_arg = cmd[7]  # gateway_config.password

        assert isinstance(username_arg, str) and type(username_arg) is str, f"Username arg is {type(username_arg)}, expected str"
        assert isinstance(password_arg, str) and type(password_arg) is str, f"Password arg is {type(password_arg)}, expected str"

        # Verify the VALUES are correct (vault decrypted)
        assert username_arg == "admin", f"Expected 'admin', got {username_arg!r}"
        assert password_arg == "secret123", f"Expected 'secret123', got {password_arg!r}"


def test_empty_vault_credentials_become_empty_strings():
    """Test that None credentials become empty strings, not 'None'."""
    gateway_config = GatewayConfig(
        base_url="https://gateway.example.com",
        username=None,
        password=None,
        oauth_token=None,
    )

    script_path = Path(__file__).parent.parent.parent.parent / "plugin_utils" / "manager" / "manager_process.py"

    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        try:
            ProcessManager.spawn_manager_process(
                script_path=script_path,
                socket_path="/tmp/test.sock",
                socket_dir="/tmp",
                identifier="test_empty",
                gateway_config=gateway_config,
                authkey_b64="dGVzdA==",
            )
        except Exception:
            pass  # We don't care if it fails for other reasons

        if mock_popen.called:
            cmd = mock_popen.call_args[0][0]

            # Verify None became "" not "None"
            assert cmd[6] == "", f"None username should be '', got {cmd[6]!r}"
            assert cmd[7] == "", f"None password should be '', got {cmd[7]!r}"
            assert cmd[8] == "", f"None token should be '', got {cmd[8]!r}"


def test_base_url_also_converted_to_string():
    """Test that base_url is also converted to str (could be Vault too)."""
    vaulted_url = MockAnsibleVaultEncryptedUnicode("https://gateway.example.com")

    gateway_config = GatewayConfig(
        base_url=vaulted_url,
        username="admin",
        password="secret",
    )

    script_path = Path(__file__).parent.parent.parent.parent / "plugin_utils" / "manager" / "manager_process.py"

    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        try:
            ProcessManager.spawn_manager_process(
                script_path=script_path,
                socket_path="/tmp/test.sock",
                socket_dir="/tmp",
                identifier="test_url",
                gateway_config=gateway_config,
                authkey_b64="dGVzdA==",
            )
        except Exception:
            pass

        if mock_popen.called:
            cmd = mock_popen.call_args[0][0]
            base_url_arg = cmd[5]  # gateway_config.base_url

            assert type(base_url_arg) is str, f"base_url should be plain str, got {type(base_url_arg)}"
            assert base_url_arg == "https://gateway.example.com"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
