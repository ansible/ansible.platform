==============================
ansible.platform Release Notes
==============================

.. contents:: Topics

v2.7.20260630
=============

Bugfixes
--------

- application - fix ``client_secret`` not returned in module result when creating a confidential OAuth application (https://issues.redhat.com/browse/AAP-80136).

v2.7.20260615
=============

Bugfixes
--------

- gateway_api lookup / search_api - Fix pagination for relative next URLs. AAP returns the next link as a relative path; it is now resolved against base_url with urljoin so absolute URLs are always requested.
- gateway_api lookup / search_api - Support Galaxy/Hub pagination envelope. Hub list responses use {meta, links, data} instead of the DRF {count, next, results} shape. return_all now handles both envelopes so /api/galaxy/ endpoints no longer silently return only the first page (backport of

v2.7.20260604
=============

Bugfixes
--------

- All modules - Fix aap_validate_certs alias resolution. When aap_validate_certs false was set via module_defaults or group/ansible.platform.gateway, it was silently ignored due to incorrect or-chaining in the config extractor. The parameter is now resolved using an explicit in-key check so that False is honoured correctly (AAP-75645).
- All modules - Fix empty-string handling for aap_request_timeout and gateway_request_timeout. The AAP built-in credential type injects aap_request_timeout as {{request_timeout}} which evaluates to empty string when not configured. Empty string caused argspec validation to fail with cannot be converted to float. Empty strings are now stripped before validation and the 10-second default is applied instead.
- All modules - Restore async/poll 0 parallelism for all ansible.platform action plugins. BaseResourceActionPlugin now sets _supports_async = True. All tasks always target localhost so Ansible's fork-based async mechanism works correctly, restoring the parallel execution that infra.aap_configuration gateway roles depend on and that was broken in the action plugin rewrite (AAP-76233).

v2.7.20260515
=============

Bugfixes
--------

- All modules - Fix task-level environment vars (e.g. SSL_CERT_FILE, REQUESTS_CA_BUNDLE, proxy settings) not being forwarded to the manager subprocess when using connection ansible.platform.http in direct or persistent mode. Previously forwarding only worked for connection local.
- All modules - Map SSL_CERT_FILE to REQUESTS_CA_BUNDLE automatically in the manager subprocess environment. The manager uses the requests library which reads REQUESTS_CA_BUNDLE not SSL_CERT_FILE; without this shim the containerized AAP installer SSL environment was silently ignored. SSL_CERT_FILE support is deprecated and will be removed in a future release.

v2.7.20260513
=============

Minor Changes
-------------

- Introduce new action plugin architecture with persistent manager process, RPC-based client, and versioned data model transformation layer. All modules now route through BaseResourceActionPlugin for consistent CRUD dispatch and idempotency handling.

Bugfixes
--------

- Strip scheme and hostname from AAP url builder, which previously lead to malformed urls in the ansible.platform.gateway_api lookup plugin (ACA-5393).
- application - Fix broken idempotency for redirect_uris and organization fields caused by list vs string and name vs integer FK type mismatches (AAP-73293).
- role_team_assignment - Fix deletion bug where assignments were not correctly removed when state absent was specified (AAP-73742).
- role_user_assignment - Raise a clear error when the specified role_definition or user does not exist on the Gateway rather than silently swallowing the failure (AAP-73741).
- role_user_assignment, role_team_assignment - Fix state exists returning a missing key error when no matching assignment was found (AAP-73294)

v1.0.0
======

