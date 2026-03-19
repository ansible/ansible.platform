#!/usr/bin/python
# coding: utf-8 -*-

# Copyright: (c) 2025, Hui Song <@hsong>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: ca_certificate
author: Hui Song (@hsong)
short_description: Manage CA Certificates
version_added: "1.0.0"
description:
    - This module allows for the management of CA Certificates in the gateway.
options:
    name:
        description:
            - The name of the CA Certificate.
        required: true
        type: str
    pem_data:
        description:
            - The PEM encoded certificate data.
            - Required when creating a new certificate or updating certificate data.
            - If provided, sha256 must also be provided for validation.
        required: false
        type: str
    sha256:
        description:
            - The SHA256 fingerprint of the certificate.
            - Required when creating a new certificate or updating certificate data.
            - If provided, pem_data must also be provided for validation.
        required: false
        type: str
    related_id_reference:
        description:
            - Used to track the related EDA credential.
        type: str
    state:
        description:
            - Whether the certificate should exist or not.
        choices: [ 'present', 'absent', 'exists' ]
        default: 'present'
        type: str

extends_documentation_fragment:
    - ansible.platform.state
    - ansible.platform.auth
"""

EXAMPLES = """
- name: Add a CA Certificate
  ansible.platform.ca_certificate:
    name: "My CA Certificate"
    pem_data: "{{ lookup('file', 'ca_cert.pem') }}"
    sha256: "a1b2c3d4e5f6789012345678901234567890123456789012345678901234567890"
    state: present

- name: Add a CA Certificate with EDA credential tracking
  ansible.platform.ca_certificate:
    name: "EDA CA Certificate"
    pem_data: "{{ lookup('file', 'eda_ca_cert.pem') }}"
    sha256: "b2c3d4e5f6789012345678901234567890123456789012345678901234567890a1"
    related_id_reference: "12345678-1234-1234-1234-123456789012"
    state: present

- name: Remove a CA Certificate
  ansible.platform.ca_certificate:
    name: "My CA Certificate"
    state: absent
...
"""

RETURN = """
id:
    description: The ID of the CA Certificate
    returned: success
    type: str
    sample: "42"
"""

# This module is doc-only; the action plugin runs all logic via the manager.
