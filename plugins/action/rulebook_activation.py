#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Action plugin for ansible.platform.rulebook_activation module.

Rulebook activations support create, update, delete, enable, disable, and
restart operations.  The action plugin handles all FK resolution (project,
rulebook, decision environment, organization, AWX token, EDA credentials,
event streams) and state transitions (enabled/disabled/restart) directly
via the manager API.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from typing import Any, Dict

import yaml
from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.rulebook_activation import AnsibleRulebookActivation
from ansible_collections.ansible.platform.plugins.plugin_utils.api.eda.v1.rulebook_activation import (
    ACTIVATION_DETAIL_ENDPOINT,
    ACTIVATION_DISABLE_ENDPOINT,
    ACTIVATION_ENABLE_ENDPOINT,
    ACTIVATION_RESTART_ENDPOINT,
    ACTIVATIONS_ENDPOINT,
)


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for rulebook_activation module."""

    MODULE_NAME = "rulebook_activation"
    MODEL_CLASS = AnsibleRulebookActivation

    def run(self, tmp=None, task_vars=None):
        """Execute rulebook activation management.

        Handles the full lifecycle: create, update, delete, enable,
        disable, and restart operations with FK resolution.

        Args:
            tmp: Deprecated parameter.
            task_vars: Task variables dictionary.

        Returns:
            dict: Ansible result dictionary.
        """
        if task_vars is None:
            task_vars = dict()

        self._task_vars = task_vars
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        try:
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                raise AnsibleError("Could not load DOCUMENTATION for %s module" % self.MODULE_NAME)

            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, "input")
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            if facts_to_set:
                result["ansible_facts"] = facts_to_set
                result["_ansible_facts_cacheable"] = True

            params = validated_input.validated_parameters
            name = params.get("name")
            new_name = params.get("new_name")
            state = params.get("state", "present")
            restart = params.get("restart", False)

            # ---- restart (non-idempotent) ------------------------------------
            if restart:
                return self._handle_restart(manager, name, result)

            # ---- find existing activation ------------------------------------
            existing = self._find_activation(manager, name)

            # ---- state: absent -----------------------------------------------
            if state == "absent":
                return self._handle_absent(manager, name, existing, result)

            # ---- state: enabled/disabled on existing activation ---------------
            if state in ("enabled", "disabled") and existing:
                return self._handle_state_transition(manager, state, existing, result)

            # ---- create or update --------------------------------------------
            return self._handle_create_or_update(manager, params, state, name, new_name, existing, result)

        except Exception as e:
            import traceback

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, e))
            result["failed"] = True
            result["msg"] = str(e)
            if self._display.verbosity >= 3:
                result["exception"] = traceback.format_exc()

        return result

    def _find_activation(self, manager, name):
        """Find an existing activation by name.

        Args:
            manager: The platform manager client.
            name: Name of the activation to find.

        Returns:
            dict or None: The activation data if found, None otherwise.
        """
        try:
            find_result = manager.execute(
                operation="find",
                module_name=self.MODULE_NAME,
                ansible_data={"name": name},
            )
            if find_result and find_result.get("id"):
                return find_result
        except ValueError as e:
            if "not found" not in str(e).lower() and "404" not in str(e):
                raise
        return None

    def _handle_restart(self, manager, name, result):
        """Handle restart operation.

        Args:
            manager: The platform manager client.
            name: Activation name.
            result: Result dict to update.

        Returns:
            dict: Updated result.
        """
        existing = self._find_activation(manager, name)
        if not existing:
            raise AnsibleError("Cannot restart activation that does not exist: %s" % name)
        if self._task.check_mode:
            result.update({"changed": True, "failed": False, self.MODULE_NAME: existing})
            return result
        manager.direct_request("POST", ACTIVATION_RESTART_ENDPOINT.format(id=existing["id"]))
        result.update(
            {
                "changed": True,
                "failed": False,
                self.MODULE_NAME: existing,
                "id": existing["id"],
            }
        )
        return result

    def _handle_absent(self, manager, name, existing, result):
        """Handle state=absent (delete).

        Args:
            manager: The platform manager client.
            name: Activation name.
            existing: Existing activation data or None.
            result: Result dict to update.

        Returns:
            dict: Updated result.
        """
        if not existing:
            result.update(
                {
                    "changed": False,
                    "failed": False,
                    self.MODULE_NAME: {"state": "absent"},
                    "msg": "%s '%s' does not exist (already absent)" % (self.MODULE_NAME, name),
                }
            )
            return result
        if self._task.check_mode:
            result.update(
                {
                    "changed": True,
                    "failed": False,
                    self.MODULE_NAME: {"state": "absent", "id": existing["id"]},
                }
            )
            return result
        manager.direct_request("DELETE", ACTIVATION_DETAIL_ENDPOINT.format(id=existing["id"]))
        result.update(
            {
                "changed": True,
                "failed": False,
                self.MODULE_NAME: {"state": "absent", "id": existing["id"]},
            }
        )
        return result

    def _handle_state_transition(self, manager, state, existing, result):
        """Handle enable/disable state transition on existing activation.

        Args:
            manager: The platform manager client.
            state: Desired state ('enabled' or 'disabled').
            existing: Existing activation data.
            result: Result dict to update.

        Returns:
            dict: Updated result.
        """
        is_enabled = existing.get("is_enabled", False)
        need_enable = state == "enabled" and not is_enabled
        need_disable = state == "disabled" and is_enabled

        if need_enable or need_disable:
            if self._task.check_mode:
                result.update({"changed": True, "failed": False, self.MODULE_NAME: existing})
                return result
            endpoint = ACTIVATION_ENABLE_ENDPOINT if need_enable else ACTIVATION_DISABLE_ENDPOINT
            manager.direct_request("POST", endpoint.format(id=existing["id"]))
            result.update(
                {
                    "changed": True,
                    "failed": False,
                    self.MODULE_NAME: existing,
                    "id": existing["id"],
                }
            )
            return result

        # Already in correct state
        result.update(
            {
                "changed": False,
                "failed": False,
                self.MODULE_NAME: existing,
                "id": existing["id"],
            }
        )
        return result

    def _handle_create_or_update(self, manager, params, state, name, new_name, existing, result):
        """Handle create or update of an activation.

        Args:
            manager: The platform manager client.
            params: Validated module parameters.
            state: Desired state.
            name: Current activation name.
            new_name: New name for rename (or None).
            existing: Existing activation data or None.
            result: Result dict to update.

        Returns:
            dict: Updated result.
        """
        payload = self._build_activation_payload(manager, params, state)
        payload["name"] = new_name if new_name else (existing.get("name", name) if existing else name)

        if self._task.check_mode:
            result.update(
                {
                    "changed": True,
                    "failed": False,
                    self.MODULE_NAME: {"name": payload["name"]},
                }
            )
            return result

        if existing:
            api_result = manager.direct_request(
                "PATCH",
                ACTIVATION_DETAIL_ENDPOINT.format(id=existing["id"]),
                data=payload,
            )
        else:
            api_result = manager.direct_request(
                "POST",
                ACTIVATIONS_ENDPOINT,
                data=payload,
            )

        result.update(
            {
                "changed": True,
                "failed": False,
                self.MODULE_NAME: api_result,
                "id": api_result.get("id"),
            }
        )
        return result

    def _build_activation_payload(self, manager, params, state):
        """Build the API payload with resolved FK references.

        Args:
            manager: The platform manager client.
            params: Validated module parameters.
            state: Desired state.

        Returns:
            dict: API-ready payload with resolved IDs.
        """
        payload: Dict[str, Any] = {}

        # Resolve project_name -> project_id
        project_name = params.get("project_name")
        project_id = None
        if project_name:
            project_id = manager.lookup_resource_id(
                "projects",
                "name",
                project_name,
                service="eda",
            )
            if project_id is None:
                raise AnsibleError("Project '%s' not found." % project_name)

        # Resolve rulebook_name -> rulebook_id (needs project_id)
        rulebook_name = params.get("rulebook_name")
        rulebook_id = None
        if rulebook_name and project_id is not None:
            rulebook_id = manager.lookup_resource_id(
                "rulebooks",
                "name",
                rulebook_name,
                service="eda",
                extra_query_params={"project_id": project_id},
            )
            if rulebook_id is None:
                raise AnsibleError("Rulebook '%s' not found for project '%s'." % (rulebook_name, project_name))
            payload["rulebook_id"] = rulebook_id

        # Resolve decision_environment_name -> decision_environment_id
        de_name = params.get("decision_environment_name")
        if de_name:
            de_id = manager.lookup_resource_id(
                "decision-environments",
                "name",
                de_name,
                service="eda",
            )
            if de_id is None:
                raise AnsibleError("Decision Environment '%s' not found." % de_name)
            payload["decision_environment_id"] = de_id

        # Resolve organization_name -> organization_id
        org_name = params.get("organization_name")
        if org_name:
            org_id = manager.lookup_resource_id(
                "organizations",
                "name",
                org_name,
                service="eda",
            )
            if org_id is None:
                raise AnsibleError("Organization '%s' not found." % org_name)
            payload["organization_id"] = org_id

        # Resolve awx_token_name -> awx_token_id
        token_name = params.get("awx_token_name")
        if token_name:
            token_id = manager.lookup_resource_id(
                "users/me/awx-tokens",
                "name",
                token_name,
                service="eda",
            )
            if token_id is not None:
                payload["awx_token_id"] = token_id

        # Resolve eda_credentials -> credential IDs
        cred_names = params.get("eda_credentials")
        if cred_names:
            cred_ids = []
            for cred_name in cred_names:
                cred_id = manager.lookup_resource_id(
                    "eda-credentials",
                    "name",
                    cred_name,
                    service="eda",
                )
                if cred_id is not None:
                    cred_ids.append(cred_id)
            payload["eda_credentials"] = cred_ids

        # Process event_streams -> source_mappings
        if params.get("event_streams") and rulebook_id is not None:
            payload["source_mappings"] = self._process_event_streams(
                manager,
                rulebook_id,
                params,
            )

        # k8s_service_name
        if params.get("k8s_service_name"):
            payload["k8s_service_name"] = params["k8s_service_name"]

        # Simple scalar fields
        if params.get("description") is not None:
            payload["description"] = params["description"]
        if params.get("extra_vars"):
            payload["extra_var"] = params["extra_vars"]
        if params.get("restart_policy"):
            payload["restart_policy"] = params["restart_policy"]
        if params.get("log_level"):
            payload["log_level"] = params["log_level"]
        if params.get("enable_persistence") is not None:
            payload["enable_persistence"] = params["enable_persistence"]
        if params.get("rule_engine_credential_id") is not None:
            payload["rule_engine_credential_id"] = params["rule_engine_credential_id"]
        if params.get("restart_on_project_update") is not None:
            payload["restart_on_project_update"] = params["restart_on_project_update"]

        # Set is_enabled based on state
        payload["is_enabled"] = state != "disabled"

        return payload

    def _process_event_streams(self, manager, rulebook_id, params):
        """Process event streams and return source_mappings YAML string.

        Args:
            manager: The platform manager client.
            rulebook_id: The resolved rulebook ID.
            params: Validated module parameters.

        Returns:
            str: YAML-serialized source mappings.
        """
        # Get rulebook sources
        sources_result = manager.search_api(
            "rulebooks/%s/sources" % rulebook_id,
            service="eda",
        )
        sources = sources_result if isinstance(sources_result, list) else sources_result.get("results", [])

        source_mappings = []
        for event in params.get("event_streams", []):
            source_mapping: Dict[str, Any] = {}

            source_index = event.get("source_index")
            source_name = event.get("source_name")

            if source_index is not None and source_name is not None:
                raise AnsibleError("source_index and source_name options are mutually exclusive.")
            if source_index is None and source_name is None:
                raise AnsibleError("You must specify one of the options: source_index or source_name.")

            if source_index is not None:
                if source_index >= len(sources):
                    raise AnsibleError("The specified source_index %s is out of range." % source_index)
                source_mapping["source_name"] = sources[source_index].get("name")
                source_mapping["rulebook_hash"] = sources[source_index].get("rulebook_hash")
            elif source_name:
                match = next((s for s in sources if s["name"] == source_name), None)
                if not match:
                    raise AnsibleError("The specified source_name '%s' does not exist." % source_name)
                source_mapping["source_name"] = match.get("name")
                source_mapping["rulebook_hash"] = match.get("rulebook_hash")

            event_stream_name = event.get("event_stream")
            if not event_stream_name:
                raise AnsibleError("You must specify an event stream name.")

            event_stream_id = manager.lookup_resource_id(
                "event-streams",
                "name",
                event_stream_name,
                service="eda",
            )
            if event_stream_id is None:
                raise AnsibleError("The event stream '%s' does not exist." % event_stream_name)

            source_mapping["event_stream_name"] = event_stream_name
            source_mapping["event_stream_id"] = event_stream_id
            source_mappings.append(source_mapping)

        return yaml.dump(source_mappings).rstrip("\n")
