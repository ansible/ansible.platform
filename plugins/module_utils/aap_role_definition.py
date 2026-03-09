from ..module_utils.aap_object import AAPObject  # noqa

__metaclass__ = type


class AAPRoleDefinition(AAPObject):
    API_ENDPOINT_NAME = "role_definitions"
    ITEM_TYPE = "role_definition"

    def unique_field(self):
        return self.module.IDENTITY_FIELDS["role_definitions"]

    def set_new_fields(self):
        # Name
        name = self.module.params.get("name")
        if name is not None:
            self.new_fields["name"] = self.module.get_item_name(self.data) if self.data else name

        # New name (for renaming)
        new_name = self.module.params.get("new_name")
        if new_name is not None:
            self.new_fields["name"] = new_name

        # Description
        description = self.module.params.get("description")
        if description is not None:
            self.new_fields["description"] = description

        # Content Type
        content_type = self.module.params.get("content_type")
        if content_type is not None:
            self.new_fields["content_type"] = content_type

        # Permissions
        permissions = self.module.params.get("permissions")
        if permissions is not None:
            self.new_fields["permissions"] = permissions
