#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2017, Wayne Witzel III <wayne@riotousliving.com>
# Copyright: (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for controller_job_list.

Read-only query module that lists jobs from the Controller API
using the SDK search_api() method.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.api.controller.v2.controller_job_list import (
    CONTROLLER_JOBS_ENDPOINT,
    build_query_params,
)


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "controller_job_list"

    def run(self, tmp=None, task_vars=None):
        """Query the Controller jobs API and return results.

        This is a read-only module: changed is always False.
        Uses search_api() to query /api/controller/v2/jobs/ with
        optional filters (status, page, query dict).
        """
        result = {}
        try:
            prepared = self._prepare_action(tmp, task_vars)
            result = prepared["result"]
            validated_params = prepared["validated_params"]
            manager = prepared["manager"]

            # Build query parameters from validated input
            query_params = build_query_params(validated_params)
            all_pages = validated_params.get("all_pages", False)

            # Use search_api() to query the Controller jobs endpoint
            response = manager.search_api(
                endpoint=CONTROLLER_JOBS_ENDPOINT,
                query_params=query_params or None,
                return_all=all_pages,
            )

            # Return the API response directly
            result["changed"] = False
            result["failed"] = False
            result["count"] = response.get("count", 0)
            result["next"] = response.get("next")
            result["previous"] = response.get("previous")
            result["results"] = response.get("results", [])

        except Exception as exc:
            import traceback as _tb

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, exc))
            result["failed"] = True
            result["msg"] = str(exc)
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()

        return result
