import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import ProcessManager


class TestProcessManagerStaleSocket(TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.socket_path = os.path.join(self.test_dir.name, "test_manager.sock")
        self.pid_path = f"{self.socket_path}.pid"

    def tearDown(self):
        self.test_dir.cleanup()

    def test_is_socket_stale_no_socket(self):
        """Test when the socket file does not exist at all."""
        self.assertFalse(ProcessManager.is_socket_stale(self.socket_path))

    def test_is_socket_stale_no_pid_file(self):
        """Test when socket exists, but PID file is missing."""
        Path(self.socket_path).touch()
        self.assertTrue(ProcessManager.is_socket_stale(self.socket_path))

    def test_is_socket_stale_invalid_pid_file(self):
        """Test when PID file contains non-integer garbage."""
        Path(self.socket_path).touch()
        Path(self.pid_path).write_text("not_a_number")
        self.assertTrue(ProcessManager.is_socket_stale(self.socket_path))

    @patch('os.kill')
    def test_is_socket_stale_process_dead(self, mock_kill):
        """Test when os.kill raises OSError (process is dead)."""
        Path(self.socket_path).touch()
        Path(self.pid_path).write_text("12345")
        # Simulate process not existing
        mock_kill.side_effect = OSError("No such process")
        self.assertTrue(ProcessManager.is_socket_stale(self.socket_path))
        mock_kill.assert_called_once_with(12345, 0)

    @patch('os.kill')
    def test_is_socket_stale_process_alive(self, mock_kill):
        """Test when os.kill succeeds (process is alive)."""
        Path(self.socket_path).touch()
        Path(self.pid_path).write_text("12345")
        # Simulate process existing (os.kill returns None)
        mock_kill.return_value = None
        self.assertFalse(ProcessManager.is_socket_stale(self.socket_path))
        mock_kill.assert_called_once_with(12345, 0)

    def test_cleanup_old_socket_removes_both_files(self):
        """Test that cleanup removes both the socket and the PID file."""
        Path(self.socket_path).touch()
        Path(self.pid_path).touch()
        ProcessManager.cleanup_old_socket(self.socket_path)
        self.assertFalse(os.path.exists(self.socket_path))
        self.assertFalse(os.path.exists(self.pid_path))
