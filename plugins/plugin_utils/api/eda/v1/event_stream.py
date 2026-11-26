"""API v1 Event Stream dataclass and transform mixin."""

import logging
import uuid as uuid_mod
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APIEventStream_v1(BaseTransformMixin):
    """API v1 representation of an EDA event stream.

    Note: The API uses ``test_mode`` (inverted logic of the user-facing
    ``forward_events`` boolean) and ``additional_data_headers`` instead of
    ``headers``.  Reference fields are integer IDs.
    """

    name: Optional[str] = None
    eda_credential_id: Optional[int] = None
    organization_id: Optional[int] = None
    test_mode: Optional[bool] = None
    additional_data_headers: Optional[str] = None
    uuid: Optional[str] = None

    # Read-only fields from API
    id: Optional[int] = None


class EventStreamTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for Event Stream API v1."""

    require_unique_lookup = True

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> "APIEventStream_v1":
        """Create API instance from Ansible dataclass.

        Handles field renames (forward_events -> test_mode, headers ->
        additional_data_headers), reference field resolution (credential_name
        and organization_name to IDs), and UUID format validation.
        """
        api_data: Dict[str, Any] = {}

        op = context.operation if isinstance(context, TransformContext) else context.get("operation")

        # --- name / new_name handling ---
        name = getattr(ansible_instance, "name", None)
        new_name = getattr(ansible_instance, "new_name", None)

        if op == "create":
            api_data["name"] = name or new_name or ""
        elif op in ("update", "enforced"):
            if new_name is not None:
                api_data["name"] = new_name
            elif name is not None and not str(name).strip().isdigit():
                api_data["name"] = name
        else:
            api_data["name"] = name or new_name or ""

        mgr = context.manager if isinstance(context, TransformContext) else context.get("manager")

        # Resolve the organization first so credential names can be scoped to
        # the event stream's organization.
        organization_name = getattr(ansible_instance, "organization_name", None)
        if organization_name is not None:
            api_data["organization_id"] = cls.resolve_reference_id(mgr, "organizations", organization_name, service="eda")

        # --- credential_name -> eda_credential_id ---
        credential_name = getattr(ansible_instance, "credential_name", None)
        if credential_name is not None:
            org_scope = {"organization": api_data["organization_id"]} if api_data.get("organization_id") is not None else None
            api_data["eda_credential_id"] = cls.resolve_reference_id(
                mgr,
                "eda-credentials",
                credential_name,
                service="eda",
                extra_query_params=org_scope,
            )

        if op == "create":
            if not credential_name:
                raise ValueError("credential_name is required to create an event stream")
            if organization_name is None:
                raise ValueError("organization_name is required to create an event stream")

        # --- forward_events (bool) -> test_mode (inverted bool) ---
        forward_events = getattr(ansible_instance, "forward_events", None)
        if forward_events is not None:
            api_data["test_mode"] = not forward_events
        elif op == "create":
            api_data["test_mode"] = True

        # --- headers -> additional_data_headers ---
        headers = getattr(ansible_instance, "headers", None)
        if headers is not None:
            api_data["additional_data_headers"] = headers

        # --- uuid (with format validation) ---
        uuid_val = getattr(ansible_instance, "uuid", None)
        if uuid_val is not None:
            try:
                uuid_mod.UUID(uuid_val)
            except ValueError:
                raise ValueError("Invalid UUID format: %s" % uuid_val)
            api_data["uuid"] = uuid_val

        # Read-only fields
        for ro in ("id",):
            val = getattr(ansible_instance, ro, None)
            if val is not None:
                api_data[ro] = val

        return APIEventStream_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Define API endpoints for EDA event stream operations."""
        fields = [
            "name",
            "eda_credential_id",
            "organization_id",
            "test_mode",
            "additional_data_headers",
            "uuid",
        ]

        return {
            "create": EndpointOperation(
                path="/api/eda/v1/event-streams/",
                method="POST",
                fields=fields,
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/eda/v1/event-streams/{id}/",
                method="PATCH",
                fields=fields,
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/eda/v1/event-streams/{id}/",
                method="DELETE",
                fields=[],
                path_params=["id"],
                required_for="delete",
                order=1,
            ),
            "get": EndpointOperation(
                path="/api/eda/v1/event-streams/{id}/",
                method="GET",
                fields=[],
                path_params=["id"],
                required_for="find",
                order=1,
            ),
            "list": EndpointOperation(
                path="/api/eda/v1/event-streams/",
                method="GET",
                fields=[],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        """Return the field used to look up existing resources."""
        return "name"

    @classmethod
    def get_find_list_query_params(cls, ansible_data) -> Dict[str, Any]:
        """Scope event stream name lookups to the requested EDA organization."""
        organization_id = getattr(ansible_data, "organization_id", None)
        return {"organization_id": organization_id} if organization_id is not None else {}

    @staticmethod
    def resolve_reference_id(manager, endpoint: str, value, service: str = "eda", extra_query_params: Optional[dict] = None) -> Optional[int]:
        """Resolve a numeric ID or a unique resource name to an API ID."""
        if value is None:
            return None
        value_str = str(value).strip()
        if value_str.isdigit():
            return int(value_str)
        if manager is None:
            raise ValueError("Cannot resolve %s '%s' without an API client" % (endpoint, value))
        try:
            resource_id = manager.lookup_resource_id(
                endpoint,
                "name",
                value_str,
                service=service,
                extra_query_params=extra_query_params,
                require_unique=True,
            )
        except ValueError as exc:
            raise ValueError("Could not resolve %s reference '%s': %s" % (endpoint, value, exc)) from exc
        if resource_id is None:
            raise ValueError("Could not resolve %s reference '%s'" % (endpoint, value))
        return int(resource_id)

    @staticmethod
    def _resolve_fk_name(manager, endpoint: str, fk_id) -> Optional[str]:
        """Resolve an FK integer ID back to its name for idempotent comparison.

        Args:
            manager: Platform manager instance.
            endpoint: API endpoint name (e.g. 'eda-credentials').
            fk_id: Foreign key integer ID to resolve.

        Returns:
            Optional[str]: Resolved name, or string of the ID as fallback.
        """
        if manager is None or fk_id is None:
            return str(fk_id) if fk_id is not None else None
        try:
            results = manager.search_api(
                "/api/eda/v1/%s/" % endpoint,
                query_params={"id": int(fk_id)},
            ).get("results", [])
            if results:
                return results[0].get("name", str(fk_id))
        except Exception:
            pass
        return str(fk_id)

    @classmethod
    def get_idempotency_value_from_current_data(cls, field: str, current_data: Dict[str, Any], context: TransformContext):
        """Map the Ansible representation back to API fields for update comparison."""
        manager = context.manager if isinstance(context, TransformContext) else context.get("manager")
        if field == "test_mode":
            forward_events = current_data.get("forward_events")
            return not forward_events if forward_events is not None else None
        if field == "additional_data_headers":
            return current_data.get("headers")
        if field == "organization_id":
            api_data = context.current_api_data if isinstance(context, TransformContext) else context.get("current_api_data", {})
            organization = api_data.get("organization") if api_data else None
            organization_id = organization.get("id") if isinstance(organization, dict) else None
            if organization_id is None and api_data:
                organization_id = api_data.get("organization_id")
            if organization_id is not None:
                return organization_id
            value = current_data.get("organization_name")
            return cls.resolve_reference_id(manager, "organizations", value, service="eda") if value is not None else None
        if field == "eda_credential_id":
            api_data = context.current_api_data if isinstance(context, TransformContext) else context.get("current_api_data", {})
            credential = api_data.get("eda_credential") if api_data else None
            credential_id = credential.get("id") if isinstance(credential, dict) else None
            if credential_id is None and api_data:
                credential_id = api_data.get("eda_credential_id")
            if credential_id is not None:
                return credential_id
            value = current_data.get("credential_name")
            if value is not None and str(value).strip().isdecimal():
                return int(value)
            return value
        return current_data.get(field)

    @classmethod
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        """Transform from API format to Ansible format.

        Handles the reverse field renames: test_mode -> forward_events (inverted),
        additional_data_headers -> headers. Resolves FK IDs to names for the
        Ansible result and retains the raw API fields for update comparisons.
        """
        from ....ansible_models.event_stream import AnsibleEventStream

        if isinstance(context, TransformContext):
            context.current_api_data = dict(api_data)
        else:
            context["current_api_data"] = dict(api_data)

        manager = context.manager if isinstance(context, TransformContext) else context.get("manager")

        # EDA returns these relationships as nested objects in resource
        # responses, while the write payload uses *_id fields. Prefer the
        # names already present in the response and fall back to resolving an
        # ID for API versions that return only the foreign key.
        credential = api_data.get("eda_credential")
        credential_id = api_data.get("eda_credential_id")
        if isinstance(credential, dict):
            credential_id = credential_id if credential_id is not None else credential.get("id")
        credential_name = credential.get("name") if isinstance(credential, dict) else None
        if credential_name is None:
            credential_name = cls._resolve_fk_name(manager, "eda-credentials", credential_id)

        organization = api_data.get("organization")
        organization_id = api_data.get("organization_id")
        if isinstance(organization, dict):
            organization_id = organization_id if organization_id is not None else organization.get("id")
        organization_name = organization.get("name") if isinstance(organization, dict) else None
        if organization_name is None:
            organization_name = cls._resolve_fk_name(manager, "organizations", organization_id)

        # Reverse-transform test_mode -> forward_events (inverted)
        test_mode = api_data.get("test_mode")
        forward_events = not test_mode if test_mode is not None else False

        return AnsibleEventStream(
            name=api_data.get("name", ""),
            credential_name=credential_name,
            organization_name=organization_name,
            headers=api_data.get("additional_data_headers"),
            forward_events=forward_events,
            uuid=api_data.get("uuid"),
            id=api_data.get("id"),
        )
