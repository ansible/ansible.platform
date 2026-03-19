#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.service module.

Delegates to the module so service tasks use the same action-plugin-based
flow. Gateway config comes from task vars or module_defaults.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):
    """Action plugin for service; runs the module."""

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}
        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp
        return self._execute_module(
            module_name='ansible.platform.service',
            task_vars=task_vars,
        )
