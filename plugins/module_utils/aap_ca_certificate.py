# coding: utf-8 -*-
# Copyright: (c) 2025, Hui Song <hsong@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ..module_utils.aap_object import AAPObject


class AAPCACertificate(AAPObject):
    endpoint = 'ca_certificates'
    module_name = 'ca_certificate'

    def __init__(self, module):
        super(AAPCACertificate, self).__init__(module)

    def create(self):
        data = {
            'name': self.module.params['name'],
            'pem_data': self.module.params['pem_data'],
            'remote_id': self.module.params.get('remote_id'),
            'sha256': self.module.params.get('sha256')
        }
        return self._create(data)

    def update(self, existing):
        data = {
            'name': self.module.params['name'],
            'pem_data': self.module.params['pem_data'],
            'remote_id': self.module.params.get('remote_id'),
            'sha256': self.module.params.get('sha256')
        }
        return self._update(existing, data)

    def delete(self, existing):
        return self._delete(existing)

    def get(self):
        return self._get()