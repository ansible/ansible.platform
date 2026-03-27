#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.service_key import AnsibleServiceKey


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = 'service_key'
    MODEL_CLASS = AnsibleServiceKey
    # mark_previous_inactive: operation-time directive; API never returns it.
    # secret: write-only; API returns null/hash, not the original value.
    # Including either in _should_update() causes false positives.
    _WRITE_ONLY_FIELDS = frozenset({'mark_previous_inactive', 'secret'})
