=========================================
ansible.platform Release Notes
=========================================

.. contents:: Topics


v2.7.20260313
=============
Added OIDC User Identity support for Ansible Automation Platform Gateway, enabling OpenID Connect integration for user authentication and authorization.

New modules:
* feature_flag - Manage feature flags in Automation Platform Gateway
* ca_certificates - Manage CA certificates for mTLS
* role_team_assignment - Add role team assignment module (AAP-50089)
* role_definition - Add role definition module (AAP-50274)

Additional changes:
* Add request_timeout_seconds and idle_timeout_seconds attributes to route modules (AAP-66486)
* Add enable_mtls attribute to route module for mutual TLS support (AAP-48345)
* Add associated_authenticators parameter to users module (AAP-48878)
* Add Gateway UI plugin Route Collection Module (AAP-44404)
* Add object_ids parameter support for processing lists of object_ids/names (AAP-43078)
* Add Organization Association Logic to user Module (AAP-41665)
* Add option to create Auditor users in user module (AAP-43080)
* Enhance documentation for gateway_api.py lookup plugin (AAP-64338)
* Fix for custom role team assignment (AAP-57909)
* Fix multiple assignment object deletion (AAP-52248)
* Fix to honor check_mode flag (AAP-40779)
* Fix idempotent cases in create_if_needed() when auto_exit is disabled (AAP-44752)
* Strip scheme and hostname from AAP url builder parameters to prevent malformed URLs (AAP-47990)
* Standardize host validation across modules
* Fix Envoy configuration for checking health of service cluster nodes (AAP-37005)
* Update get_aap_gateway_and_dab.py with updated repo url for ansible-gateway (AAP-49513)

Deprecations:
* Deprecate authenticator_uid and authenticators fields in favor of associated_authenticators

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
