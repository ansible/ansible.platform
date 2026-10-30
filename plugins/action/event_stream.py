#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.event_stream module.

Manages EDA event streams via the standard CRUD state machine provided
by BaseResourceActionPlugin.  Field renames (forward_events -> test_mode,
headers -> additional_data_headers) and FK resolution (credential_name,
organization_name) are handled by the transform layer.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.event_stream import AnsibleEventStream


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for event_stream module."""

    MODULE_NAME = "event_stream"
    MODEL_CLASS = AnsibleEventStream
    LOOKUP_FIELD = "name"

    _DEPRECATED_FIELDS = {
        "event_stream_type": (
            "The event_stream_type parameter is deprecated and will be removed in version 3.0.0.",
            "3.0.0",
        ),
    }

    # credential_name and organization_name are FK fields whose values can
    # change via update.  Suppress the non-digit-name vs digit-string skip
    # in _should_update() so genuine FK changes trigger the update path.
    _MUTABLE_FK_FIELDS = frozenset({"credential_name", "organization_name"})
