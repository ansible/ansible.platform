"""Tests for Gateway user transformations."""

from ansible_collections.ansible.platform.plugins.plugin_utils.api.gateway.v1.user import UserTransformMixin_v1


def test_user_create_includes_associated_authenticators():
    operations = UserTransformMixin_v1.get_endpoint_operations()

    assert "associated_authenticators" in operations["create"].fields


def test_numeric_authenticator_name_uses_name_prefix_and_not_id():
    class Manager:
        def lookup_resource_id(self, *args, **kwargs):
            assert args == ("authenticators", "name", "123")
            assert kwargs == {"service": "gateway", "numeric_is_id": False}
            return 77

    class User:
        associated_authenticators = {"name:123": {"uid": "alice"}}
        organizations = []
        username = "alice"

    result = UserTransformMixin_v1.from_ansible_data(User(), {"manager": Manager(), "operation": "create"})

    assert result.associated_authenticators == {"77": {"uid": "alice"}}
