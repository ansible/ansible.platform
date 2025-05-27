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
