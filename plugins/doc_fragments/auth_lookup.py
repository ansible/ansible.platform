# -*- coding: utf-8 -*-

# Copyright: (c) 2020, Ansible by Red Hat, Inc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment(object):
    # Automation Platform Gateway documentation fragment
    DOCUMENTATION = r"""
options:
  host:
    description:
    - URL to automation platform gateway.
    - If value not set, the environment variable E(GATEWAY_HOSTNAME) will be used,
      with E(AAP_HOSTNAME) as a fallback.
    - If value not specified by any means, the value of C(127.0.0.1) will be used
    type: str
    env:
    - name: AAP_HOSTNAME
    - name: GATEWAY_HOSTNAME
  username:
    description:
    - Username for your automation platform gateway.
    - If value not set, the environment variable E(GATEWAY_USERNAME) will be used,
      with E(AAP_USERNAME) as a fallback.
    type: str
    env:
    - name: AAP_USERNAME
    - name: GATEWAY_USERNAME
  password:
    description:
    - Password for your automation platform gateway.
    - If value not set, the environment variable E(GATEWAY_PASSWORD) will be used,
      with E(AAP_PASSWORD) as a fallback.
    type: str
    env:
    - name: AAP_PASSWORD
    - name: GATEWAY_PASSWORD
  oauth_token:
    description:
    - The automation platform gateway token to use.
    - This value can be in one of two formats.
    - A string which is the token itself. (i.e. bqV5txm97wqJqtkxlMkhQz0pKhRMMX)
    - A dictionary structure as returned by the gateway_token module.
    - If value not set, the environment variable E(GATEWAY_API_TOKEN) will be used,
      with E(AAP_TOKEN) as a fallback.
    type: raw
    env:
    - name: AAP_TOKEN
    - name: GATEWAY_API_TOKEN
  verify_ssl:
    description:
    - Whether to allow insecure connections to automation platform gateway.
    - If C(no), SSL certificates will not be validated.
    - This should only be used on personally controlled sites using self-signed certificates.
    - If value not set, the environment variable E(GATEWAY_VERIFY_SSL) will be used,
      with E(AAP_VALIDATE_CERTS) as a fallback.
    type: bool
    env:
    - name: AAP_VALIDATE_CERTS
    - name: GATEWAY_VERIFY_SSL
    aliases: [ validate_certs ]
  request_timeout:
    description:
    - Specify the timeout Ansible should use in requests to the automation platform gateway.
    - Defaults to 10s, but this is handled by the shared module_utils code
    - If value not set, the environment variable E(GATEWAY_REQUEST_TIMEOUT) will be used,
      with E(AAP_REQUEST_TIMEOUT) as a fallback.
    type: float
    env:
    - name: AAP_REQUEST_TIMEOUT
    - name: GATEWAY_REQUEST_TIMEOUT
    aliases: [ request_timeout ]

notes:
- If no I(config_file) is provided we will attempt to use the
  defaults to find your host information.
- I(config_file) should be in the following format
    host=hostname
    username=username
    password=password
"""
