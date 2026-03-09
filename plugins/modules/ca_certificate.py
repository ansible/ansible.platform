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

from ..module_utils.aap_module import AAPModule
from ..module_utils.aap_ca_certificate import AAPCACertificate


def main():
    argument_spec = dict(
        name=dict(type="str", required=True),
        pem_data=dict(type="str", required=False),
        sha256=dict(type="str", required=False),
        related_id_reference=dict(type="str"),
        state=dict(choices=["present", "absent", "exists"], default="present"),
    )

    module = AAPModule(argument_spec=argument_spec, supports_check_mode=True)

    # Validate certificate data consistency for present state
    if module.params.get("state") == "present":
        pem_data = module.params.get("pem_data")
        sha256 = module.params.get("sha256")

        # If one is provided, both must be provided (for data integrity)
        if (pem_data and not sha256) or (sha256 and not pem_data):
            module.fail_json(msg="pem_data and sha256 must be provided together for certificate validation")

    AAPCACertificate(module).manage()


if __name__ == "__main__":
    main()
