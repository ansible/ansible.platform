from ..module_utils.aap_object import AAPObject

__metaclass__ = type


class AAPServiceKey(AAPObject):
    API_ENDPOINT_NAME = "service_keys"
    ITEM_TYPE = "service_key"
    DEPRECATED_CREATION_FIELDS = {
        'service_cluster': "The 'service_cluster' parameter is deprecated because Gateway no longer permits creating service keys through its API.",
        'secret': "The 'secret' parameter is deprecated because Gateway no longer permits creating service keys through its API.",
        'secret_length': "The 'secret_length' parameter is deprecated because Gateway no longer permits creating service keys through its API.",
        'mark_previous_inactive': (
            "The 'mark_previous_inactive' parameter is deprecated because Gateway no longer permits creating service keys through its API."
        ),
        'algorithm': "The 'algorithm' parameter is deprecated because Gateway no longer permits creating service keys through its API.",
    }

    def __init__(self, module, params=None, **kwargs):
        super().__init__(module, params, **kwargs)

    def manage(self, **kwargs):
        if self.present() or self.enforced():
            self.warn_deprecated_creation_fields()
        super().manage(**kwargs)

    def warn_deprecated_creation_fields(self):
        for field, message in self.DEPRECATED_CREATION_FIELDS.items():
            if self.params.get(field) is not None:
                self.module.deprecate(msg=message, version='4.0.0', collection_name='ansible.platform')

    def unique_field(self):
        return self.module.IDENTITY_FIELDS['service_keys']

    def set_new_fields(self):
        # Create the data that gets sent for create and update
        self.set_name_field()

        is_active = self.params.get('is_active')
        if is_active is not None:
            self.new_fields['is_active'] = is_active
