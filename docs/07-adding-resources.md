# Adding Resources

This is the step-by-step guide for adding a new platform action plugin to `ansible.platform`.
Follow these steps in order. Each step has a clear deliverable and a quality check.

**Time estimate**:

| Phase | Simple resource | Complex resource |
|-------|----------------|-----------------|
| `generate_resource.py` (boilerplate generation) | ~2 minutes | ~2 minutes |
| Review + fix generated `DOCUMENTATION` stub | 10–15 minutes | 20–30 minutes |
| Transform mixin business logic (manual) | 20–30 minutes | 1–2 hours |
| Molecule mock scenario (manual) | 30–45 minutes | 45–60 minutes |
| Integration test run + fix failures | 30–45 minutes | 45–90 minutes |
| **Total** | **~1.5 hours** | **~3–5 hours** |

A **simple resource** has mostly 1:1 field mappings and no reference fields (e.g. `organization`, `feature_flag`).
A **complex resource** has ref fields (name → ID resolution), secondary endpoints, `fields_to_null` transitions, or write-only fields (e.g. `authenticator_map`, `service_node`, `user`).

---

## Table of Contents

1. [Prerequisites Checklist](#section-0-prerequisites-checklist)
2. [Overview: The Seven Files](#overview-the-seven-files)
3. [Step 1: Run the Generator](#section-1-run-the-generator)
4. [Step 2: Review Generated DOCUMENTATION and AnsibleFoo](#section-2-review-the-generated-documentation-and-ansiblefoo-dataclass)
5. [Step 3: Complete the Transform Mixin](#section-3-complete-the-transform-mixin)
6. [Step 4: Review the Generated Action Plugin](#section-4-review-the-generated-action-plugin)
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

Every platform action plugin requires these seven files. Files 1–4 are generated
automatically. Files 5–7 require manual work.

| # | File | How produced |
|---|------|-------------|
| 1 | `plugins/modules/<resource>.py` | **Generated** — `DOCUMENTATION` + `EXAMPLES` scaffold from OpenAPI spec |
| 2 | `plugins/plugin_utils/ansible_models/<resource>.py` | **Generated** — `AnsibleFoo` dataclass from OpenAPI spec |
| 3 | `plugins/plugin_utils/api/v1/<resource>.py` | **Generated skeleton, manual completion** — `APIFoo_v1` dataclass + `FooTransformMixin_v1` business logic |
| 4 | `plugins/action/<resource>.py` | **Generated** — `ActionModule(BaseResourceActionPlugin)` skeleton |
| 5 | `tests/integration/targets/<resource>s_test/tasks/main.yml` | **Generated scaffold, manual completion** — integration test structure |
| 6 | `extensions/molecule/<resource>_mock/` | **Manual** — Molecule mock scenario |
| 7 | (optional) `tests/unit/` | **Manual** — unit tests for complex transform logic |

---

## SECTION 1: Run the Generator

All boilerplate is produced in one command from the Gateway OpenAPI spec. Run from
the collection root:

```bash
python tools/generate_resource.py \
    --tag <openapi_tag> \
    --spec ../aap-openapi-specs/2.6/gateway.json
```

Use `--dry-run` first to preview what will be created without writing files:

```bash
python tools/generate_resource.py \
    --tag teams \
    --spec ../aap-openapi-specs/2.6/gateway.json \
    --dry-run
```

> **Note**: `team` already exists in the collection — this example uses it because
> the real spec fields (`name`, `organization`, `description`) make the workflow
> concrete. When adding a genuinely new resource, use its actual OpenAPI tag.

**What the generator produces**:

```
plugins/modules/team.py                    ← DOCUMENTATION + EXAMPLES
plugins/plugin_utils/ansible_models/team.py ← AnsibleTeam dataclass
plugins/plugin_utils/api/v1/team.py        ← APITeam_v1 + TransformMixin skeleton
plugins/action/team.py                     ← ActionModule skeleton
tests/integration/targets/teams_test/
  tasks/main.yml                           ← integration test scaffold
```

The generator skips files that already exist. Use `--overwrite` to regenerate them.

**Quality check**: Confirm all five files were created. Run:

```bash
ansible-doc -t module ansible.platform.team
```

All options from the OpenAPI spec should render correctly.

---

## SECTION 2: Review the Generated `DOCUMENTATION` and `AnsibleFoo` Dataclass

The generator produces these from the OpenAPI spec. They are usually correct but
always need a human review pass before proceeding.

**For `plugins/modules/<resource>.py`** — check:
- `short_description` is clear and user-facing (not an API description copy-paste)
- `required: true` is set on truly required fields only
- Reference fields (org names, cluster names) have a description mentioning they
  accept the resource name, not an ID
- `EXAMPLES` block covers at least `state: present` and `state: absent`
- `extends_documentation_fragment` includes `ansible.platform.auth` and `ansible.platform.state`

**For `plugins/plugin_utils/ansible_models/<resource>.py`** — check:
- Field names match `DOCUMENTATION.options` keys exactly
- Reference fields are `Optional[str]` (name), not `Optional[int]` (ID)
- Write-only fields like `password` have no default and are not in the reverse transform
- Read-only fields (`id`, `created`, `modified`) are `Optional[int/str] = None`

**Quality check**: Field names in `AnsibleFoo` must match `DOCUMENTATION.options`
keys exactly — they are what the action plugin receives as `task_vars`.

---

## SECTION 3: Complete the Transform Mixin (`plugins/plugin_utils/api/v1/`)

The generator produces the `APIFoo_v1` dataclass and a `FooTransformMixin_v1` skeleton.
The `APIFoo_v1` dataclass is usually correct as-is. The transform mixin skeleton needs
to be completed — this is the only file that requires real authorship.

It bridges Ansible model ↔ Gateway API wire format. The generator stubs out the
methods; you fill in the logic.

```python
# plugins/plugin_utils/api/v1/team.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any

from ansible_collections.ansible.platform.plugins.plugin_utils.platform.base_transform import (
    BaseTransformMixin,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.platform.types import (
    EndpointOperation, TransformContext,
)
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.team import (
    AnsibleTeam,
)


@dataclass
class APITeam_v1:
    """Wire format for Gateway API v1 teams.

    Note: organization is an INTEGER ID in the API wire format.
    The Ansible model uses a name string — the mixin resolves the name to an ID.
    """
    name: str
    organization: int              # INTEGER ID in API, not name
    description: Optional[str] = None
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None


class TeamTransformMixin_v1(BaseTransformMixin):
    """
    Transforms between AnsibleTeam (name-based) and APITeam_v1 (ID-based).
    """

    def from_ansible_data(
        self,
        ansible_instance: AnsibleTeam,
        context: TransformContext,
    ) -> APITeam_v1:
        """Forward: Ansible model → API wire format."""
        # Reference field: resolve organization name → integer ID
        org_id = context.manager.lookup_resource_id(
            'organization', ansible_instance.organization
        )

        params: Dict[str, Any] = {
            'name': ansible_instance.name,
            'organization': org_id,
        }

        if ansible_instance.description is not None:
            params['description'] = ansible_instance.description

        return APITeam_v1(**params)

    def from_api(
        self,
        api_data: dict,
        context: TransformContext,
    ) -> AnsibleTeam:
        """Reverse: API response → Ansible model."""
        # Resolve organization ID back to name for the return value
        org_name = None
        if api_data.get('organization'):
            org_name = context.manager.lookup_resource_name(
                'organization', api_data['organization']
            )

        return AnsibleTeam(
            id=api_data.get('id'),
            name=api_data.get('name'),
            organization=org_name,
            description=api_data.get('description'),
            created=api_data.get('created'),
            modified=api_data.get('modified'),
        )

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        return {
            'create': EndpointOperation(
                method='POST',
                path='/api/gateway/v1/teams/',
            ),
            'update': EndpointOperation(
                method='PATCH',
                path='/api/gateway/v1/teams/{id}/',
            ),
            'delete': EndpointOperation(
                method='DELETE',
                path='/api/gateway/v1/teams/{id}/',
            ),
            'get': EndpointOperation(
                method='GET',
                path='/api/gateway/v1/teams/{id}/',
            ),
            'list': EndpointOperation(
                method='GET',
                path='/api/gateway/v1/teams/',
            ),
        }

    @classmethod
    def get_lookup_field(cls) -> str:
        return 'name'

    @classmethod
    def get_find_list_query_params(cls, ansible_instance: AnsibleTeam) -> dict:
        # Teams are scoped per organization — include both in the lookup
        return {'name': ansible_instance.name}
```

**Quality check**:
- All fields in `APITeam_v1` correspond to actual Gateway API fields (cross-check against `gateway.json` `Team` schema)
- `from_ansible_data` resolves `organization` name → ID before sending to API
- `from_api` resolves `organization` ID → name in the return value
- `get_lookup_field()` returns `'name'` — the unique identifier within an org
- Endpoint paths match the actual Gateway API (`/api/gateway/v1/teams/`)

---

## SECTION 4: Review the Generated Action Plugin (`plugins/action/`)

The generator produces a complete `ActionModule` skeleton. For most resources it
requires no changes — review it and move on. The only things to check:

```python
# plugins/action/team.py
# Auto-generated by tools/generate_resource.py — review before committing.
from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible_collections.ansible.platform.plugins.action.base_action import (
    BaseResourceActionPlugin,
)


class ActionModule(BaseResourceActionPlugin):
    """Resource module action plugin for team."""

    USER_MODEL = "plugins.plugin_utils.ansible_models.team.AnsibleTeam"
```

**Quality check**:
- `USER_MODEL` dotted path resolves to the correct `AnsibleFoo` dataclass for this resource
- The class has no extra logic — all behaviour lives in `BaseResourceActionPlugin` and the transform mixin
- File name matches the module stub (`team.py` → `ansible.platform.team`)

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
module: team
short_description: Manage teams in the AAP platform
extends_documentation_fragment:
  - ansible.platform.auth
  - ansible.platform.state
options:
  name:
    description: Name of the team.
    type: str
    required: true
  organization:
    description: Name of the organization this team belongs to.
    type: str
    required: true
"""
```

When you run `ansible-doc -t module ansible.platform.team`, the `gateway_idle_timeout` option will appear in the final documentation.

**Quality check**: `ansible-doc -t module ansible.platform.<resource>` shows the new option.

---

## SECTION 5: Integration Test (`tests/integration/targets/`)

Create a test target that exercises all states against a live (or mock) AAP instance.

```
tests/integration/targets/teams_test/
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
  ansible.platform.team:
    name: "test-{{ test_id }}"
    organization: Default
    state: absent
  failed_when: false

- name: Create a team
  ansible.platform.team:
    name: "test-{{ test_id }}"
    organization: Default
    description: "Integration test team"
    state: present
  register: create_result

- name: Assert create succeeded
  assert:
    that:
      - create_result.changed
      - create_result.id is defined
      - create_result.name == "test-{{ test_id }}"

- name: Run create again (idempotency check)
  ansible.platform.team:
    name: "test-{{ test_id }}"
    organization: Default
    description: "Integration test team"
    state: present
  register: idempotent_result

- name: Assert idempotent run did not change
  assert:
    that:
      - not idempotent_result.changed

- name: Check existence
  ansible.platform.team:
    name: "test-{{ test_id }}"
    organization: Default
    state: exists
  register: exists_result

- name: Assert exists check correct
  assert:
    that:
      - exists_result.exists
      - not exists_result.changed

- name: Delete the team
  ansible.platform.team:
    name: "test-{{ test_id }}"
    organization: Default
    state: absent
  register: delete_result

- name: Assert delete succeeded
  assert:
    that:
      - delete_result.changed

- name: Delete again (idempotency check)
  ansible.platform.team:
    name: "test-{{ test_id }}"
    organization: Default
    state: absent
  register: delete_idempotent

- name: Assert double-delete is a no-op
  assert:
    that:
      - not delete_idempotent.changed

- name: Clean up always block
  block:
    - name: Final cleanup
      ansible.platform.team:
        name: "test-{{ test_id }}"
        organization: Default
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
    - name: Create team (first run)
      ansible.platform.team:
        name: test-team
        organization: Default
        description: "Mock test team"
        state: present
      register: first_run

    - name: Assert first run changed
      assert:
        that: first_run.changed

    - name: Create team (idempotency run)
      ansible.platform.team:
        name: test-team
        organization: Default
        description: "Mock test team"
        state: present
      register: second_run

    - name: Assert idempotency
      assert:
        that: not second_run.changed
...
```

Run locally:
```bash
cd extensions/molecule/team_mock
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
def from_api(self, api_data: dict, context: TransformContext) -> AnsibleTeam:
    # WRONG: return api_data  # This is a dict, not a dataclass
    
    # RIGHT: create an instance
    return AnsibleTeam(
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
