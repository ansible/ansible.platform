#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.instance import AnsibleInstance

_SERVICE = "controller"


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "instance"
    MODEL_CLASS = AnsibleInstance

    _WRITE_ONLY_FIELDS = frozenset({"peers"})

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}

        cap_adj = self._task.args.get("capacity_adjustment")
        if cap_adj is not None:
            try:
                self._task.args["capacity_adjustment"] = float(cap_adj)
            except (ValueError, TypeError):
                pass

        peers = self._task.args.pop("peers", None)
        state = self._task.args.get("state", "present")
        check_mode = self._task.check_mode

        if state in ("absent", "deleted"):
            self._task.args["state"] = "exists"
            result = super().run(tmp, task_vars)
            if result.get("failed"):
                return result
            if not result.get("exists", False):
                return {
                    "changed": False,
                    "msg": "Instance does not exist (already absent)",
                    "instance": {"state": "absent"},
                }
            self._task.args["state"] = "present"
            self._task.args["node_state"] = "deprovisioning"

        result = super().run(tmp, task_vars)
        if result.get("failed") or state in ("absent", "deleted", "exists"):
            return result

        instance_id = result.get("id") or (result.get(self.MODULE_NAME) or {}).get("id")
        if not instance_id or peers is None:
            return result

        if check_mode:
            result["changed"] = True
            return result

        try:
            manager = self._client
            peers_ids = self._resolve_peers(manager, peers)

            find_result = manager.execute(
                operation="find",
                module_name=self.MODULE_NAME,
                ansible_data={"id": instance_id, "hostname": result.get("hostname", "")},
            )
            current_peers = find_result.get("peers", []) if find_result else []

            if sorted(peers_ids) != sorted(current_peers):
                manager.execute(
                    operation="update",
                    module_name=self.MODULE_NAME,
                    ansible_data={"id": instance_id, "hostname": result.get("hostname", ""), "peers": peers_ids},
                )
                result["changed"] = True
        except Exception as exc:
            result["failed"] = True
            result["msg"] = "Failed to reconcile peers: %s" % exc

        return result

    @staticmethod
    def _resolve_peers(manager, peers):
        resolved = []
        for p in peers:
            p_str = str(p).strip()
            if p_str.isdigit():
                resolved.append(int(p_str))
            else:
                peer_id = manager.lookup_resource_id("receptor_addresses", "address", p_str, service=_SERVICE)
                resolved.append(peer_id)
        return resolved
