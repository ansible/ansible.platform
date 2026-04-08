# Adding Resources

This is the step-by-step guide for adding a new resource module to `ansible.platform`.
Follow these steps in order. Each step has a clear deliverable and a quality check.

**Time estimate**: 1–2 hours for a simple resource, 2–4 hours for complex (ref fields,
secondary endpoints, version-specific quirks).

---

## Table of Contents

1. [Prerequisites Checklist](#section-0-prerequisites-checklist)
2. [Overview: The Seven Files](#overview-the-seven-files)
3. [Step 1: Module Stub](#section-1-write-the-module-stub)
4. [Step 2: Ansible Model](#section-2-create-the-ansible-model)
5. [Step 3: API Model & Transform](#section-3-create-the-api-model-and-transform-mixin)
6. [Step 4: Action Plugin](#section-4-create-the-action-plugin)
7. [Step 5: Integration Tests](#section-5-integration-test)
8. [Step 6: Molecule Scenario](#section-6-molecule-mock-scenario)
9. [Common Patterns Catalog](#common-patterns-catalog)
10. [Troubleshooting](#troubleshooting)
11. [Pre-PR Checklist](#checklist-before-opening-a-pr)

---

## SECTION 0: Prerequisites Checklist

Before starting, verify these foundations exist:

- [ ] **Registry discovers your module**: After adding `plugins/modules/<resource>.py`, run
  ```bash
  python -c "from ansible_collections.ansible.platform.plugins.plugin_utils.platform.registry import APIVersionRegistry; r = APIVersionRegistry(); modules = r.discover_modules(); print([m for m in modules if '<resource>' in m])"
  ```
  You should see your new module in the list.

- [ ] **Mock server available**: Start the mock Gateway server (required for Molecule tests):
  ```bash
  python tools/mock_gateway_server.py --port 8080
  ```
  Visit http://localhost:8080/api/gateway/v1/ in your browser to confirm it's running.

- [ ] **Integration test environment (if live)**: For Layer 3 tests, verify you have valid
  credentials:
  ```bash
  cat tests/integration/integration_config.yml
  # Should contain: gateway_host, gateway_username, gateway_password
  ```

---

## Overview: The Seven Files

Every resource requires these seven files:

| # | File | Contents |
|---|------|---------|
| 1 | `plugins/modules/<resource>.py` | `DOCUMENTATION` + `EXAMPLES` |
| 2 | `plugins/plugin_utils/ansible_models/<resource>.py` | `AnsibleFoo` dataclass |
| 3 | `plugins/plugin_utils/api/v1/<resource>.py` | `APIFoo_v1` + `FooTransformMixin_v1` |
| 4 | `plugins/action/<resource>.py` | `ActionModule(BaseResourceActionPlugin)` |
| 5 | `tests/integration/targets/<resource>s_test/tasks/main.yml` | Integration tests |
| 6 | `extensions/molecule/<resource>_mock/` | Molecule mock scenario |
| 7 | (optional) Unit tests | `tests/unit/` |

---

## SECTION 1: Write the Module Stub (`plugins/modules/`)

Start with `DOCUMENTATION`. This is the contract with playbook authors and the source
of truth for the `AnsibleFoo` dataclass.

```python
# plugins/modules/notification_profile.py

DOCUMENTATION = r"""
---
module: notification_profile
short_description: Manage notification profiles on Ansible Automation Platform
description:
  - Create, update, delete, and query notification profiles on AAP Gateway.
version_added: "2.5.0"
author:
  - Your Name (@yourhandle)
extends_documentation_fragment:
  - ansible.platform.auth
  - ansible.platform.state
options:
  name:
    description:
      - Name of the notification profile.
    type: str
    required: true
  notification_type:
    description:
      - The type of notification backend.
    type: str
    choices: [email, slack, webhook]
    required: true
  url:
    description:
      - Destination URL (required for slack and webhook types).
    type: str
  organization:
    description:
      - Name of the organization that owns this profile.
    type: str
"""

EXAMPLES = r"""
- name: Create a Slack notification profile
  ansible.platform.notification_profile:
    name: ops-alerts
    notification_type: slack
    url: https://hooks.slack.com/services/T00/B00/xxx
    organization: Red Hat
    state: present

- name: Delete a notification profile
  ansible.platform.notification_profile:
    name: ops-alerts
    state: absent
...
"""
```

**Quality check**: Run `ansible-doc -t module ansible.platform.notification_profile`
and verify all options render correctly.

---

## SECTION 2: Create the Ansible Model (`plugins/plugin_utils/ansible_models/`)

Translate `DOCUMENTATION.options` directly into a `@dataclass`. Rules:
- `required: true` → positional field (no default)
- `required: false` / not required → `Optional[T] = None`
- `type: str` → `str` or `Optional[str]`
- `type: bool` → `Optional[bool]`
- `type: int` → `Optional[int]`
- `type: list` → `Optional[List[str]]`
- `type: dict` → `Optional[Dict[str, Any]]`
- Reference fields (org names, cluster names) → `Optional[Union[str, int]]` to accept
  both names and IDs

```python
# plugins/plugin_utils/ansible_models/notification_profile.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class AnsibleNotificationProfile:
    name: str                              # required (no default)
    notification_type: str                 # required
    url: Optional[str] = None
    organization: Optional[str] = None    # ref field — org name
    state: str = 'present'
    # read-only (populated from API response):
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
```

**Quality check**: Field names must match `DOCUMENTATION.options` keys exactly.

---

## SECTION 3: Create the API Model and Transform Mixin (`plugins/plugin_utils/api/v1/`)

This is the most important file. It bridges Ansible model ↔ Gateway API wire format.

```python
# plugins/plugin_utils/api/v1/notification_profile.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any, ClassVar

from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_transform import (
    BaseTransformMixin,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import (
    EndpointOperation, TransformContext,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.notification_profile import (
    AnsibleNotificationProfile,
)


@dataclass
class APINotificationProfile_v1:
    """Wire format for Gateway API v1 notification profiles."""
    name: str
    notification_type: str
    url: Optional[str] = None
    organization: Optional[int] = None   # INTEGER ID in API, not name
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None


class NotificationProfileTransformMixin_v1(BaseTransformMixin):
    """
    Transforms between AnsibleNotificationProfile and APINotificationProfile_v1.
    """

    def from_ansible_data(
        self,
        ansible_instance: AnsibleNotificationProfile,
        context: TransformContext,
    ) -> APINotificationProfile_v1:
        """Forward: Ansible model → API wire format."""
        params: Dict[str, Any] = {
            'name': ansible_instance.name,
            'notification_type': ansible_instance.notification_type,
        }

        if ansible_instance.url is not None:
            params['url'] = ansible_instance.url

        # Reference field: resolve organization name → integer ID
        if ansible_instance.organization is not None:
            org_id = context.manager.lookup_resource_id(
                'organization', ansible_instance.organization
            )
            params['organization'] = org_id

        return APINotificationProfile_v1(**params)

    def from_api(
        self,
        api_data: dict,
        context: TransformContext,
    ) -> AnsibleNotificationProfile:
        """Reverse: API response → Ansible model."""
        # Resolve organization ID back to name for the return value
        org_name = None
        if api_data.get('organization'):
            org_name = context.manager.lookup_resource_id(
                'organization', api_data['organization']
            )

        return AnsibleNotificationProfile(
            id=api_data.get('id'),
            name=api_data.get('name'),
            notification_type=api_data.get('notification_type'),
            url=api_data.get('url'),
            organization=org_name,
            created=api_data.get('created'),
            modified=api_data.get('modified'),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            'create': EndpointOperation(
                method='POST',
                path='/api/gateway/v1/notification-profiles/',
            ),
            'update': EndpointOperation(
                method='PATCH',
                path='/api/gateway/v1/notification-profiles/{id}/',
            ),
            'delete': EndpointOperation(
                method='DELETE',
                path='/api/gateway/v1/notification-profiles/{id}/',
            ),
            'get': EndpointOperation(
                method='GET',
                path='/api/gateway/v1/notification-profiles/{id}/',
            ),
            'list': EndpointOperation(
                method='GET',
                path='/api/gateway/v1/notification-profiles/',
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return 'name'

    @classmethod
    def get_find_list_query_params(cls, ansible_instance: AnsibleNotificationProfile) -> dict:
        return {'name': ansible_instance.name}
```

**Quality check**:
- All fields in `APINotificationProfile_v1` correspond to actual Gateway API fields
- `from_ansible_data` handles all non-null optional fields
- `from_api` maps all fields back correctly
- `get_lookup_field()` returns the field that uniquely identifies the resource
- Endpoint paths match the actual Gateway API

---

## SECTION 4: Create the Action Plugin (`plugins/action/`)

The action plugin is thin. It delegates everything to `BaseResourceActionPlugin`.
The only resource-specific code here is `MODULE_NAME` and the idempotency comparison.

```python
# plugins/action/notification_profile.py
from __future__ import absolute_import, division, print_function
__metaclass__ = type

import dataclasses
from ansible_collections.ansible.platform.plugins.action.base_action import (
    BaseResourceActionPlugin,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.notification_profile import (
    AnsibleNotificationProfile,
)

DOCUMENTATION_MODULE = 'notification_profile'


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = 'notification_profile'

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}

        result = super().run(tmp, task_vars)
        if result.get('failed'):
            return result

        # Load and validate args from DOCUMENTATION
        from ansible_collections.ansible.platform.plugins.modules import notification_profile as mod
        argspec = self._build_argspec_from_docs(mod.DOCUMENTATION)
        validated, errors = self._validate_args(self._task.args, argspec)
        if errors:
            return dict(failed=True, msg=f"Invalid arguments: {errors}")

        state = validated.get('state', 'present')
        manager = self._get_or_spawn_manager(task_vars)

        ansible_data = {k: v for k, v in validated.items() if v is not None}

        try:
            if state == 'absent':
                find_result = manager.execute('find', self.MODULE_NAME, ansible_data)
                if not find_result.get('id'):
                    return dict(changed=False, exists=False)
                if self._task.check_mode:
                    return dict(changed=True, check_mode=True)
                manager.execute('delete', self.MODULE_NAME,
                                {**ansible_data, 'id': find_result['id']})
                return dict(changed=True)

            elif state == 'exists':
                find_result = manager.execute('find', self.MODULE_NAME, ansible_data)
                exists = bool(find_result.get('id'))
                return dict(changed=False, exists=exists, **find_result)

            else:  # present / enforced
                find_result = manager.execute('find', self.MODULE_NAME, ansible_data)
                if find_result.get('id'):
                    # Check idempotency
                    if self._is_idempotent(validated, find_result):
                        return dict(changed=False, **find_result)
                    if self._task.check_mode:
                        return dict(changed=True, check_mode=True)
                    result = manager.execute('update', self.MODULE_NAME,
                                            {**ansible_data, 'id': find_result['id']})
                else:
                    if self._task.check_mode:
                        return dict(changed=True, check_mode=True)
                    result = manager.execute('create', self.MODULE_NAME, ansible_data)

                return dict(changed=True, **result)

        except Exception as exc:
            return dict(failed=True, msg=str(exc))
        finally:
            self.cleanup()

    def _is_idempotent(self, desired: dict, existing: dict) -> bool:
        """Return True if all specified desired fields match the existing resource."""
        for key, desired_val in desired.items():
            if key in ('state', 'id'):
                continue
            if desired_val is None:
                continue
            if existing.get(key) != desired_val:
                return False
        return True
```

**Quality check**:
- `MODULE_NAME` matches the module file name
- All states handled: `present`, `absent`, `exists`
- `check_mode` respected
- `cleanup()` called in `finally` block

---

## SECTION 4b: Document Fragment Registration (`plugins/doc_fragments/`)

If your resource introduces a new connection-level or authentication option (like `gateway_idle_timeout`), it must be registered in the documentation fragment so it appears in `ansible-doc` output.

### Example: Adding `gateway_idle_timeout` to the auth fragment

```python
# plugins/doc_fragments/auth.py

class ModuleDocFragment(object):
    DOCUMENTATION = r"""
options:
  aap_hostname:
    description: URL to automation platform gateway.
    type: str
    aliases: [ gateway_hostname ]
  aap_username:
    description: Username for your automation platform gateway.
    type: str
    aliases: [ gateway_username ]
  # ... other existing options ...
  
  gateway_idle_timeout:
    description:
      - Idle timeout in seconds for gateway manager process.
      - If a manager process has no activity for this duration, it is terminated.
      - Default is 300 seconds (5 minutes).
    type: int
    aliases: [ aap_idle_timeout ]
"""
```

### In your module's DOCUMENTATION

Reference the fragment:

```python
DOCUMENTATION = r"""
---
module: notification_profile
short_description: Manage notification profiles
extends_documentation_fragment:
  - ansible.platform.auth
  - ansible.platform.state
options:
  name:
    description: Name of the profile.
    type: str
    required: true
"""
```

When you run `ansible-doc -t module ansible.platform.notification_profile`, the `gateway_idle_timeout` option will appear in the final documentation.

**Quality check**: `ansible-doc -t module ansible.platform.<resource>` shows the new option.

---

## SECTION 5: Integration Test (`tests/integration/targets/`)

Create a test target that exercises all states against a live (or mock) AAP instance.

```
tests/integration/targets/notification_profiles_test/
├── tasks/
│   └── main.yml
└── meta/
    └── main.yml
```

`meta/main.yml`:
```yaml
---
dependencies:
  - role: setup_gateway
```

`tasks/main.yml` — minimal structure:
```yaml
---
- name: Generate a test ID to avoid conflicts with existing resources
  set_fact:
    test_id: "{{ lookup('password', '/dev/null length=8 chars=ascii_lowercase') }}"

- name: Delete any pre-existing test resource (cleanup from failed runs)
  ansible.platform.notification_profile:
    name: "test-{{ test_id }}"
    state: absent
  failed_when: false

- name: Create a notification profile
  ansible.platform.notification_profile:
    name: "test-{{ test_id }}"
    notification_type: webhook
    url: https://example.com/hook
    state: present
  register: create_result

- name: Assert create succeeded
  assert:
    that:
      - create_result.changed
      - create_result.id is defined
      - create_result.name == "test-{{ test_id }}"

- name: Run create again (idempotency check)
  ansible.platform.notification_profile:
    name: "test-{{ test_id }}"
    notification_type: webhook
    url: https://example.com/hook
    state: present
  register: idempotent_result

- name: Assert idempotent run did not change
  assert:
    that:
      - not idempotent_result.changed

- name: Check existence
  ansible.platform.notification_profile:
    name: "test-{{ test_id }}"
    state: exists
  register: exists_result

- name: Assert exists check correct
  assert:
    that:
      - exists_result.exists
      - not exists_result.changed

- name: Delete the notification profile
  ansible.platform.notification_profile:
    name: "test-{{ test_id }}"
    state: absent
  register: delete_result

- name: Assert delete succeeded
  assert:
    that:
      - delete_result.changed

- name: Delete again (idempotency check)
  ansible.platform.notification_profile:
    name: "test-{{ test_id }}"
    state: absent
  register: delete_idempotent

- name: Assert double-delete is a no-op
  assert:
    that:
      - not delete_idempotent.changed

- name: Clean up always block
  block:
    - name: Final cleanup
      ansible.platform.notification_profile:
        name: "test-{{ test_id }}"
        state: absent
      failed_when: false
  tags: [always]
...
```

**Quality check**:
- Create, idempotency, exists, delete, delete-idempotency all tested
- Cleanup in `always:` block so a test failure does not leave stale resources
- `failed_when: false` on cleanup (not `ignore_errors: true`)

---

## SECTION 6: Molecule Mock Scenario (`extensions/molecule/`)

The mock scenario tests idempotency without a live AAP instance. It uses the
mock Gateway server (`tools/mock_gateway_server.py`).

```
extensions/molecule/<resource>_mock/
├── molecule.yml
├── converge.yml
├── verify.yml
└── cleanup.yml
```

`molecule.yml`:
```yaml
---
dependency:
  name: galaxy
driver:
  name: default
platforms:
  - name: instance
provisioner:
  name: ansible
  inventory:
    hosts:
      all:
        hosts:
          localhost:
            ansible_connection: local
verifier:
  name: ansible
...
```

`converge.yml`:
```yaml
---
- name: Converge
  hosts: localhost
  gather_facts: false

  pre_tasks:
    - name: Start mock Gateway server
      include_role:
        name: start_mock_server

  tasks:
    - name: Create notification profile (first run)
      ansible.platform.notification_profile:
        name: test-profile
        notification_type: webhook
        url: https://example.com/hook
        state: present
      register: first_run

    - name: Assert first run changed
      assert:
        that: first_run.changed

    - name: Create notification profile (idempotency run)
      ansible.platform.notification_profile:
        name: test-profile
        notification_type: webhook
        url: https://example.com/hook
        state: present
      register: second_run

    - name: Assert idempotency
      assert:
        that: not second_run.changed
...
```

Run locally:
```bash
cd extensions/molecule/notification_profile_mock
molecule converge
molecule verify
molecule destroy
```

---

## Common Patterns Catalog

### Pattern 1: Simple 1:1 field mapping

When all Ansible field names match API field names and types, the mixin is trivial:

```python
def from_ansible_data(self, ansible_instance, context):
    return APIFoo_v1(
        **{k: v for k, v in dataclasses.asdict(ansible_instance).items()
           if v is not None and k not in ('state', 'id', 'created', 'modified', 'url')}
    )
```

### Pattern 2: Name-to-ID reference field

```python
if ansible_instance.organization is not None:
    org_id = context.manager.lookup_resource_id(
        'organization', ansible_instance.organization
    )
    params['organization'] = org_id
```

### Pattern 3: Write-only field (password)

Never send a write-only field on update unless explicitly provided. Never return it
from `from_api`:

```python
# In from_ansible_data:
if ansible_instance.password:  # only if a new password was set
    params['password'] = ansible_instance.password

# In from_api: simply omit the password field
return AnsibleUser(
    id=api_data['id'],
    username=api_data['username'],
    # password NOT included — never in API response
)
```

### Pattern 4: List as space-separated string

```python
# Forward
if ansible_instance.redirect_uris is not None:
    if isinstance(ansible_instance.redirect_uris, list):
        params['redirect_uris'] = ' '.join(ansible_instance.redirect_uris)
    else:
        params['redirect_uris'] = ansible_instance.redirect_uris

# Reverse
uris = api_data.get('redirect_uris', '')
return AnsibleApplication(
    redirect_uris=uris.split() if uris else None,
    ...
)
```

### Pattern 5: Composite key lookup

When a resource has no single unique field but is identified by a combination:

```python
@classmethod
def get_find_list_query_params(cls, ansible_instance) -> dict:
    return {
        'role_definition': ansible_instance.role_definition,
        'user': ansible_instance.user,
    }
```

### Pattern 6: Secondary endpoint (post-create operation)

```python
@classmethod
def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
    return {
        'create': EndpointOperation(method='POST', path='/api/gateway/v1/users/'),
        'associate_orgs': EndpointOperation(
            method='POST',
            path='/api/gateway/v1/users/{id}/organizations/',
            operation_type='secondary',
            depends_on='create',
            order=2,
        ),
    }
```

### Pattern 7: `get_fields_to_null_for_update()` — Key field change incompatibility

**Use case**: When changing a key field (like `map_type` in `authenticator_map`), certain other fields become incompatible and must be explicitly nulled to avoid API errors.

For example, `authenticator_map` with `map_type: saml` has different required fields than `map_type: oidc`. When switching types, the old type's fields must be cleared.

```python
class AuthenticatorMapTransformMixin_v1(BaseTransformMixin):
    """Transform mixin for AuthenticatorMap API v1."""
    
    @classmethod
    def get_fields_to_null_for_update(cls, ansible_instance, existing_data) -> Dict[str, str]:
        """
        Return fields that must be nulled (set to empty string) on update.
        
        When a key field (like map_type) changes, incompatible fields from the old
        type must be explicitly cleared to avoid "field not allowed for this type" errors.
        """
        # If map_type changed, null out all type-specific fields
        if ansible_instance.map_type != existing_data.get('map_type'):
            return {
                'saml_auto_create_users': '',
                'saml_url': '',
                'saml_username_path': '',
                'oidc_client_id': '',
                'oidc_client_secret': '',
                'oidc_scope': '',
            }
        return {}
```

In your action plugin or update operation, check and apply these nulls:

```python
# In transform or manager
fields_to_null = mixin_class.get_fields_to_null_for_update(
    ansible_instance, 
    existing_resource
)
api_data.update(fields_to_null)
```

### Pattern 8: `state: enforced` vs `state: present` — Defaults reset behavior

**`state: present`** (default): Only specified fields are updated. Unspecified optional fields are left as-is.

```yaml
- ansible.platform.authenticator_map:
    name: my-map
    map_type: saml
    state: present
  # Only `name` and `map_type` are checked/updated.
  # If `saml_auto_create_users` already exists with value true, it stays true.
```

**`state: enforced`**: Unspecified optional fields are reset to API defaults. Use this when you want a clean, predictable state.

```yaml
- ansible.platform.authenticator_map:
    name: my-map
    map_type: saml
    saml_url: https://idp.example.com
    state: enforced
  # Any other fields (e.g. saml_auto_create_users) are reset to defaults
  # if not explicitly specified.
```

**Implementation in action plugin**:

```python
if state == 'enforced':
    # Fill in defaults for fields not specified by user
    api_data = manager.apply_defaults(self.MODULE_NAME, api_data)
else:  # present
    # Only send what the user specified; let existing values persist
    api_data = {k: v for k, v in api_data.items() if v is not None}
```

---

## Troubleshooting

### Common Errors and Fixes

#### Error: "object of type dict has no attribute id"

**Symptom**: Integration test fails with `AttributeError: object of type dict has no attribute id`

**Root cause**: Your transform mixin's `from_api()` is returning a dict instead of an `AnsibleFoo` instance.

**Fix**:
```python
def from_api(self, api_data: dict, context: TransformContext) -> AnsibleNotificationProfile:
    # WRONG: return api_data  # This is a dict, not a dataclass
    
    # RIGHT: create an instance
    return AnsibleNotificationProfile(
        id=api_data.get('id'),
        name=api_data.get('name'),
        # ... other fields
    )
```

---

#### Error: "changed always true on second run"

**Symptom**: Idempotency test fails: first run is `changed: true` (correct), second run is also `changed: true` (wrong).

**Root cause**: Your idempotency comparison is broken. Usually the `ref` field (like `name` or `id`) comparison is failing.

**Fix**: Ensure your `_is_idempotent()` method properly compares the reference field:

```python
def _is_idempotent(self, desired: dict, existing: dict) -> bool:
    """Compare desired against existing, ignoring state and id."""
    for key, desired_val in desired.items():
        if key in ('state', 'id'):
            continue
        if desired_val is None:
            continue
        # CRITICAL: Compare with correct type. If existing[key] is int, convert desired_val.
        existing_val = existing.get(key)
        if str(existing_val) != str(desired_val):  # Safe comparison
            return False
    return True
```

---

#### Error: "object has no attribute 'id' in assertion"

**Symptom**: Integration test asserts fail because result dict doesn't contain `id`.

**Root cause**: Your action plugin isn't returning the API response data in the result dict.

**Fix**: Ensure the manager's result is unpacked into the return:

```python
result = manager.execute('create', self.MODULE_NAME, ansible_data)
return dict(changed=True, **result)  # <-- **result unpacks the id, name, etc.
```

---

#### Error: "KeyError: 'organization'" in `from_ansible_data()`

**Symptom**: Reference field lookup fails with KeyError.

**Root cause**: Your code assumes the field exists when it might be None.

**Fix**:
```python
# WRONG
org_id = context.manager.lookup_resource_id('organization', ansible_instance.organization)

# RIGHT
if ansible_instance.organization is not None:
    org_id = context.manager.lookup_resource_id('organization', ansible_instance.organization)
    params['organization'] = org_id
```

---

#### Error: "Molecule test hangs or times out"

**Symptom**: `molecule converge` hangs indefinitely.

**Root cause**: Mock server not started or not listening.

**Fix**:
```bash
# Start mock server in a separate terminal
python tools/mock_gateway_server.py --port 8080

# In another terminal, test connectivity
curl http://localhost:8080/api/gateway/v1/organizations/

# Then run Molecule
cd extensions/molecule/<resource>_mock
molecule converge
```

---

#### Error: "field_name does not exist in the API spec"

**Symptom**: Mock server returns 400 Bad Request for valid field.

**Root cause**: Your API dataclass includes fields not in the actual Gateway API spec.

**Fix**: Verify the field name matches the real API. Check the API documentation or mock server's endpoint definition:
```bash
grep -r "field_name" tools/mock_gateway_server.py
```

---

## Checklist Before Opening a PR

### Code Files

```
Core Resource Files:
[ ] plugins/modules/<resource>.py
    - DOCUMENTATION complete with all options and examples
    - EXAMPLES section shows create, update (if applicable), delete, exists
    - Module extends proper doc_fragments (auth, state)
    
[ ] plugins/plugin_utils/ansible_models/<resource>.py
    - Dataclass fields match DOCUMENTATION options exactly
    - Required fields have no default (no Optional[])
    - Optional fields use Optional[T] = None
    - Read-only fields (id, created, etc.) included
    
[ ] plugins/plugin_utils/api/v1/<resource>.py
    - APIFoo_v1 dataclass matches API wire format
    - TransformMixin.from_ansible_data() handles all non-null fields
    - TransformMixin.from_api() returns AnsibleFoo instance (not dict)
    - get_endpoint_operations() defines all CRUD operations
    - get_lookup_field() returns the unique identifier field
    - Ref field resolution (name → ID) in place
    
[ ] plugins/action/<resource>.py
    - MODULE_NAME matches filename
    - All states handled: present, absent, exists
    - Idempotency check correct (ref field comparison)
    - check_mode respected (no API calls)
    - cleanup() called in finally block
    
[ ] plugins/doc_fragments/auth.py (if adding new auth option)
    - New option documented with type, description, aliases
    - Option follows naming convention
```

### Test Files

```
[ ] tests/integration/targets/<resource>s_test/tasks/main.yml
    - Generate test_id with set_fact for unique resource names
    - Pre-cleanup task with failed_when: false
    - Create with state: present (assert changed: true)
    - Recreate idempotency test (assert changed: false)
    - exists state check (if supported)
    - Update test (if applicable)
    - Delete with state: absent (assert changed: true)
    - Delete idempotency (assert changed: false)
    - always: cleanup block with failed_when: false (not ignore_errors)
    
[ ] tests/integration/targets/<resource>s_test/meta/main.yml
    - Dependencies listed (usually setup_gateway role)
    
[ ] extensions/molecule/<resource>_mock/molecule.yml
    - Driver configured correctly (default, local)
    - Provisioner paths point to correct playbooks
    - Test sequence: converge, verify, cleanup
    
[ ] extensions/molecule/<resource>_mock/converge.yml
    - Pre-tasks start mock server
    - Create test (first_run) with state: present
    - Idempotency test (second_run) with state: present
    - exists check if supported
    - Delete test with state: absent
    - Delete idempotency test
    - Cleanup in always block
    
[ ] extensions/molecule/<resource>_mock/verify.yml
    - Optional additional assertions beyond converge
    
[ ] extensions/molecule/<resource>_mock/cleanup.yml
    - Ensure test resources are removed
```

### Validation Checklist

```
Syntax & Linting:
[ ] ansible-doc -t module ansible.platform.<resource> renders correctly
[ ] python -m py_compile plugins/modules/<resource>.py (no syntax errors)
[ ] python -m py_compile plugins/plugin_utils/ansible_models/<resource>.py
[ ] python -m py_compile plugins/plugin_utils/api/v1/<resource>.py
[ ] python -m py_compile plugins/action/<resource>.py
[ ] tox -e black,flake8,isort passes (or: black + isort + flake8 manual)
[ ] ansible-lint tests/integration/targets/<resource>s_test/ passes
[ ] ansible-lint extensions/molecule/<resource>_mock/ passes

Unit Tests:
[ ] pytest tests/unit/ passes (all existing tests still pass)

Mock Testing (Layer 2):
[ ] molecule converge -s <resource>_mock succeeds
[ ] molecule verify -s <resource>_mock succeeds (if verify.yml exists)
[ ] molecule destroy -s <resource>_mock cleans up
[ ] Second converge run shows no changes (idempotency)

Integration Testing (Layer 3 — if live AAP available):
[ ] ansible-test integration <resource>s_test --venv --requirements passes
[ ] Idempotency: second run of present = changed: false
[ ] Idempotency: second run of absent = changed: false

Behavioral Testing:
[ ] check_mode: true in a task does not make API calls
[ ] check_mode result has correct changed value (matches non-check run)
[ ] Ref field resolution works (names → IDs, vice versa)
[ ] Write-only fields (password) never returned in output
[ ] Read-only fields (id, created) present in output
```

### Common Pre-PR Mistakes to Avoid

- [ ] Forgot to import the Ansible model in action plugin
- [ ] Idempotency check doesn't account for type differences (int vs str)
- [ ] `ignore_errors: true` in cleanup (should be `failed_when: false`)
- [ ] DOCUMENTATION field names don't match dataclass field names (casing)
- [ ] API operation path has typo (test against real API docs)
- [ ] Transform mixin's `from_api()` returns dict instead of dataclass instance
- [ ] Ref field (organization, user) not resolved to ID before sending to API
- [ ] Missing fields in API dataclass that Gateway API actually requires
- [ ] Molecule scenario uses hardcoded resource name instead of test_id variable
- [ ] Module DOCUMENTATION missing `extends_documentation_fragment` for auth options
- [ ] Result dict not unpacked (`return dict(**result)`) so caller can't access fields
