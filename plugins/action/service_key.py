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
    # mark_previous_inactive: operation-time directive; API never returns it.
    # secret: write-only; API returns null/hash, not the original value.
    # Including either in _should_update() causes false positives.
    _WRITE_ONLY_FIELDS = frozenset({"mark_previous_inactive", "secret"})

    def _pre_execute_hook(self, ansible_data, write_only_data, validated_params, operation):
        """Re-inject write-only fields so they reach the API payload.

        ``mark_previous_inactive`` and ``secret`` are excluded from the
        AnsibleServiceKey dataclass (via _WRITE_ONLY_FIELDS) to prevent
        false-positive idempotency checks — the API never echoes these
        fields back in GET responses, so _should_update() would always
        see None vs. a user-supplied value and report changed.

        For create/update operations however, both fields must still reach
        the transform and ultimately the API request body.  This hook puts
        them back into ansible_data (from the write_only_data stash) so
        the transform can include them when they are non-None.

        Note: mark_previous_inactive=False is a valid explicit value and
        must not be filtered out here — only skip genuinely absent (None)
        values.
        """
        if operation in ("create", "update"):
            for field in ("mark_previous_inactive", "secret"):
                val = write_only_data.get(field)
                if val is not None:
                    ansible_data[field] = val
