#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.route import AnsibleRoute


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "route"
    MODEL_CLASS = AnsibleRoute

    # Gateway API schema defaults for proxy timeout floors.
    # These are used when the settings endpoint does not return the value
    # (older gateway versions may not expose all settings keys).
    _DEFAULT_REQUEST_TIMEOUT_FLOOR = 30  # seconds; gateway API schema default
    _DEFAULT_IDLE_TIMEOUT_FLOOR = 15  # seconds; gateway API schema default

    def _pre_execute_hook(self, ansible_data, write_only_data, validated_params, operation):
        """Validate route timeout values against global proxy settings floors.

        The gateway settings expose ``request_timeout`` and ``idle_timeout`` as
        the minimum values that individual route timeouts may not go below.
        Rejecting out-of-range values client-side gives a clear error message
        before any PATCH is sent.

        Floor values are read from ``/api/gateway/v1/settings/all/``.  When a
        key is absent or null (older gateway versions), the API schema defaults
        (30 s for request_timeout, 15 s for idle_timeout) are used instead.
        """
        if operation not in ("create", "update"):
            return

        request_timeout_seconds = ansible_data.get("request_timeout_seconds")
        idle_timeout_seconds = ansible_data.get("idle_timeout_seconds")

        if request_timeout_seconds is None and idle_timeout_seconds is None:
            return

        # Fetch global settings to determine the floor values.
        # Fall back to schema defaults on any error (e.g. permissions) so that
        # the most conservative floor is always enforced.
        global_settings = {}
        try:
            settings_result = self._client.execute(
                operation="find",
                module_name="settings",
                ansible_data={"settings": {}},
            )
            global_settings = (settings_result or {}).get("settings") or {}
        except Exception:
            pass  # use schema defaults below

        # Use schema defaults when the key is absent or null in the response.
        floor_request = global_settings.get("request_timeout") or self._DEFAULT_REQUEST_TIMEOUT_FLOOR
        floor_idle = global_settings.get("idle_timeout") or self._DEFAULT_IDLE_TIMEOUT_FLOOR

        errors = []

        if request_timeout_seconds is not None:
            try:
                if int(request_timeout_seconds) < int(floor_request):
                    errors.append(
                        "request_timeout_seconds ({val}) is below the global proxy request_timeout floor ({floor})".format(
                            val=request_timeout_seconds, floor=floor_request
                        )
                    )
            except (TypeError, ValueError):
                pass

        if idle_timeout_seconds is not None:
            try:
                if int(idle_timeout_seconds) < int(floor_idle):
                    errors.append(
                        "idle_timeout_seconds ({val}) is below the global proxy idle_timeout floor ({floor})".format(val=idle_timeout_seconds, floor=floor_idle)
                    )
            except (TypeError, ValueError):
                pass

        if errors:
            raise ValueError("; ".join(errors))
