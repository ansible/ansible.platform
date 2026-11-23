#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# This module is implemented as an action plugin.
# See plugins/action/import.py for the implementation.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: import
author: Red Hat (@RedHatOfficial)
short_description: Import resources into Ansible Automation Platform.
description:
  - Import Controller and Gateway resources from a structured asset dict.
  - Accepts the native ansible.platform format (module-parameter dicts keyed
    by resource type) or legacy awxkit export format when
    C(auto_convert_legacy) is enabled.
  - Resources are created or updated in dependency order so that foreign key
    references (e.g. organization, credential_type, project) resolve correctly.
  - Each resource is imported idempotently using the corresponding
    C(ansible.platform) module. Running the import twice with the same data
    produces C(changed=false) on the second run.
  - This module never deletes resources. Only resources present in the asset
    dict are created or updated.
version_added: "2.7.0"

options:
  assets:
    description:
      - The assets to import.
      - Top-level keys are resource type names (e.g. C(organizations),
        C(credentials), C(job_templates)). Values are lists of dicts whose
        keys match the corresponding C(ansible.platform) module parameters.
      - Can be the output of C(awx export) or the legacy C(awx.awx.export)
        module when C(auto_convert_legacy=true).
    required: true
    type: dict
  auto_convert_legacy:
    description:
      - When C(true), automatically convert legacy awxkit natural-key format
        to the native ansible.platform format before importing.
      - Enable this when importing data produced by C(awx export) CLI or
        the C(awx.awx.export) module.
    type: bool
    default: false

seealso:
  - module: awx.awx.import
  - module: ansible.controller.import

extends_documentation_fragment:
  - ansible.platform.auth
...
"""

EXAMPLES = """
- name: Import assets from a file (native format)
  ansible.platform.import:
    assets: "{{ lookup('file', 'platform_export.json') | from_json }}"

- name: Import from a legacy awxkit export with auto-conversion
  ansible.platform.import:
    assets: "{{ lookup('file', 'awxkit_export.json') | from_json }}"
    auto_convert_legacy: true

- name: Import assets from a previous export task
  ansible.platform.import:
    assets: "{{ export_output.assets | ansible.platform.from_awxkit_export }}"

- name: Import only organizations and teams (native format)
  ansible.platform.import:
    assets:
      organizations:
        - name: Engineering
          description: "Engineering department"
      teams:
        - name: Backend
          organization: Engineering
...
"""

RETURN = """
changed:
    description: Whether any resources were created or updated.
    returned: success
    type: bool
results:
    description: Per-resource-type import results with counts.
    returned: success
    type: dict
    sample:
      organizations: {"changed": 1, "ok": 0, "failed": 0}
      credentials: {"changed": 2, "ok": 1, "failed": 0}
failed_resources:
    description: List of resources that failed to import.
    returned: when failures occur
    type: list
    elements: dict
...
"""
