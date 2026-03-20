#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""
Action plugin for ansible.platform.ca_certificate module.

Uses the persistent connection manager architecture.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import hashlib
import logging
import time
from dataclasses import asdict
from datetime import datetime, timezone

from ansible.errors import AnsibleError
from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.ca_certificate import AnsibleCACertificate

logger = logging.getLogger(__name__)

try:
    from cryptography import x509
    from cryptography.exceptions import UnsupportedAlgorithm
    _HAS_CRYPTOGRAPHY = True
except ImportError:
    _HAS_CRYPTOGRAPHY = False


def _validate_ca_certificate_data(pem_data, sha256):
    """Validate PEM data and SHA256 when both are provided. Raises AnsibleError on failure."""
    if not _HAS_CRYPTOGRAPHY:
        raise AnsibleError(
            "The cryptography library is required for CA certificate validation. "
            "Install it with: pip install cryptography"
        )
    try:
        certificates = x509.load_pem_x509_certificates(pem_data.encode("utf-8"))
    except (ValueError, UnsupportedAlgorithm) as e:
        raise AnsibleError("Invalid PEM certificate data: %s" % e)
    if not certificates:
        raise AnsibleError("No valid certificates found in PEM data")
    now = datetime.now(timezone.utc)
    for certificate in certificates:
        if now > certificate.not_valid_after_utc:
            raise AnsibleError("Certificate has expired: %s" % certificate.not_valid_after_utc)
    if sha256:
        normalized_pem = pem_data.strip().replace("\r\n", "\n").replace("\r", "\n")
        calculated = hashlib.sha256(normalized_pem.encode("utf-8")).hexdigest()
        if calculated != sha256:
            raise AnsibleError("SHA256 mismatch. Expected: %s, Calculated: %s" % (sha256, calculated))


class ActionModule(BaseResourceActionPlugin):
    """Action plugin for ca_certificate; uses manager."""

    MODULE_NAME = 'ca_certificate'

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = dict()
        self._task_vars = task_vars
        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp
        action_start = time.perf_counter()
        auth_params = [
            'gateway_hostname', 'gateway_username', 'gateway_password',
            'gateway_token', 'gateway_validate_certs', 'gateway_request_timeout',
            'aap_hostname', 'aap_username', 'aap_password', 'aap_token',
            'aap_validate_certs', 'aap_request_timeout'
        ]
        try:
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                raise AnsibleError("Could not load DOCUMENTATION for ca_certificate module")
            module_args = self._task.args.copy()
            validated_input = self._validate_data(module_args, argspec, 'input')
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager
            if facts_to_set:
                result['ansible_facts'] = facts_to_set
                result['_ansible_facts_cacheable'] = True
            validated_params = validated_input.validated_parameters
            if validated_params.get('state') == 'present':
                pem_data = validated_params.get('pem_data')
                sha256_val = validated_params.get('sha256')
                if (pem_data and not sha256_val) or (sha256_val and not pem_data):
                    raise AnsibleError("pem_data and sha256 must be provided together for certificate validation")
                if pem_data and sha256_val:
                    _validate_ca_certificate_data(pem_data, sha256_val)
            cert_data = {
                k: v for k, v in validated_params.items()
                if v is not None and k not in auth_params
            }
            cert = AnsibleCACertificate(**cert_data)
            operation = self._detect_operation(validated_params)
            if operation == 'create' and validated_params.get('state') == 'present':
                try:
                    find_result = manager.execute(
                        operation='find',
                        module_name=self.MODULE_NAME,
                        ansible_data={'name': cert.name}
                    )
                    if find_result and find_result.get('id'):
                        operation = 'update'
                        cert.id = find_result.get('id')
                except Exception:
                    pass
            if operation == 'delete' and not cert.id:
                try:
                    find_result = manager.execute(
                        operation='find',
                        module_name=self.MODULE_NAME,
                        ansible_data={'name': cert.name}
                    )
                    if find_result and find_result.get('id'):
                        cert.id = find_result.get('id')
                    else:
                        result.update({
                            'changed': False, 'failed': False,
                            self.MODULE_NAME: {'state': 'absent'},
                            'msg': "CA certificate '%s' does not exist (already absent)" % cert.name
                        })
                        return result
                except Exception:
                    result.update({
                        'changed': False, 'failed': False,
                        self.MODULE_NAME: {'state': 'absent'},
                        'msg': "CA certificate '%s' does not exist (already absent)" % cert.name
                    })
                    return result
            if operation == 'enforced':
                read_only_fields = {'id', 'created', 'modified', 'url'}
                argspec_fields = set(argspec.get('argument_spec', {}).keys())
                try:
                    find_result = manager.execute(
                        operation='find',
                        module_name=self.MODULE_NAME,
                        ansible_data={'name': cert.name}
                    )
                except ValueError:
                    find_result = None
                if find_result and find_result.get('id'):
                    merged = {}
                    for k in argspec_fields:
                        if k in auth_params:
                            continue
                        if k in validated_params:
                            merged[k] = validated_params[k]
                        elif k == 'name':
                            merged[k] = find_result.get(k) or cert.name
                        else:
                            merged[k] = None
                    for ro in read_only_fields:
                        if ro in find_result:
                            merged[ro] = find_result[ro]
                    merged.setdefault('name', cert.name or find_result.get('name'))
                    cert_data = {k: v for k, v in merged.items() if hasattr(AnsibleCACertificate, k)}
                    cert_data.setdefault('name', cert.name)
                    cert = AnsibleCACertificate(**cert_data)
                    operation = 'update'
                else:
                    operation = 'create'
            ansible_data = asdict(cert)
            if operation == 'update' and validated_params.get('state') == 'enforced':
                ansible_data['_platform_enforced'] = True
            try:
                manager_result = manager.execute(
                    operation=operation,
                    module_name=self.MODULE_NAME,
                    ansible_data=ansible_data
                )
            except ValueError as e:
                if operation == 'find' and ('not found' in str(e).lower() or 'resource with' in str(e).lower()):
                    result.update({
                        'changed': False, 'failed': False, self.MODULE_NAME: {},
                        'exists': False, 'msg': "CA certificate '%s' does not exist" % cert.name
                    })
                    return result
                raise
            read_only_fields = {'id', 'created', 'modified', 'url'}
            argspec_fields = set(argspec.get('argument_spec', {}).keys())
            filtered_result = {k: v for k, v in manager_result.items() if k in argspec_fields or k in read_only_fields}
            try:
                validated_output = self._validate_data(
                    {k: v for k, v in filtered_result.items() if k in argspec_fields},
                    argspec, 'output'
                )
                for field in read_only_fields:
                    if field in filtered_result:
                        validated_output[field] = filtered_result[field]
            except Exception:
                validated_output = manager_result
            result.update({
                'changed': manager_result.get('changed', False),
                'failed': False,
                self.MODULE_NAME: validated_output,
                'id': validated_output.get('id'),
                'name': validated_output.get('name'),
            })
            if operation == 'find':
                result['exists'] = bool(validated_output.get('id'))
            elif operation == 'delete':
                result[self.MODULE_NAME]['state'] = 'absent'
            action_end = time.perf_counter()
            timing = manager_result.get('_timing', {})
            result.setdefault('_timing', {})['action_plugin_time'] = action_end - action_start
            result['_timing']['manager_processing_time'] = timing.get('manager_processing_time', 0)
            result['_timing']['api_call_time'] = timing.get('api_call_time', 0)
        except Exception as e:
            import traceback
            self._display.vvv("Error in ca_certificate action plugin: %s" % e)
            result['failed'] = True
            result['msg'] = str(e)
            if self._display.verbosity >= 3:
                result['exception'] = traceback.format_exc()
        return result
