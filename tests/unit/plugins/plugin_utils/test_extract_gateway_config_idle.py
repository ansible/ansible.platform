# (c) 2026 Red Hat Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Tests for persistent_manager_idle_timeout extraction (including value 0)."""

from __future__ import absolute_import, division, print_function

import sys
import unittest
from pathlib import Path

# Lives in plugin_utils/ (not plugin_utils/platform/) to avoid shadowing stdlib ``platform`` on import.
_COLLECTIONS_PARENT = str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent.parent)
if _COLLECTIONS_PARENT not in sys.path:
    sys.path.insert(0, _COLLECTIONS_PARENT)

from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import (  # noqa: E402
    extract_gateway_config,
)


class TestExtractPersistentManagerIdleTimeout(unittest.TestCase):
    """Only ``persistent_manager_idle_timeout`` is read; ``0`` must be preserved."""

    _base_task = {
        "gateway_url": "https://gw.example",
        "gateway_username": "a",
        "gateway_password": "b",
    }

    def test_task_zero_disables_idle_shutdown(self):
        c = extract_gateway_config(
            task_args={**self._base_task, "persistent_manager_idle_timeout": 0},
            host_vars={},
            required=True,
        )
        self.assertEqual(c.idle_timeout, 0.0)

    def test_task_zero_wins_over_host_nonzero(self):
        c = extract_gateway_config(
            task_args={**self._base_task, "persistent_manager_idle_timeout": 0},
            host_vars={"persistent_manager_idle_timeout": 7200},
            required=True,
        )
        self.assertEqual(c.idle_timeout, 0.0)

    def test_host_zero_when_not_in_task(self):
        c = extract_gateway_config(
            task_args=dict(self._base_task),
            host_vars={"persistent_manager_idle_timeout": 0},
            required=True,
        )
        self.assertEqual(c.idle_timeout, 0.0)

    def test_default_3600_when_unset(self):
        c = extract_gateway_config(
            task_args=dict(self._base_task),
            host_vars={},
            required=True,
        )
        self.assertEqual(c.idle_timeout, 3600.0)

    def test_other_keys_do_not_set_idle_timeout(self):
        """Only persistent_manager_idle_timeout is honored."""
        c = extract_gateway_config(
            task_args={**self._base_task, "gateway_idle_timeout": 99},
            host_vars={},
            required=True,
        )
        self.assertEqual(c.idle_timeout, 3600.0)


if __name__ == "__main__":
    unittest.main()
