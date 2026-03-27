"""
API v1 CA Certificate dataclass and transform mixin.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from ...platform.base_transform import BaseTransformMixin
from ...platform.types import EndpointOperation, TransformContext

logger = logging.getLogger(__name__)


@dataclass
class APICACertificate_v1(BaseTransformMixin):
    """API v1 representation of a CA certificate."""

    name: Optional[str] = None
    pem_data: Optional[str] = None
    sha256: Optional[str] = None
    related_id_reference: Optional[str] = None

    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None


class CACertificateTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for CA Certificate API v1."""

    @classmethod
    def from_ansible_data(cls, ansible_instance, context: Union[TransformContext, Dict[str, Any]]) -> "APICACertificate_v1":
        api_data = {}
        for field in ("name", "pem_data", "sha256", "related_id_reference"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
        for field in ("id", "created", "modified", "url"):
            val = getattr(ansible_instance, field, None)
            if val is not None:
                api_data[field] = val
        return APICACertificate_v1(**api_data)

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/gateway/v1/ca_certificates/",
                method="POST",
                fields=["name", "pem_data", "sha256", "related_id_reference"],
                required_for="create",
                order=1,
            ),
            "update": EndpointOperation(
                path="/api/gateway/v1/ca_certificates/{id}/",
                method="PATCH",
                fields=["name", "pem_data", "sha256", "related_id_reference"],
                path_params=["id"],
                required_for="update",
                order=1,
            ),
            "delete": EndpointOperation(
                path="/api/gateway/v1/ca_certificates/{id}/", method="DELETE", fields=[], path_params=["id"], required_for="delete", order=1
            ),
            "get": EndpointOperation(path="/api/gateway/v1/ca_certificates/{id}/", method="GET", fields=[], path_params=["id"], required_for="find", order=1),
            "list": EndpointOperation(path="/api/gateway/v1/ca_certificates/", method="GET", fields=[], required_for="find", order=1),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return "name"

    @classmethod
    def from_api(cls, api_data: Dict[str, Any], context: Union[TransformContext, Dict[str, Any]]) -> "AnsibleCACertificate":
        from ...ansible_models.ca_certificate import AnsibleCACertificate

        return AnsibleCACertificate(
            name=api_data.get("name", ""),
            pem_data=api_data.get("pem_data"),
            sha256=api_data.get("sha256"),
            related_id_reference=api_data.get("related_id_reference"),
            id=api_data.get("id"),
            created=api_data.get("created"),
            modified=api_data.get("modified"),
            url=api_data.get("url"),
        )
