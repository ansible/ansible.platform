#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import base64
import json
import os
import signal
import tempfile
import time
from pathlib import Path

from ansible.plugins.callback import CallbackBase

DOCUMENTATION = r"""
name: platform_manager_cleanup
short_description: Gracefully shut down ansible.platform manager processes after each play
description:
  - Terminates persistent manager subprocesses that were spawned by the
    ansible.platform connection/action plugins once the play they belong to
    has finished.
  - Reads companion C(.meta) files written next to each Unix socket to
    discover which processes are still alive, so it works correctly even when
    the action plugin that spawned the manager is in a different worker fork.
  - Zero configuration required. C(CALLBACK_NEEDS_ENABLED = False) causes
    Ansible to auto-load this plugin from the collection without any entry in
    C(ansible.cfg).
type: notification
requirements: []
options: {}
"""

CALLBACK_TYPE = "notification"
# False = Ansible auto-loads this plugin from the collection with zero
# user configuration.  No callbacks_enabled entry in ansible.cfg required.
CALLBACK_NEEDS_ENABLED = False
CALLBACK_VERSION = 2.0
CALLBACK_NAME = "ansible.platform.platform_manager_cleanup"

# Socket directory used by the platform connection plugin and action plugin.
_SOCKET_DIR = Path(tempfile.gettempdir()) / "ansible_platform"


class CallbackModule(CallbackBase):
    """Graceful platform manager cleanup on play-end."""

    CALLBACK_TYPE = CALLBACK_TYPE
    CALLBACK_NEEDS_ENABLED = False
    CALLBACK_VERSION = CALLBACK_VERSION
    CALLBACK_NAME = CALLBACK_NAME

    # ------------------------------------------------------------------ #
    # Ansible hooks                                                        #
    # ------------------------------------------------------------------ #

    def v2_playbook_on_play_end(self, play):
        """Called by Ansible in the main process when a play finishes."""
        self._shutdown_all_managers()

    def v2_playbook_on_stats(self, stats):
        """
        Belt-and-suspenders: also clean up at the very end of the playbook
        in case v2_playbook_on_play_end was not fired (e.g. play was skipped).
        """
        self._shutdown_all_managers()

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _shutdown_all_managers(self):
        """Scan the socket directory for .meta files and shut down each manager."""
        if not _SOCKET_DIR.exists():
            return

        meta_files = list(_SOCKET_DIR.glob("*.meta"))
        if not meta_files:
            return

        self._display.vv(f"[platform_manager_cleanup] Found {len(meta_files)} manager(s) to shut down")

        for meta_path in meta_files:
            self._shutdown_one(meta_path)

    def _shutdown_one(self, meta_path: Path):
        """Shut down the manager described by *meta_path* and remove both files."""
        try:
            meta = json.loads(meta_path.read_text())
        except Exception as exc:
            self._display.vvvv(f"[platform_manager_cleanup] Cannot read {meta_path}: {exc}")
            _safe_unlink(meta_path)
            return

        pid = meta.get("pid")
        authkey_b64 = meta.get("authkey_b64")
        socket_path = str(meta_path).removesuffix(".meta")

        if not pid:
            self._display.vvvv(f"[platform_manager_cleanup] No PID in {meta_path}, skipping")
            _safe_unlink(meta_path)
            return

        # Check whether the process is still alive.
        if not _pid_alive(pid):
            self._display.vvvv(f"[platform_manager_cleanup] Manager PID {pid} already gone")
            _safe_unlink(meta_path)
            _safe_unlink(Path(socket_path))
            return

        self._display.vv(f"[platform_manager_cleanup] Shutting down manager PID={pid} socket={socket_path}")

        # 1. Try graceful RPC shutdown first (manager handles it cleanly).
        if authkey_b64 and Path(socket_path).exists():
            try:
                self._rpc_shutdown(socket_path, authkey_b64)
            except Exception as exc:
                self._display.vvvv(f"[platform_manager_cleanup] RPC shutdown failed: {exc}")

        # 2. Wait up to 5 s for the process to exit on its own.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if not _pid_alive(pid):
                break
            time.sleep(0.1)

        # 3. Force-terminate if still running.
        if _pid_alive(pid):
            self._display.vvvv(f"[platform_manager_cleanup] Manager PID {pid} still alive, sending SIGTERM")
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            time.sleep(1)

        if _pid_alive(pid):
            self._display.warning(f"[platform_manager_cleanup] Manager PID {pid} did not stop, sending SIGKILL")
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

        # 4. Clean up files.
        _safe_unlink(meta_path)
        _safe_unlink(Path(socket_path))
        self._display.vvvv(f"[platform_manager_cleanup] Manager PID {pid} cleaned up")

    def _rpc_shutdown(self, socket_path: str, authkey_b64: str):
        """Send a graceful shutdown RPC to the manager."""
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import (
            ManagerRPCClient,
        )

        authkey = base64.b64decode(authkey_b64)
        client = ManagerRPCClient("", socket_path, authkey)
        try:
            client.shutdown_manager()
        finally:
            client.close()


# ------------------------------------------------------------------ #
# Module-level helpers                                                #
# ------------------------------------------------------------------ #


def _pid_alive(pid: int) -> bool:
    """Return True if *pid* is still a running process."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but owned by another user — treat as alive.
        return True


def _safe_unlink(path: Path):
    """Remove *path* silently if it exists."""
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass
