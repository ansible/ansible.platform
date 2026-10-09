"""
API v2 Controller Subscriptions dataclass and transform mixin.

Subscriptions uses a singleton endpoint (/api/v2/config/subscriptions/) via POST
to retrieve available subscriptions using Red Hat credentials.
The mixin declares is_singleton=True so the framework handles it correctly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext


@dataclass
class APIControllerSubscriptions_v2(BaseTransformMixin):
    """API v2 representation of controller subscriptions request."""

    subscriptions_username: Optional[str] = None
    subscriptions_password: Optional[str] = None
    subscriptions_client_id: Optional[str] = None
    subscriptions_client_secret: Optional[str] = None


class ControllerSubscriptionsTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for Controller Subscriptions API v2.

    Subscriptions is a singleton resource: POST /api/v2/config/subscriptions/
    with Red Hat credentials returns the list of available subscriptions.
    There is no list, create, or delete.
    """

    is_singleton = True

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APIControllerSubscriptions_v2:
        username = getattr(ansible_instance, "username", None)
        password = getattr(ansible_instance, "password", None)
        client_id = getattr(ansible_instance, "client_id", None)
        client_secret = getattr(ansible_instance, "client_secret", None)

        if username and password:
            return APIControllerSubscriptions_v2(
                subscriptions_username=username,
                subscriptions_password=password,
            )
        else:
            return APIControllerSubscriptions_v2(
                subscriptions_client_id=client_id,
                subscriptions_client_secret=client_secret,
            )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "get": EndpointOperation(
                path="/api/v2/config/subscriptions/",
                method="POST",
                fields=["subscriptions_username", "subscriptions_password", "subscriptions_client_id", "subscriptions_client_secret"],
                required_for="find",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        # Singleton: no lookup field needed.
        return ""

    @classmethod
    def from_api(
        cls,
        api_data: Union[List[Dict[str, Any]], Dict[str, Any]],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        from ....ansible_models.controller_subscriptions import AnsibleControllerSubscriptions

        # The API returns a list of subscription dicts
        if isinstance(api_data, list):
            return AnsibleControllerSubscriptions(subscriptions=api_data)
        return AnsibleControllerSubscriptions(subscriptions=[api_data] if api_data else [])
