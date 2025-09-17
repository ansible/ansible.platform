==============================
ansible.platform Release Notes
==============================

.. contents:: Topics

v2.6.20250924
=============
The ansible.platform collection now provides unified, platform-wide Role-Based Access Control (RBAC) management across Ansible Automation Platform components. New or enhanced modules include Organization, Team, User, Role definition, and Role assignment (team/user).

Additional changes:

* You can declare the RBAC state as code and apply it idempotently across services.
* Ansible collections now use a standard global environment variable prefix across components. Automation Controller, Automation Hub, and Event-Driven Ansible all use the new standard ``AAP_`` instead of ``COMPONENT_``. For example, ``aap_hostname``. See the Automation Hub documentation for more information.