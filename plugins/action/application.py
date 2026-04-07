#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.application import AnsibleApplication


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "application"
    MODEL_CLASS = AnsibleApplication

    # API-generated; returned flat only, not in the nested dict (not round-trip safe as input).
    _EXTRA_RETURN_FIELDS = frozenset({"client_id"})

    # redirect_uris fields are stored as space-separated strings by the API; split to list on output.
    _SPACE_SEPARATED_LIST_FIELDS = frozenset({"redirect_uris", "post_logout_redirect_uris"})
