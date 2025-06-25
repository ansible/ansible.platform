# coding: utf-8 -*-
# Copyright: (c) 2025, Hui Song <hsong@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = '''
---
module: ca_certificate
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
        required: true
        type: str
    remote_id:
        description:
            - The remote identifier for the certificate.
        type: str
    sha256:
        description:
            - The SHA256 fingerprint of the certificate.
        type: str
    state:
        description:
            - Whether the certificate should exist or not.
        choices: [ 'present', 'absent' ]
        default: 'present'
        type: str

extends_documentation_fragment:
    - ansible.platform.state
    - ansible.platform.auth
'''

EXAMPLES = '''
- name: Add a CA Certificate
  ansible.platform.ca_certificate:
    name: "My CA Certificate"
    pem_data: "{{ lookup('file', 'ca_cert.pem') }}"
    state: present

- name: Remove a CA Certificate
  ansible.platform.ca_certificate:
    name: "My CA Certificate"
    state: absent
...
'''

RETURN = '''
id:
    description: The ID of the CA Certificate
    returned: success
    type: str
    sample: "42"
'''

from ..module_utils.aap_module import AAPModule
from ..module_utils.aap_ca_certificate import AAPCACertificate


def main():
    argument_spec = dict(
        name=dict(type='str', required=True),
        pem_data=dict(type='str', required=True),
        remote_id=dict(type='str'),
        sha256=dict(type='str'),
        state=dict(choices=['present', 'absent'], default='present'),
    )

    module = AAPModule(argument_spec=argument_spec, supports_check_mode=True)

    AAPCACertificate(module).manage()


if __name__ == '__main__':
    main()