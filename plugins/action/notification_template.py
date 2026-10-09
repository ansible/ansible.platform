#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.notification_template import AnsibleNotificationTemplate


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = "notification_template"
    MODEL_CLASS = AnsibleNotificationTemplate
