=========================================
ansible.platform Release Notes
=========================================

.. contents:: Topics


v2.5.0
======
Initial Release

v2.5.1
======
No Change

v2.5.2
======
No Change

v2.5.3
======
Added authenticator_user module

v2.5.20241218
======
Removed the default `map_type` of `team` from `authenticator_map` module.
Removed the `required_if` condition from `authenticator_map` module.
Added the `secret` field to the output of `secret_key` module.
Fixed the parameter `authenticator_uid` on the `user` module.
Fixed a broken doc fragment in the `authenticator_user` module.

v2.5.20250212
======
Added application and organization lookup for tokens.

v2.5.20250312
======
Bug fix in AAP module that could cause a stack trace when using "present"

v2.5.20250326
======
Added support for setting URL for applications

v2.5.20250507
======
Added `lightspeed` as a valid `service_type` choice for the `service_cluster` module

v2.5.20250528
======
Support for dynamic `service_type` added.
Internal route supported added (`service_cluster`) (development use only).
Control plane authentication configurability added (`service_cluster`) (development use only).

v2.5.20250604
======
Add `healthy_panic_threshold` parameter to the `ansible.platform.service_cluster` module

v2.5.20250702
======
* Ensures that modules in the ansible.platform collection accepts `AAP_*` variable for authentication.
* Adds missing option in the ansible.platform.user module to allow setting the `is_platform_auditor` flag on a user.
* Allows running `ansible.platform` collection modules in check mode.
* Fixes `ansible.platform.user` not adding users to organizations.
* Specify correct `aap_*` parameters in `ansible.platform.token` module examples.
* Fixes an example task in `ansible.platform.token` module.
* Adds a new section in the collection README describing how to authenticate to AAP from the playbook.
* Allows `object_id` field in `role_user_assignment` module to accept a list of items.
* Updated documentation examples for the `ansible.platform.settings` module with tested tasks examples.
* Improve documentation and examples for `ansible.platform.authenticator` and `ansible.platform.authenticator_map` modules.
* Allows role assignments using `object_ansible_id` in the `role_user_assignment` module.
* Improve documentation and examples related to `object_id` and `object_ansible_id` parameters in `role_user_assignment` module.
