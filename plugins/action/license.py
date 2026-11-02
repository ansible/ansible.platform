#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import base64
from dataclasses import asdict

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.license import AnsibleLicense
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.license import ATTACH_ENDPOINT

_SERVICE = "controller"


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "license"
    MODEL_CLASS = AnsibleLicense
    _MUTUALLY_EXCLUSIVE = [["manifest", "subscription_id"]]

    def run(self, tmp=None, task_vars=None):
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            manager = prepared["manager"]

            manifest_path = validated_params.get("manifest")
            subscription_id = validated_params.get("subscription_id")
            force = validated_params.get("force", False)
            state = validated_params.get("state", "present")

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

    def _get_config(self, manager):
        """GET current config via SDK execute('find')."""
        return manager.execute(
            operation="find",
            module_name=self.MODULE_NAME,
            ansible_data=asdict(AnsibleLicense()),
        )

    def _is_licensed(self, config):
        license_info = config.get("license_info", {})
        return license_info.get("instance_count", 0) > 0 and license_info.get("valid_key", False) and not license_info.get("trial", True)

    def _handle_absent(self, manager, result):
        config = self._get_config(manager)
        license_info = config.get("license_info", {})
        has_license = bool(license_info.get("license_type") or license_info.get("instance_count"))
        if not has_license:
            result.update({"changed": False, "msg": "No license to remove"})
            return result

        if self._task.check_mode:
            result.update({"changed": True})
            return result

        manager.delete_resource("config/", service=_SERVICE)
        result.update({"changed": True, "msg": "License removed"})
        return result

    def _handle_manifest(self, manager, result, manifest_path, force):
        try:
            manifest_path = self._find_needle("files", manifest_path)
        except AnsibleError as e:
            result.update({"changed": False, "failed": True, "msg": str(e)})
            return result
        try:
            with open(manifest_path, "rb") as fid:
                manifest_b64 = base64.b64encode(fid.read()).decode()
        except OSError as e:
            result.update({"changed": False, "failed": True, "msg": str(e)})
            return result

        config = self._get_config(manager)
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

        license_data = AnsibleLicense(manifest=manifest_b64)
        create_result = manager.execute(
            operation="create",
            module_name=self.MODULE_NAME,
            ansible_data=asdict(license_data),
        )

        result.update(
            {
                "changed": True,
                "license_info": create_result.get("license_info", {}),
            }
        )
        return result

    def _handle_subscription(self, manager, result, subscription_id, force):
        config = self._get_config(manager)
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

        # Subscription uses /config/attach/ — different endpoint than default create.
        manager.post_resource(ATTACH_ENDPOINT, {"subscription_id": subscription_id}, service=_SERVICE, retry=False)

        updated = self._get_config(manager)
        result.update(
            {
                "changed": True,
                "license_info": updated.get("license_info", {}),
            }
        )
        return result
