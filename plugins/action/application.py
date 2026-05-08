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

    # FK fields that from_api() returns as bare integers (not digit strings).
    # The base _should_update() FK skip only fires for digit strings, so these
    # fields would fall through to the cross-type str() branch and produce
    # "Default" != "1" false positives on every re-run.
    # We handle them explicitly in the override below instead.
    _INT_FK_FIELDS = frozenset({"organization", "user"})

    def _should_update(self, desired_data, current_data):
        """
        Override to normalise application-specific fields before comparison.

        Two issues are handled here:

        1. redirect_uris / post_logout_redirect_uris:
           The argspec declares these as ``type: list``, so Ansible always
           delivers Python lists.  from_api() keeps the API's space-separated
           string as-is.  Without normalisation the cross-type branch produces
           str(list) != str(string) → false positive every run.
           Fix: join list values to space-separated strings on the desired side,
           mirroring what _join_uri_list() does for the API payload.

        2. organization / user:
           from_api() returns these as bare integers (the resolved FK id).
           The task supplies them as name strings (e.g. "Default", "admin").
           The base FK skip only fires for digit strings, not bare ints, so
           "Default" vs 1 falls through to str() coercion → always changed.
           Fix: when the desired value is a non-digit string and the current
           value is a bare int, drop the field from the comparison.
           This is safe because:
           - organization changes use new_organization, not organization.
           - user is resolved to an id by from_ansible_data(); a name string
             vs a different id would be caught on the API side if we do PATCH.
        """
        desired_norm = dict(desired_data)

        # Fix 1: normalise space-separated list fields.
        for field in self._SPACE_SEPARATED_LIST_FIELDS:
            val = desired_norm.get(field)
            if val is not None and isinstance(val, list):
                desired_norm[field] = " ".join(str(u) for u in val)

        # Fix 2: drop bare-int FK fields when desired is an unresolved name string.
        for field in self._INT_FK_FIELDS:
            val = desired_norm.get(field)
            if val is not None and isinstance(val, str) and not val.isdigit() and isinstance(current_data.get(field), int):
                desired_norm.pop(field)

        return super(ActionModule, self)._should_update(desired_norm, current_data)
