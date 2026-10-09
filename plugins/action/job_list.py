#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.job_list module.

This is a read-only module that lists controller jobs via the
/api/controller/v2/jobs/ endpoint using manager.search_api().
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for job_list module."""

    MODULE_NAME = "job_list"

    JOBS_ENDPOINT = "/api/controller/v2/jobs/"

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = dict()

        self._task_vars = task_vars
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        try:
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                from ansible.errors import AnsibleError

                raise AnsibleError("Could not load DOCUMENTATION for job_list module")

            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, "input")
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            validated_params = validated_input.validated_parameters
            status = validated_params.get("status")
            page = validated_params.get("page")
            all_pages = validated_params.get("all_pages", False)
            query = validated_params.get("query")

            # Build query parameters
            query_params = {}
            if status:
                query_params["status"] = status
            if page:
                query_params["page"] = page
            if query:
                query_params.update(query)

            # Use search_api to perform the GET request
            api_response = manager.search_api(
                self.JOBS_ENDPOINT,
                query_params=query_params if query_params else None,
                return_all=all_pages,
            )

            # Return the raw API response
            result["changed"] = False
            result["failed"] = False
            result.update(api_response)

        except Exception as e:
            import traceback

            self._display.vvv("Error in job_list action plugin: %s" % e)
            result["failed"] = True
            result["msg"] = str(e)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result
