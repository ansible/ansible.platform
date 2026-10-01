# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.ansible.platform.plugins.module_utils.aap_service_key import AAPServiceKey


class FakeModule:
    IDENTITY_FIELDS = {
        'service_keys': 'name',
    }

    def __init__(self, params, existing=None):
        self.params = params
        self.existing = existing
        self.json_output = {'changed': False}
        self.create_or_update_call = None
        self.deprecations = []

    def get_one(self, endpoint, name_or_id=None):
        self.get_one_call = {
            'endpoint': endpoint,
            'name_or_id': name_or_id,
        }
        return self.existing

    def create_or_update_if_needed(self, data, new_fields, endpoint=None, item_type=None, auto_exit=True):
        self.create_or_update_call = {
            'data': data,
            'new_fields': dict(new_fields),
            'endpoint': endpoint,
            'item_type': item_type,
            'auto_exit': auto_exit,
        }
        result = {'id': 1}
        result.update(new_fields)
        return result

    def deprecate(self, msg=None, version=None, collection_name=None):
        self.deprecations.append(
            {
                'msg': msg,
                'version': version,
                'collection_name': collection_name,
            }
        )


def test_missing_service_key_create_attempt_uses_only_editable_fields():
    module = FakeModule(
        {
            'name': 'missing-key',
            'is_active': True,
            'service_cluster': 'gateway',
            'secret': 'secret-value',
            'secret_length': 32,
            'mark_previous_inactive': True,
            'algorithm': 'HS256',
            'state': 'present',
        }
    )

    AAPServiceKey(module).manage(auto_exit=False)

    assert module.create_or_update_call['data'] is None
    assert module.create_or_update_call['new_fields'] == {
        'name': 'missing-key',
        'is_active': True,
    }
    assert len(module.deprecations) == 5


def test_existing_service_key_update_ignores_deprecated_creation_fields():
    module = FakeModule(
        {
            'name': 'existing-key',
            'new_name': 'renamed-key',
            'is_active': False,
            'service_cluster': 'gateway',
            'state': 'present',
        },
        existing={'id': 42, 'name': 'existing-key', 'is_active': True},
    )

    AAPServiceKey(module).manage(auto_exit=False)

    assert module.create_or_update_call['data']['id'] == 42
    assert module.create_or_update_call['new_fields'] == {
        'name': 'renamed-key',
        'is_active': False,
    }
    assert module.deprecations == [
        {
            'msg': "The 'service_cluster' parameter is deprecated because Gateway no longer permits creating service keys through its API.",
            'version': '4.0.0',
            'collection_name': 'ansible.platform',
        }
    ]
