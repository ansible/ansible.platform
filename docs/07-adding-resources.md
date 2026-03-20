# Adding Resources

This is the step-by-step guide for adding a new resource module to `ansible.platform`.
Follow these steps in order. Each step has a clear deliverable and a quality check.

**Time estimate**: 1–2 hours for a simple resource, 2–4 hours for complex (ref fields,
secondary endpoints, version-specific quirks).

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

## Step 1: Write the Module Stub (`plugins/modules/`)

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

## Step 2: Create the Ansible Model (`plugins/plugin_utils/ansible_models/`)

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

## Step 3: Create the API Model and Transform Mixin (`plugins/plugin_utils/api/v1/`)

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

## Step 4: Create the Action Plugin (`plugins/action/`)

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

## Step 5: Integration Test (`tests/integration/targets/`)

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

## Step 6: Molecule Mock Scenario (`extensions/molecule/`)

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

---

## Checklist Before Opening a PR

```
Code:
[ ] plugins/modules/<resource>.py       — DOCUMENTATION + EXAMPLES
[ ] plugins/plugin_utils/ansible_models/<resource>.py   — AnsibleFoo dataclass
[ ] plugins/plugin_utils/api/v1/<resource>.py           — APIFoo_v1 + mixin
[ ] plugins/action/<resource>.py                        — ActionModule

Tests:
[ ] tests/integration/targets/<resource>s_test/         — integration tests
[ ] extensions/molecule/<resource>_mock/                — mock scenario

Validation:
[ ] ansible-doc renders correctly (no YAML errors in DOCUMENTATION)
[ ] tox -e black,flake8,isort  passes
[ ] pytest tests/unit/ passes
[ ] molecule converge + verify passes for <resource>_mock
[ ] ansible-test integration <resource>s_test passes
[ ] Idempotency: second run of present = changed: false
[ ] Idempotency: second run of absent = changed: false
[ ] check_mode: true = no API calls, correct changed value
```
