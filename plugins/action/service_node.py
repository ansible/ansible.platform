#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.service_node import AnsibleServiceNode


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "service_node"
    MODEL_CLASS = AnsibleServiceNode
    # service_cluster is a mutable FK: allow change-by-name detection even
    # when from_api() returns the current cluster as a digit string.
    _MUTABLE_FK_FIELDS = frozenset({"service_cluster"})
