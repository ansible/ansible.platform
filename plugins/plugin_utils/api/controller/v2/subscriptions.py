"""
API v2 Subscriptions dataclass and transform mixin.

Subscriptions uses a POST to /api/controller/v2/config/subscriptions/
with Red Hat credentials to retrieve available subscriptions.
This is a non-CRUD resource; the only meaningful operation is 'create'
which POSTs credentials and returns a list of subscriptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from ....platform.base_transform import BaseTransformMixin
from ....platform.types import EndpointOperation, TransformContext


@dataclass
class APISubscriptions_v2(BaseTransformMixin):
    """API v2 representation of subscription lookup request."""

    subscriptions_username: Optional[str] = None
    subscriptions_password: Optional[str] = None
    subscriptions_client_id: Optional[str] = None
    subscriptions_client_secret: Optional[str] = None


class SubscriptionsTransformMixin_v2(BaseTransformMixin):
    """Transform mixin for Subscriptions API v2.

    Subscriptions is a non-CRUD resource: POST credentials to
    /api/controller/v2/config/subscriptions/ and receive a list
    of available subscriptions.
    """

    @classmethod
    def from_ansible_data(
        cls,
        ansible_instance,
        context: Union[TransformContext, Dict[str, Any]],
    ) -> APISubscriptions_v2:
        """Transform Ansible credentials to API POST body format.

        The controller API expects field names with 'subscriptions_' prefix.
        """
        username = getattr(ansible_instance, "username", None)
        password = getattr(ansible_instance, "password", None)
        client_id = getattr(ansible_instance, "client_id", None)
        client_secret = getattr(ansible_instance, "client_secret", None)

        if username and password:
            return APISubscriptions_v2(
                subscriptions_username=username,
                subscriptions_password=password,
            )
        return APISubscriptions_v2(
            subscriptions_client_id=client_id,
            subscriptions_client_secret=client_secret,
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            "create": EndpointOperation(
                path="/api/controller/v2/config/subscriptions/",
                method="POST",
                fields=[
                    "subscriptions_username",
                    "subscriptions_password",
                    "subscriptions_client_id",
                    "subscriptions_client_secret",
                ],
                required_for="create",
                order=1,
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return ""

    @classmethod
    def from_api(
        cls,
        api_data: Union[List[Dict[str, Any]], Dict[str, Any]],
        context: Union[TransformContext, Dict[str, Any]],
    ):
        """Convert API response (a JSON list of subscriptions) to Ansible model."""
        from ....ansible_models.subscriptions import AnsibleSubscriptions

        # The API returns a bare JSON list of subscription dicts
        if isinstance(api_data, list):
            return AnsibleSubscriptions(subscriptions=api_data)
        # Fallback: if it's a dict with a 'results' key (paginated)
        if isinstance(api_data, dict) and "results" in api_data:
            return AnsibleSubscriptions(subscriptions=api_data["results"])
        return AnsibleSubscriptions(subscriptions=[])
