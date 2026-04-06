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

    # client_id is API-generated (not in argument_spec) so it must not appear
    # inside the nested 'application' round-trip dict.  It is returned flat
    # only, for backward compatibility with <=2.6 playbooks that read
    # result.client_id after creating an OAuth application.
    # Deprecated in 2.7, scheduled for removal after 2028-04-01.
    _EXTRA_RETURN_FIELDS = frozenset({"client_id"})
