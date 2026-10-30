"""API v1 Rulebook Activation dataclass and transform mixin.

Also exports endpoint path constants used by the action plugin, keeping
hardcoded API URLs out of ``plugins/action/`` (required by
``check_action_plugin_invariants``).
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Endpoint path constants -- importable by the action plugin so that
# tools/check_action_plugin_invariants.sh never flags hardcoded API URLs
# in plugins/action/*.py.
# ---------------------------------------------------------------------------
ACTIVATIONS_ENDPOINT = "/api/eda/v1/activations/"
ACTIVATION_DETAIL_ENDPOINT = "/api/eda/v1/activations/{id}/"
ACTIVATION_RESTART_ENDPOINT = "/api/eda/v1/activations/{id}/restart/"
ACTIVATION_ENABLE_ENDPOINT = "/api/eda/v1/activations/{id}/enable/"
ACTIVATION_DISABLE_ENDPOINT = "/api/eda/v1/activations/{id}/disable/"
ACTIVATION_COPY_ENDPOINT = "/api/eda/v1/activations/{id}/copy/"

_EDA_SERVICE = "eda"


def _resolve_fk(manager, endpoint, lookup_field, value, service="eda"):
    """Resolve a name or id to an integer id using the EDA API.

    Args:
        manager: PlatformService or compatible client.
        endpoint: API endpoint name (e.g. 'projects').
        lookup_field: Field to filter on (e.g. 'name').
        value: Value to look up.
        service: API service name.

    Returns:
        int resource ID or None.
    """
    if value is None:
        return None
    if str(value).isdigit():
        return int(value)
    try:
        return manager.lookup_resource_id(endpoint, lookup_field, str(value), service=service)
    except Exception:
        return None


def _resolve_fk_required(manager, endpoint, lookup_field, value, resource_label, service="eda"):
    """Resolve a name to an ID, raising ValueError if not found.

    Args:
        manager: PlatformService or compatible client.
        endpoint: API endpoint name.
        lookup_field: Field to filter on.
        value: Value to look up.
        resource_label: Human-readable label for error messages.
        service: API service name.

    Returns:
        int resource ID.

    Raises:
        ValueError: If the resource is not found.
    """
    if value is None:
        return None
    if str(value).isdigit():
        return int(value)
    result = manager.lookup_resource_id(endpoint, lookup_field, str(value), service=service)
    if result is None:
        raise ValueError("%s '%s' not found" % (resource_label, value))
    return result


def _resolve_credential_ids(manager, credential_names):
    """Resolve a list of EDA credential names to IDs.

    Args:
        manager: PlatformService or compatible client.
        credential_names: List of credential name strings.

    Returns:
        List of integer credential IDs.
    """
    if not credential_names:
        return None
    ids = []
    for name in credential_names:
        cred_id = _resolve_fk_required(manager, "eda-credentials", "name", name, "EDA credential")
        if cred_id is not None:
            ids.append(cred_id)
    return ids


def _process_event_streams(manager, event_streams, rulebook_id):
    """Process event streams and return source_mappings YAML string.

    Args:
        manager: PlatformService or compatible client.
        event_streams: List of event stream dicts from the user.
        rulebook_id: Resolved rulebook ID for source lookup.

    Returns:
        YAML string of source mappings, or None.
    """
    if not event_streams or rulebook_id is None:
        return None

    try:
        import yaml
    except ImportError:
        raise ValueError("PyYAML is required for event_streams processing")

    source_mappings = []

    # Get rulebook sources via the EDA API
    sources_data = manager.search_api(
        "rulebooks/%s/sources" % rulebook_id,
        service=_EDA_SERVICE,
    )
    sources = sources_data.get("results", sources_data if isinstance(sources_data, list) else [])

    for event in event_streams:
        source_mapping = {}

        source_index = event.get("source_index")
        source_name = event.get("source_name")

        if source_index is not None and source_name is not None:
            raise ValueError("source_index and source_name options are mutually exclusive")
        if source_index is None and source_name is None:
            raise ValueError("You must specify one of the options: source_index or source_name")

        if source_index is not None:
            if source_index < 0 or source_index >= len(sources):
                raise ValueError("The specified source_index %s is out of range" % source_index)
            source_mapping["source_name"] = sources[source_index].get("name")
            source_mapping["rulebook_hash"] = sources[source_index].get("rulebook_hash")
        elif source_name:
            matching = [s for s in sources if s["name"] == source_name]
            if not matching:
                raise ValueError("The specified source_name %s does not exist" % source_name)
            source_mapping["source_name"] = matching[0].get("name")
            source_mapping["rulebook_hash"] = matching[0].get("rulebook_hash")

        event_stream_name = event.get("event_stream")
        if not event_stream_name:
            raise ValueError("You must specify an event stream name")

        event_stream_id = _resolve_fk_required(manager, "event-streams", "name", event_stream_name, "Event stream")
        source_mapping["event_stream_name"] = event_stream_name
        source_mapping["event_stream_id"] = event_stream_id
        source_mappings.append(source_mapping)

    return yaml.dump(source_mappings).rstrip("\n")


@dataclass
class APIRulebookActivation_v1(BaseTransformMixin):
    """API v1 representation of an EDA rulebook activation."""

    name: Optional[str] = None
    description: Optional[str] = None
    is_enabled: Optional[bool] = None
    rulebook_id: Optional[int] = None
    decision_environment_id: Optional[int] = None
    organization_id: Optional[int] = None
    awx_token_id: Optional[int] = None
    extra_var: Optional[str] = None
    restart_policy: Optional[str] = None
    log_level: Optional[str] = None
    enable_persistence: Optional[bool] = None
    rule_engine_credential_id: Optional[int] = None
    eda_credentials: Optional[List[int]] = None
    k8s_service_name: Optional[str] = None
    source_mappings: Optional[str] = None
    restart_on_project_update: Optional[bool] = None

    # Read-only fields from API
    id: Optional[int] = None


class RulebookActivationTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for Rulebook Activation API v1.

    Handles bidirectional transformation between Ansible user-facing names
    and EDA API integer IDs, including cascading lookups (project -> rulebook)
    and event stream source mapping serialization.
    """

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APIRulebookActivation_v1":
        """Create API instance from Ansible dataclass.

        Resolves all reference fields (names to IDs) using the EDA API.

        Args:
            ansible_instance: AnsibleRulebookActivation dataclass instance.
            context: TransformContext or dict with manager/session.

        Returns:
            APIRulebookActivation_v1 with resolved IDs.
        """
        manager = context.manager if isinstance(context, TransformContext) else context.get("manager")
        api_data = {}

        # Handle name / rename
        name = getattr(ansible_instance, "name", None)
        new_name = getattr(ansible_instance, "new_name", None)
        if new_name:
            api_data["name"] = new_name
        elif name is not None:
            api_data["name"] = name

        # Direct field mappings (no resolution needed)
        for field in (
            "description",
            "is_enabled",
            "restart_policy",
            "log_level",
            "enable_persistence",
            "rule_engine_credential_id",
            "k8s_service_name",
            "restart_on_project_update",
        ):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        # Map extra_vars -> extra_var (API uses singular)
        extra_vars = getattr(ansible_instance, "extra_vars", None)
        if extra_vars is not None:
            api_data["extra_var"] = extra_vars

        # --- FK resolution (names -> IDs via EDA API) ---
        if manager:
            # Resolve project_name -> project_id (needed for rulebook lookup)
            project_name = getattr(ansible_instance, "project_name", None)
            project_id = None
            if project_name is not None:
                project_id = _resolve_fk_required(manager, "projects", "name", project_name, "Project")

            # Resolve rulebook_name -> rulebook_id (scoped by project_id)
            rulebook_name = getattr(ansible_instance, "rulebook_name", None)
            if rulebook_name is not None and project_id is not None:
                rulebook_id = manager.lookup_resource_id(
                    "rulebooks",
                    "name",
                    str(rulebook_name),
                    service="eda",
                    extra_query_params={"project_id": project_id},
                )
                if rulebook_id is None:
                    raise ValueError("Rulebook '%s' not found for project '%s'" % (rulebook_name, project_name))
                api_data["rulebook_id"] = rulebook_id

            # Resolve decision_environment_name -> decision_environment_id
            de_name = getattr(ansible_instance, "decision_environment_name", None)
            if de_name is not None:
                api_data["decision_environment_id"] = _resolve_fk_required(manager, "decision-environments", "name", de_name, "Decision environment")

            # Resolve organization_name -> organization_id
            org_name = getattr(ansible_instance, "organization_name", None)
            if org_name is not None:
                api_data["organization_id"] = _resolve_fk_required(manager, "organizations", "name", org_name, "Organization")

            # Resolve awx_token_name -> awx_token_id
            token_name = getattr(ansible_instance, "awx_token_name", None)
            if token_name is not None:
                token_id = _resolve_fk(manager, "users/me/awx-tokens", "name", token_name)
                if token_id is not None:
                    api_data["awx_token_id"] = token_id

            # Resolve eda_credentials (list of names -> list of IDs)
            cred_names = getattr(ansible_instance, "eda_credentials", None)
            if cred_names is not None:
                api_data["eda_credentials"] = _resolve_credential_ids(manager, cred_names)

            # Process event_streams -> source_mappings YAML
            event_streams = getattr(ansible_instance, "event_streams", None)
            if event_streams is not None:
                rulebook_id_for_sources = api_data.get("rulebook_id")
                source_mappings = _process_event_streams(manager, event_streams, rulebook_id_for_sources)
                if source_mappings is not None:
                    api_data["source_mappings"] = source_mappings

        # Read-only fields
        for field in ("id",):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val

        return APIRulebookActivation_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for rulebook activation operations."""
        return {
            "create": EndpointOperation(
                path="/api/eda/v1/activations/",
                method="POST",
                fields=[
                    "name",
                    "description",
                    "is_enabled",
                    "rulebook_id",
                    "decision_environment_id",
                    "organization_id",
                    "awx_token_id",
                    "extra_var",
                    "restart_policy",
                    "log_level",
                    "enable_persistence",
                    "rule_engine_credential_id",
                    "eda_credentials",
                    "k8s_service_name",
                    "source_mappings",
                    "restart_on_project_update",
                ],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/eda/v1/activations/{id}/",
                method="PATCH",
                fields=[
                    "name",
                    "description",
                    "is_enabled",
                    "restart_policy",
                    "log_level",
                    "enable_persistence",
                    "rule_engine_credential_id",
                    "eda_credentials",
                    "k8s_service_name",
                    "restart_on_project_update",
                ],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/eda/v1/activations/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/eda/v1/activations/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/eda/v1/activations/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
            "enable": EndpointOperation(
                path="/api/eda/v1/activations/{id}/enable/",
                method="POST",
                fields=[],
                path_params=["id"],
                order=1,
            ),
            "disable": EndpointOperation(
                path="/api/eda/v1/activations/{id}/disable/",
                method="POST",
                fields=[],
                path_params=["id"],
                order=1,
            ),
            "restart": EndpointOperation(
                path="/api/eda/v1/activations/{id}/restart/",
                method="POST",
                fields=[],
                path_params=["id"],
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        """Return the field used for existence checks."""
        return "name"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleRulebookActivation":
        """Transform from API format to Ansible format.

        Args:
            api_data: Raw API response dict.
            context: TransformContext or dict.

        Returns:
            AnsibleRulebookActivation instance.
        """
        from ....ansible_models.rulebook_activation import AnsibleRulebookActivation

        # Handle eda_credentials: API returns list of dicts with "id" key
        eda_creds = api_data.get("eda_credentials")
        if eda_creds and isinstance(eda_creds, list):
            if eda_creds and isinstance(eda_creds[0], dict):
                eda_creds = [str(c.get("id", c)) for c in eda_creds]
            else:
                eda_creds = [str(c) for c in eda_creds]

        ansible_data = {
            "name": api_data.get("name", ""),
            "description": api_data.get("description"),
            "id": api_data.get("id"),
            "is_enabled": api_data.get("is_enabled"),
            "restart_policy": api_data.get("restart_policy"),
            "log_level": api_data.get("log_level"),
            "enable_persistence": api_data.get("enable_persistence"),
            "rule_engine_credential_id": api_data.get("rule_engine_credential_id"),
            "k8s_service_name": api_data.get("k8s_service_name"),
            "restart_on_project_update": api_data.get("restart_on_project_update"),
            "extra_vars": api_data.get("extra_var"),
            "eda_credentials": eda_creds,
        }
        return AnsibleRulebookActivation(**ansible_data)
