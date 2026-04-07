# Module: ansible.platform.settings

Modify automation platform gateway settings.

## Note: Module is new in 2.7.x (though settings management existed before in different form)

This module provides a new interface for managing gateway settings with detailed change tracking.

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `settings` | dict | yes | A dictionary of setting key-value pairs to apply |

## Result structure

### Example result (2.7.x)

```json
{
    "changed": true,
    "old_values": {
        "gateway_token_name": "old_token_name",
        "gateway_access_token_expiration": 3600
    },
    "new_values": {
        "gateway_token_name": "new_gateway_token",
        "gateway_access_token_expiration": 6000
    },
    "diff": {
        "before": {
            "gateway_token_name": "old_token_name",
            "gateway_access_token_expiration": 3600
        },
        "after": {
            "gateway_token_name": "new_gateway_token",
            "gateway_access_token_expiration": 6000
        }
    },
    "elapsed_ms": 234,
    "api_version": "1"
}
```

## State: (N/A — always present)

This module does not use `state` parameter. It always applies the settings provided.

## Full example playbook

```yaml
---
- name: Configure platform gateway settings
  hosts: localhost
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_pw }}"

  tasks:
    - name: Configure basic gateway settings
      ansible.platform.settings:
        settings:
          gateway_token_name: "aap-gateway-token"
          gateway_access_token_expiration: 6000
          gateway_basic_auth_enabled: true
          gateway_proxy_url: https://proxy.example.com:9080
          gateway_proxy_url_ignore_cert: false

    - name: Configure JWT settings
      ansible.platform.settings:
        settings:
          jwt_private_key: "{{ vault_jwt_private_key }}"
          jwt_public_key: "{{ vault_jwt_public_key }}"
          jwt_expiration_buffer_in_seconds: 600

    - name: Set backend and timeout configurations
      ansible.platform.settings:
        settings:
          status_endpoint_backend_timeout_seconds: 30
          status_endpoint_backend_verify: true
          resource_client_request_timeout: 60
          request_timeout: 120

    - name: Configure password and security policies
      ansible.platform.settings:
        settings:
          password_min_length: 12
          password_min_digits: 1
          password_min_upper: 1
          password_min_special: 1
          allow_admins_to_set_insecure: false

    - name: Customize login and session behavior
      ansible.platform.settings:
        settings:
          LOGIN_REDIRECT_OVERRIDE: "https://example.com/dashboard"
          custom_login_info: "Welcome to AAP Gateway"
          SOCIAL_AUTH_USERNAME_IS_FULL_EMAIL: true
          SESSION_COOKIE_AGE: 3600

    - name: Configure SSO and OAuth2 settings
      ansible.platform.settings:
        settings:
          CONTROLLER_SSO_URL: "https://controller.example.com/sso/"
          AUTOMATION_HUB_SSO_URL: "https://hub.example.com/sso/"
          ALLOW_OAUTH2_FOR_EXTERNAL_USERS: true

    - name: Set pagination behavior
      ansible.platform.settings:
        settings:
          DEFAULT_PAGE_SIZE: 25
          MAX_PAGE_SIZE: 500

    - name: Enable analytics and tracking
      ansible.platform.settings:
        settings:
          INSIGHTS_TRACKING_STATE: true

    - name: Configure Red Hat integration
      ansible.platform.settings:
        settings:
          RED_HAT_CONSOLE_URL: "https://console.redhat.com"
          REDHAT_USERNAME: "{{ vault_redhat_user }}"
          REDHAT_PASSWORD: "{{ vault_redhat_password }}"
          SUBSCRIPTIONS_USERNAME: "{{ vault_subscriptions_user }}"
          SUBSCRIPTIONS_PASSWORD: "{{ vault_subscriptions_password }}"

    - name: Set Automation Analytics gather interval
      ansible.platform.settings:
        settings:
          AUTOMATION_ANALYTICS_GATHER_INTERVAL: 3600
```

## Common patterns

### Check settings before applying changes (dry-run)

```yaml
- name: Validate settings with check mode
  block:
    - name: Test settings with --check
      ansible.platform.settings:
        settings:
          password_min_length: 16
          gateway_access_token_expiration: 7200
      check_mode: true
      register: check_result

    - name: Show what would change
      debug:
        msg: "Would change: {{ check_result.diff }}"

    - name: Apply if validated
      ansible.platform.settings:
        settings:
          password_min_length: 16
          gateway_access_token_expiration: 7200
      when: not check_result.failed
```

### Environment-specific settings

```yaml
- name: Apply development settings
  ansible.platform.settings:
    settings:
      gateway_proxy_url_ignore_cert: true
      status_endpoint_backend_timeout_seconds: 10
      DEBUG: true
  when: environment == 'development'

- name: Apply production settings
  ansible.platform.settings:
    settings:
      gateway_proxy_url_ignore_cert: false
      status_endpoint_backend_timeout_seconds: 30
      DEBUG: false
  when: environment == 'production'
```

### Security hardening configuration

```yaml
- name: Configure strict security settings
  ansible.platform.settings:
    settings:
      password_min_length: 20
      password_min_digits: 2
      password_min_upper: 2
      password_min_special: 2
      allow_admins_to_set_insecure: false
      SESSION_COOKIE_AGE: 1800              # 30 minutes
      gateway_access_token_expiration: 3600 # 1 hour
```

### JWT configuration with vault

```yaml
- name: Configure JWT with vault-managed keys
  ansible.platform.settings:
    settings:
      jwt_private_key: "{{ lookup('hashi_vault', 'secret=secret/jwt/private_key') }}"
      jwt_public_key: "{{ lookup('hashi_vault', 'secret=secret/jwt/public_key') }}"
      jwt_expiration_buffer_in_seconds: 300
  no_log: true  # Don't log keys in output
```

### Proxy configuration with certificate validation

```yaml
- name: Configure gateway proxy with certificate
  ansible.platform.settings:
    settings:
      gateway_proxy_url: "{{ proxy_url }}"
      gateway_proxy_url_ignore_cert: false
  vars:
    proxy_url: "https://corporate-proxy.example.com:8080"
```

### Settings backup and restore

```yaml
- name: Backup current settings
  block:
    - name: Get all current settings
      ansible.platform.settings:
        settings: {}
      register: current_settings

    - name: Save to backup file
      copy:
        content: "{{ current_settings.old_values | to_nice_yaml }}"
        dest: "/tmp/gateway_settings_backup_{{ now(utc=True).strftime('%Y%m%d_%H%M%S') }}.yaml"

- name: Restore settings from backup
  ansible.platform.settings:
    settings: "{{ lookup('file', '/tmp/gateway_settings_backup.yaml') | from_yaml }}"
  when: restore_from_backup | default(false)
```

### Conditional settings based on feature flags

```yaml
- name: Apply feature-dependent settings
  block:
    - name: Check if new auth system is enabled
      ansible.platform.feature_flag:
        name: FEATURE_NEW_AUTH_ENABLED
        state: exists
      register: new_auth_flag

    - name: Apply modern settings if feature enabled
      ansible.platform.settings:
        settings:
          SOCIAL_AUTH_USERNAME_IS_FULL_EMAIL: true
          ALLOW_OAUTH2_FOR_EXTERNAL_USERS: true
      when: new_auth_flag.feature_flag.value | bool

    - name: Apply legacy settings if feature disabled
      ansible.platform.settings:
        settings:
          SOCIAL_AUTH_USERNAME_IS_FULL_EMAIL: false
      when: not (new_auth_flag.feature_flag.value | bool)
```
