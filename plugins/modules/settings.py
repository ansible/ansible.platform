#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2023, Sean Sullivan <@sean-m-sullivan>
# (c) 2018, Nikhil Jain <nikjain@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = """
---
module: settings
author: Sean Sullivan (@sean-m-sullivan)
short_description: Modify automation platform gateway settings.
description:
    - Modify automation platform gateway settings.
options:
    settings:
      description:
        - A data structure to be sent into the settings endpoint
      type: dict
      required: True
extends_documentation_fragment: ansible.platform.auth
"""

EXAMPLES = """
- name: Configure platform gateway settings
  ansible.platform.settings:
    settings:
      gateway_token_name: "<gateway_token_name>"
      gateway_access_token_expiration: 6000
      gateway_basic_auth_enabled: true/false
      gateway_proxy_url: https://localhost:9080
      gateway_proxy_url_ignore_cert: true/false

- name: Configure JWT settings
  ansible.platform.settings:
    settings:
      jwt_private_key: "<jwt_private_key>"
      jwt_public_key: |
        -----BEGIN PUBLIC KEY-----
        <public_key_value>
        -----END PUBLIC KEY-----
      jwt_expiration_buffer_in_seconds: <jwt_expiration_buffer_in_seconds>

- name: Set backend and timeout configurations
  ansible.platform.settings:
    settings:
      status_endpoint_backend_timeout_seconds: <timeout_seconds>
      status_endpoint_backend_verify: true/false
      resource_client_request_timeout: <timeout_in_seconds>
      request_timeout: <timeout_in_seconds>

- name: Configure password and security policies
  ansible.platform.settings:
    settings:
      password_min_length: 0
      password_min_digits: 0
      password_min_upper: 0
      password_min_special: 0
      allow_admins_to_set_insecure: false

- name: Customize login and session behavior
  ansible.platform.settings:
    settings:
      LOGIN_REDIRECT_OVERRIDE: "<redirect_url>"
      custom_login_info: "<custom_login_message>"
      custom_logo: "<path_to_logo>"
      SOCIAL_AUTH_USERNAME_IS_FULL_EMAIL: true/false
      SESSION_COOKIE_AGE: <cookie_age_in_seconds>

- name: Configure SSO and OAuth2 settings
  ansible.platform.settings:
    settings:
      CONTROLLER_SSO_URL: "<controller_sso_url>"
      AUTOMATION_HUB_SSO_URL: "<automation_hub_sso_url>"
      ALLOW_OAUTH2_FOR_EXTERNAL_USERS: true/false

- name: Set pagination behavior
  ansible.platform.settings:
    settings:
      DEFAULT_PAGE_SIZE: <default_page_size>
      MAX_PAGE_SIZE: <max_page_size>

- name: Enable analytics and tracking
  ansible.platform.settings:
    settings:
      INSIGHTS_TRACKING_STATE: true/false

- name: Configure Red Hat integration
  ansible.platform.settings:
    settings:
      RED_HAT_CONSOLE_URL: "<red_hat_console_url>"
      REDHAT_USERNAME: "<redhat_username>"
      REDHAT_PASSWORD: "<encrypted_redhat_password>"
      SUBSCRIPTIONS_USERNAME: "<subscriptions_username>"
      SUBSCRIPTIONS_PASSWORD: "<encrypted_subscriptions_password>"

- name: Set Automation Analytics gather interval
  ansible.platform.settings:
    settings:
      AUTOMATION_ANALYTICS_GATHER_INTERVAL: <gather_interval_in_seconds>
...
"""
