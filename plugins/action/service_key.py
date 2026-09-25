#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.service_key import AnsibleServiceKey


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "service_key"
    MODEL_CLASS = AnsibleServiceKey

    # Gateway no longer permits creating service keys through its API.  Keep
    # accepting these arguments during their deprecation period, but do not
    # send them on update or attempted-create requests.
    _DEPRECATED_FIELDS = {
        "service_cluster": (
            "The 'service_cluster' parameter is deprecated because Gateway no longer permits creating service keys through its API.",
            "4.0.0",
        ),
        "secret": (
            "The 'secret' parameter is deprecated because Gateway no longer permits creating service keys through its API.",
            "4.0.0",
        ),
        "secret_length": (
            "The 'secret_length' parameter is deprecated because Gateway no longer permits creating service keys through its API.",
            "4.0.0",
        ),
        "mark_previous_inactive": (
            "The 'mark_previous_inactive' parameter is deprecated because Gateway no longer permits creating service keys through its API.",
            "4.0.0",
        ),
        "algorithm": (
            "The 'algorithm' parameter is deprecated because Gateway no longer permits creating service keys through its API.",
            "4.0.0",
        ),
    }
