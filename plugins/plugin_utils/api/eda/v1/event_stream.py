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

        # --- credential_name -> eda_credential_id ---
        credential_name = getattr(ansible_instance, "credential_name", None)
        if credential_name is not None:
            credential_str = str(credential_name).strip()
            if credential_str.isdigit():
                api_data["eda_credential_id"] = int(credential_str)
            else:
                if mgr is not None:
                    try:
                        api_data["eda_credential_id"] = mgr.lookup_resource_id("eda-credentials", "name", credential_str, service="eda")
                    except Exception:
                        pass
                if "eda_credential_id" not in api_data:
                    api_data["eda_credential_id"] = credential_name

        # --- organization_name -> organization_id ---
        organization_name = getattr(ansible_instance, "organization_name", None)
        if organization_name is not None:
            org_str = str(organization_name).strip()
            if org_str.isdigit():
                api_data["organization_id"] = int(org_str)
            else:
                if mgr is not None:
                    try:
                        api_data["organization_id"] = mgr.lookup_resource_id("organizations", "name", org_str)
                    except Exception:
                        pass
                if "organization_id" not in api_data:
                    api_data["organization_id"] = organization_name

        # --- forward_events (bool) -> test_mode (inverted bool) ---
        forward_events = getattr(ansible_instance, "forward_events", None)
        if forward_events is not None:
            api_data["test_mode"] = not forward_events

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
        """Return query parameters for finding an existing event stream."""
        name = getattr(ansible_data, "name", None)
        if name is not None:
            return {"name": name}
        return {}

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
    def from_api(
        cls,
        api_data: Dict[str, Any],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        """Transform from API format to Ansible format.

        Handles the reverse field renames: test_mode -> forward_events (inverted),
        additional_data_headers -> headers.  Resolves FK integer IDs back to
        names for idempotent comparison.
        """
        from ....ansible_models.event_stream import AnsibleEventStream

        manager = context.manager if isinstance(context, TransformContext) else context.get("manager")

        # Resolve eda_credential_id -> credential_name
        credential_name = cls._resolve_fk_name(manager, "eda-credentials", api_data.get("eda_credential_id"))

        # Resolve organization_id -> organization_name
        organization_id = api_data.get("organization_id")
        organization_name = str(organization_id) if organization_id is not None else None
        if manager and organization_id is not None:
            try:
                names = manager.lookup_organization_names([organization_id])
                if names:
                    organization_name = names[0]
            except Exception:
                pass

        # Reverse-transform test_mode -> forward_events (inverted)
        forward_events = None
        test_mode = api_data.get("test_mode")
        if test_mode is not None:
            forward_events = not test_mode

        return AnsibleEventStream(
            name=api_data.get("name", ""),
            credential_name=credential_name,
            organization_name=organization_name,
            headers=api_data.get("additional_data_headers"),
            forward_events=forward_events,
            uuid=api_data.get("uuid"),
            id=api_data.get("id"),
        )
