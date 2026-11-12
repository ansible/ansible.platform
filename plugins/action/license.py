#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2026, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import base64
from dataclasses import asdict

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.license import AnsibleLicense


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "license"
    MODEL_CLASS = AnsibleLicense
    _MUTUALLY_EXCLUSIVE = [["manifest", "subscription_id"]]
    _REQUIRED_IF = [["state", "present", ["manifest", "subscription_id"], True]]

    def run(self, tmp=None, task_vars=None):
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            manager = prepared["manager"]

            operation = "delete" if validated_params.get("state", "present") == "absent" else "create"
            license_data = AnsibleLicense(
                subscription_id=validated_params.get("subscription_id"),
                force=validated_params.get("force", False),
            )
            manifest_path = validated_params.get("manifest")
            if operation == "create" and manifest_path:
                license_data.manifest = self._read_manifest(manifest_path)

            params = asdict(license_data)
            params["_platform_check_mode"] = self._task.check_mode
            sdk_result = manager.execute(operation=operation, module_name=self.MODULE_NAME, ansible_data=params)

            # Keep the public module result without returning SDK input fields.
            result["changed"] = sdk_result["changed"]
            for key in ("license_info", "msg"):
                if key in sdk_result:
                    result[key] = sdk_result[key]

        except Exception as e:
            import traceback

            self._display.vvv("Error in license action plugin: %s" % e)
            result.setdefault("changed", False)
            result["failed"] = True
            result["msg"] = str(e)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result

    def _read_manifest(self, manifest_path):
        """Resolve an Ansible file and encode its contents for the SDK."""
        manifest_path = self._find_needle("files", manifest_path)
        with open(manifest_path, "rb") as manifest_file:
            return base64.b64encode(manifest_file.read()).decode("ascii")
