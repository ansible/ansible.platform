from ..module_utils.aap_object import AAPObject  # noqa

__metaclass__ = type


class AAPFeatureFlag(AAPObject):
    API_ENDPOINT_NAME = "feature_flags"
    ITEM_TYPE = "feature_flag"

    def unique_field(self):
        return 'name'

    def set_new_fields(self):
        # Create the data that gets sent for update
        # Feature flags can only be updated, not created or deleted

        value = self.params.get('value')
        if value is not None:
            self.new_fields['value'] = value

    def manage(self, auto_exit=True, fail_when_not_exists=True, **kwargs):
        """
        Override the manage method for feature flags since they have special behavior:
        - Feature flags cannot be created or deleted via the API
        - Only runtime feature flags can be updated
        - Updates are done via PATCH, not PUT
        """
        self.get_existing_item()

        # Feature flag must exist - they cannot be created
        if self.data is None:
            self.module.fail_json(msg=f"Feature flag '{self.unique_value()}' does not exist. Feature flags cannot be created via the API.")

        # Store the flag data in the output
        self.module.json_output.update(self.data)

        # If just checking existence, return the current state
        if self.exists():
            if auto_exit:
                self.module.exit_json(**self.module.json_output)
            return

        # Feature flags cannot be deleted
        if self.absent():
            self.module.fail_json(msg="Feature flags cannot be deleted via the API.")

        # Update the feature flag if present or enforced
        if self.present() or self.enforced():
            self.set_new_fields()

            # Check if this is a runtime feature flag
            if self.data.get('toggle_type') != 'run-time':
                self.module.fail_json(msg=f"Feature flag '{self.data['name']}' is an install-time flag and cannot be modified at runtime.")

            # Check if runtime feature flags are enabled
            runtime_enabled = self._check_runtime_feature_flags_enabled()
            if not runtime_enabled:
                self.module.fail_json(msg="Runtime feature flag updates are disabled. RUNTIME_FEATURE_FLAGS must be set to 'True' in settings.")

            # Validate the value for boolean conditions
            if self.data.get('condition') == 'boolean':
                value = self.new_fields.get('value')
                if value is not None and value.lower() not in ['true', 'false']:
                    self.module.fail_json(msg="Feature flag with boolean condition requires 'True' or 'False' value.")

            # Check if update is needed
            current_value = str(self.data.get('value', ''))
            new_value = str(self.new_fields.get('value', ''))

            if current_value != new_value:
                if not self.module.check_mode:
                    # Perform the update via PATCH
                    url = self.module.build_url(f"{self.api_endpoint}/{self.data['id']}/")
                    response = self.module.make_request('PATCH', url, data=self.new_fields)

                    if response.get('status_code') not in [200, 204]:
                        self.module.fail_json(msg=f"Failed to update feature flag: {response}")

                    # Refresh the data
                    self.data = self.module.get_one(self.api_endpoint, name_or_id=self.unique_value())
                    self.module.json_output.update(self.data)

                self.module.json_output['changed'] = True
            else:
                self.module.json_output['changed'] = False

            if auto_exit:
                self.module.exit_json(**self.module.json_output)

    def _check_runtime_feature_flags_enabled(self):
        """
        Check if runtime feature flags are enabled by querying the settings endpoint.
        """
        try:
            # Try to get the RUNTIME_FEATURE_FLAGS setting
            settings_url = self.module.build_url('settings/')
            response = self.module.make_request('GET', settings_url)

            if response.get('status_code') == 200 and 'results' in response:
                for setting in response['results']:
                    if setting.get('key') == 'RUNTIME_FEATURE_FLAGS':
                        return setting.get('value', '').lower() == 'true'

            # Default to False if setting not found or error occurred
            return False
        except Exception:
            # If we can't check the setting, assume it's disabled for safety
            return False
