==============================
ansible.platform Release Notes
==============================

.. contents:: Topics

v2.6.20260930
=============

Minor Changes
-------------

- service_cluster - add ``outlier_detection_split_external_local_origin_errors`` and ``outlier_detection_consecutive_local_origin_failure`` options (https://issues.redhat.com/browse/AAP-76998).

Breaking Changes / Porting Guide
--------------------------------

- role_user_assignment - removed deprecated parameter ``object_id`` (singular). It was deprecated in favour of ``object_ids`` (plural list). Replace any use of ``object_id: <n>`` with ``object_ids: ["<n>"]``.
- user - removed deprecated parameters ``organizations``, ``is_platform_auditor``, ``authenticators``, and ``authenticator_uid`` (and its alias ``auditor``). These were deprecated in 2.6.20251106 with removal date 2026-01-31. Use ``ansible.platform.role_user_assignment`` to assign organization membership or platform auditor roles, and ``associated_authenticators`` to configure authenticator associations.

Bugfixes
--------

- authenticator_user - map the API ``provider`` field to ``authenticator`` so repeated moves are idempotent (https://issues.redhat.com/browse/AAP-38532).
- gateway_api lookup - automatically read exported ``GATEWAY_HOSTNAME``, ``GATEWAY_USERNAME``, ``GATEWAY_PASSWORD``, ``GATEWAY_VERIFY_SSL``, ``GATEWAY_API_TOKEN``, and ``GATEWAY_REQUEST_TIMEOUT`` values, with the supported ``AAP_*`` aliases as fallback. Explicit lookup options take precedence.
- role_team_assignment - allow resource-level ``type`` values (for example ``projects``, ``activations``) in ``assignment_objects`` instead of rejecting all types other than ``organizations`` and ``teams``.
- role_team_assignment - validate ``assignment_objects`` ``type`` against the role definition ``content_type`` before API calls, preventing Gateway 400/500 errors when the wrong resource type is used for name-based lookup (https://issues.redhat.com/browse/AAP-75240).

v2.6.20260504
=============

v2.6.20260306
=============

v2.6.20251106
=============

v2.6.20250924
=============

v1.0.0
======

