# Module: ansible.platform.feature_flag

Configure feature flags in Automation Platform Gateway.

## Note: Module is new in 2.7.x

This module did not exist in 2.5.x. No migration needed — use directly in new playbooks.

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | str | yes | Feature flag name, format: `FEATURE_<flag-name>_ENABLED` |
| `value` | str | no | Value to set (e.g., `'True'` or `'False'`). Required for `present`/`enforced` |
| `state` | str | no | Desired state: `exists` (default), `present`, `absent`, or `enforced` |

## Result structure

### Example result (2.7.x)

```json
{
    "changed": true,
    "feature_flag": {
        "id": 1,
        "name": "FEATURE_EXAMPLE_ENABLED",
        "ui_name": "Example Feature",
        "condition": "boolean",
        "value": "True",
        "required": false,
        "support_level": "DEVELOPER_PREVIEW",
        "visibility": true,
        "toggle_type": "run-time",
        "description": "Enables example functionality",
        "support_url": "https://docs.example.com/feature",
        "labels": ["experimental", "ui"],
        "state": true
    },
    "elapsed_ms": 134,
    "api_version": "1"
}
```

## State: exists — example (default state)

```yaml
- name: Check if feature flag exists
  ansible.platform.feature_flag:
    name: FEATURE_EXAMPLE_ENABLED
    state: exists
  register: result

# result:
# {
#   "changed": false,
#   "feature_flag": {
#     "id": 1,
#     "name": "FEATURE_EXAMPLE_ENABLED",
#     "value": "False",
#     "condition": "boolean"
#   }
# }
```

## State: present — enable/disable example

```yaml
- name: Enable a runtime feature flag
  ansible.platform.feature_flag:
    name: FEATURE_EXAMPLE_ENABLED
    value: "True"
    state: present
  register: result

- name: Disable a runtime feature flag
  ansible.platform.feature_flag:
    name: FEATURE_EXAMPLE_ENABLED
    value: "False"
    state: present
  register: result
```

## State: enforced — example

`enforced` is stricter than `present` — it ensures exact match without idempotency concerns.

```yaml
- name: Ensure feature flag has exact value
  ansible.platform.feature_flag:
    name: FEATURE_CUSTOM_SETTING_ENABLED
    value: "custom_value"
    state: enforced
  register: result
```

## Full example playbook

```yaml
---
- name: Manage feature flags
  hosts: localhost
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_pw }}"

  tasks:
    - name: Enable experimental UI features
      ansible.platform.feature_flag:
        name: FEATURE_EXPERIMENTAL_UI_ENABLED
        value: "True"
        state: present
      register: ui_flag

    - name: Disable legacy API endpoint
      ansible.platform.feature_flag:
        name: FEATURE_LEGACY_API_ENABLED
        value: "False"
        state: present

    - name: Check if advanced logging is enabled
      ansible.platform.feature_flag:
        name: FEATURE_ADVANCED_LOGGING_ENABLED
        state: exists
      register: logging_flag

    - name: Print flag status
      debug:
        msg: "Advanced logging state: {{ logging_flag.feature_flag.value }}"

    - name: Set multiple feature flags
      ansible.platform.feature_flag:
        name: "{{ item.name }}"
        value: "{{ item.value }}"
        state: present
      loop:
        - name: FEATURE_EXAMPLE_ENABLED
          value: "True"
        - name: FEATURE_BETA_UI_ENABLED
          value: "True"
        - name: FEATURE_LEGACY_SUPPORT_ENABLED
          value: "False"
```

## Common patterns

### Conditional feature enablement

```yaml
- name: Check if analytics feature exists
  ansible.platform.feature_flag:
    name: FEATURE_ANALYTICS_ENABLED
    state: exists
  register: analytics_check

- name: Enable analytics in production
  ansible.platform.feature_flag:
    name: FEATURE_ANALYTICS_ENABLED
    value: "True"
    state: present
  when: inventory_hostname in groups['production']

- name: Disable analytics in development
  ansible.platform.feature_flag:
    name: FEATURE_ANALYTICS_ENABLED
    value: "False"
    state: present
  when: inventory_hostname in groups['development']
```

### Verify installation-time flags are immutable

```yaml
- name: Check feature flag toggle type
  ansible.platform.feature_flag:
    name: FEATURE_CORE_FUNCTIONALITY_ENABLED
    state: exists
  register: core_flag

- name: Warn if trying to modify install-time flag
  debug:
    msg: "WARNING: This is an install-time flag ({{ core_flag.feature_flag.toggle_type }}), cannot be modified at runtime"
  when: core_flag.feature_flag.toggle_type != 'run-time'
```

### Configuration profiles with feature flags

```yaml
- name: Apply minimal feature set
  ansible.platform.feature_flag:
    name: "{{ item.name }}"
    value: "{{ item.value }}"
    state: present
  loop: "{{ minimal_profile }}"
  vars:
    minimal_profile:
      - name: FEATURE_ANALYTICS_ENABLED
        value: "False"
      - name: FEATURE_ADVANCED_LOGGING_ENABLED
        value: "False"
      - name: FEATURE_EXPERIMENTAL_UI_ENABLED
        value: "False"

- name: Apply full feature set
  ansible.platform.feature_flag:
    name: "{{ item.name }}"
    value: "{{ item.value }}"
    state: present
  loop: "{{ full_profile }}"
  vars:
    full_profile:
      - name: FEATURE_ANALYTICS_ENABLED
        value: "True"
      - name: FEATURE_ADVANCED_LOGGING_ENABLED
        value: "True"
      - name: FEATURE_EXPERIMENTAL_UI_ENABLED
        value: "True"
```
