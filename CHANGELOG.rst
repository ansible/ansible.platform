==============================
ansible.platform Release Notes
==============================

.. contents:: Topics

v2.7.20260515
=============

Bugfixes
--------

- All modules - Fix task-level ``environment:`` variables (e.g. ``SSL_CERT_FILE``,
  ``REQUESTS_CA_BUNDLE``, proxy settings) not being forwarded to the manager
  subprocess when using ``connection: ansible.platform.http`` in direct or
  persistent mode. Previously forwarding only worked for ``connection: local``.
- All modules - Map ``SSL_CERT_FILE`` - ``REQUESTS_CA_BUNDLE`` automatically in
  the manager subprocess environment. The manager uses the ``requests`` library
  which reads ``REQUESTS_CA_BUNDLE``, not ``SSL_CERT_FILE``; without this shim
  the containerized AAP installer's SSL environment was silently ignored.
  ``SSL_CERT_FILE`` support is deprecated and will be removed in a future release.

v2.7.20260513
=============

Minor Changes
-------------

- Introduce new action plugin architecture with persistent manager process,
  RPC-based client, and versioned data model transformation layer
  (``AnsibleModel`` - ``APIModel_v1``). All modules now route through
  ``BaseResourceActionPlugin`` for consistent CRUD dispatch and idempotency
  handling (AAP-73294).

Bugfixes
--------

- ``application`` - Fix broken idempotency for ``redirect_uris`` and
  ``organization`` fields; ``redirect_uris`` was compared as a list against
  the API's space-separated string representation and ``organization`` was
  compared as a name against the API's integer FK, always causing false drift
  detection (AAP-73293).
- ``role_team_assignment`` - Fix deletion bug where assignments were not
  correctly removed when ``state: absent`` was specified (AAP-73742).
- ``role_user_assignment`` - Raise a clear error when the specified
  ``role_definition`` or ``user`` does not exist on the Gateway, rather than
  silently returning a modified result dict that bypassed Ansible task failure
  handling (AAP-73741).
- ``role_user_assignment``, ``role_team_assignment`` - Fix ``state: exists``
  returning a missing key error when no matching assignment was found
  (AAP-73294).
- ``service_key`` - Fix false idempotency failures caused by the API
  returning ``$encrypted$`` for ``secret`` on GET responses; ``secret`` and
  ``secret_length`` are now treated as write-only fields and excluded from
  state comparison (AAP-73743)

- Strip scheme and hostname from AAP url builder, which previously lead to malformed urls in the ansible.platform.gateway_api lookup plugin

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

v1.0.0
======

