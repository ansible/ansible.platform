#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import base64

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin

_CONFIG_ENDPOINT = "/api/controller/v2/config/"
_ATTACH_ENDPOINT = "/api/controller/v2/config/attach/"
_SERVICE = "controller"


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "license"
    MODEL_CLASS = None

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}

        self._task_vars = task_vars
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        try:
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                raise AnsibleError("Could not load DOCUMENTATION for license module")

            validated_input = self._validate_data(self._task.args.copy(), argspec, "input")
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            params = validated_input.validated_parameters
            manifest_path = params.get("manifest")
            subscription_id = params.get("subscription_id")
            force = params.get("force", False)
            state = params.get("state", "present")

            if state == "absent":
                return self._handle_absent(manager, result)

            if manifest_path:
                return self._handle_manifest(manager, result, manifest_path, force)

            if subscription_id:
                return self._handle_subscription(manager, result, subscription_id, force)

            result.update({"changed": False, "failed": True, "msg": "One of 'manifest' or 'subscription_id' is required when state=present"})

        except Exception as e:
            import traceback

            self._display.vvv("Error in license action plugin: %s" % e)
            result["failed"] = True
            result["msg"] = str(e)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result

    def _is_licensed(self, config):
        license_info = config.get("license_info", {})
        return license_info.get("instance_count", 0) > 0 and license_info.get("valid_key", False) and not license_info.get("trial", True)

    def _handle_absent(self, manager, result):
        config = manager.search_api(_CONFIG_ENDPOINT)
        if not self._is_licensed(config):
            result.update({"changed": False, "msg": "No license to remove"})
            return result

        if self._task.check_mode:
            result.update({"changed": True})
            return result

        manager.delete_resource(_CONFIG_ENDPOINT, service=_SERVICE)
        result.update({"changed": True, "msg": "License removed"})
        return result

    def _handle_manifest(self, manager, result, manifest_path, force):
        try:
            with open(manifest_path, "rb") as fid:
                manifest_b64 = base64.b64encode(fid.read()).decode()
        except OSError as e:
            result.update({"changed": False, "failed": True, "msg": str(e)})
            return result

        config = manager.search_api(_CONFIG_ENDPOINT)
        if self._is_licensed(config) and not force:
            result.update(
                {
                    "changed": False,
                    "license_info": config.get("license_info", {}),
                    "msg": "Already licensed. Use force=true to re-apply.",
                }
            )
            return result

        if self._task.check_mode:
            result.update({"changed": True})
            return result

        manager.post_resource(_CONFIG_ENDPOINT, {"manifest": manifest_b64}, service=_SERVICE)

        updated_config = manager.search_api(_CONFIG_ENDPOINT)
        result.update(
            {
                "changed": True,
                "license_info": updated_config.get("license_info", {}),
            }
        )
        return result

    def _handle_subscription(self, manager, result, subscription_id, force):
        config = manager.search_api(_CONFIG_ENDPOINT)
        if self._is_licensed(config) and not force:
            result.update(
                {
                    "changed": False,
                    "license_info": config.get("license_info", {}),
                    "msg": "Already licensed. Use force=true to re-apply.",
                }
            )
            return result

        if self._task.check_mode:
            result.update({"changed": True})
            return result

        manager.post_resource(_ATTACH_ENDPOINT, {"subscription_id": subscription_id}, service=_SERVICE)

        updated_config = manager.search_api(_CONFIG_ENDPOINT)
        result.update(
            {
                "changed": True,
                "license_info": updated_config.get("license_info", {}),
            }
        )
        return result
