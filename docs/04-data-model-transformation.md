# Data Model Transformation

## Table of Contents

1. [SECTION 1: The Three-Tier Data Flow](#section-1-the-three-tier-data-flow)
2. [SECTION 2: Tier 1 — Ansible Model](#section-2-tier-1--ansible-model)
3. [SECTION 3: Tier 2 — API Model](#section-3-tier-2--api-model)
4. [SECTION 4: The Transform Mixin](#section-4-the-transform-mixin)
5. [SECTION 5: Case Study — Simple Resource (organization)](#section-5-case-study--simple-resource-organization)
6. [SECTION 6: Case Study — Reference Fields (service_node)](#section-6-case-study--reference-fields-service_node)
7. [SECTION 7: Case Study — List URI Fields (application)](#section-7-case-study--list-uri-fields-application)
8. [SECTION 8: Case Study — Conditional Fields with fields_to_null (authenticator_map)](#section-8-case-study--conditional-fields-with-fields_to_null-authenticator_map)
9. [SECTION 9: Case Study — Write-Only Fields (user)](#section-9-case-study--write-only-fields-user)
10. [SECTION 10: Write-Only Fields Pattern](#section-10-write-only-fields-pattern)
11. [SECTION 11: Fields to Null on Update Pattern](#section-11-fields-to-null-on-update-pattern)
12. [SECTION 12: Backward-Compatible Flat Keys](#section-12-backward-compatible-flat-keys)
13. [SECTION 13: The TransformContext Object](#section-13-the-transformcontext-object)
14. [SECTION 14: Agent Automation Boundary](#section-14-agent-automation-boundary)

---

## SECTION 1: The Three-Tier Data Flow

Every resource in `ansible.platform` has three data representations. Understanding these
three tiers is essential to understanding any part of the codebase.

```
┌──────────────────────────────────────────────────────────────────┐
│  Tier 1: Ansible Model  (ansible_models/user.py)                 │
│                                                                  │
│  AnsibleUser dataclass — the STABLE user-facing interface.       │
│  Field names: Ansible snake_case conventions.                    │
│  Types: Python primitives, Optional, List, Dict.                 │
│  Never changes across API versions.                              │
└───────────────────────┬──────────────────────────────────────────┘
                        │ TransformMixin.from_ansible_data()
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│  Tier 2: API Model  (api/v1/user.py)                             │
│                                                                  │
│  APIUser_v1 dataclass — the WIRE FORMAT for Gateway API v1.      │
│  Field names: match the Gateway API field names exactly.         │
│  Types: match the API's expected types (IDs as int, not str).    │
│  Changes per API version.                                        │
└───────────────────────┬──────────────────────────────────────────┘
                        │ HTTP request/response
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│  AAP Gateway REST API                                            │
└──────────────────────────────────────────────────────────────────┘
```

The **Transform Mixin** is the translator between Tier 1 and Tier 2. It is the only
place where version-specific and resource-specific logic lives.

### Why Three Tiers?

**Tier 1: Stability for Users.** The Ansible model is the stable contract. Playbooks written today work unchanged even when the Gateway API is upgraded to v2, v3, or beyond. Field names, types, and structure remain consistent.

**Tier 2: Precision for APIs.** The API model is a mirror of the actual API schema. Integer IDs, camelCase naming, nested structures — exactly as the API expects. Regenerating this layer from the API's OpenAPI spec is safe and low-risk.

**Tier 3: Transformation Logic.** The mixin is where all business logic lives: name-to-ID resolution, conditional field handling, multi-endpoint orchestration. This is the only place that changes when the API evolves.

---

## SECTION 2: Tier 1 — Ansible Model

The Ansible model (`AnsibleUser`, `AnsibleOrganization`, etc.) defines the stable
contract between the collection and playbook authors.

### Properties

- Defined as a Python `@dataclass` in `plugins/plugin_utils/ansible_models/`.
- Field names follow Ansible conventions: `snake_case`, descriptive English names.
- Optional fields use `Optional[T] = None`.
- Reference fields (like `organizations`) use the human-readable name (`str`), not the
  API's integer ID. Name-to-ID resolution happens inside the transform mixin.
- Read-only fields returned from the API (`id`, `created`, `modified`, `url`) are
  present as `Optional[int/str] = None` — populated on output, not required on input.
- Write-only fields like `password` are optional and never returned from the API.

### Field Categories in Ansible Models

| Category | Behavior | Example |
|----------|----------|---------|
| **Required input** | Must be provided; never optional | `username` |
| **Optional input** | May be provided; defaults to None | `email`, `first_name` |
| **Read-only output** | Returned by API after creation; not accepted in input | `id`, `created`, `modified` |
| **Write-only input** | Accepted on create/password-change; never returned | `password` |
| **Reference** | User provides human name; mixin resolves to ID | `organizations: ["Red Hat"]` |

### Example: `AnsibleUser`

```python
@dataclass
class AnsibleUser:
    username: str                           # required
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None          # write-only
    is_superuser: Optional[bool] = None
    is_platform_auditor: Optional[bool] = None
    organizations: Optional[List[str]] = None   # org NAMES, not IDs
    associated_authenticators: Optional[Dict[str, Any]] = None
    state: str = 'present'
    # read-only, populated from API response:
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
```

This class **never changes** even when the Gateway API releases v2 with renamed fields
or restructured organization association. Playbooks written today work unchanged.

### Round-Trip Guarantee

The Ansible model is designed so that:
1. User input → Ansible model → forward transform → API call
2. API response → reverse transform → Ansible model → user output

The output format matches the input format, enabling idempotency: `desired == gathered` means no changes needed.

---

## SECTION 3: Tier 2 — API Model

The API model (`APIUser_v1`, `APIOrganization_v1`, etc.) defines the wire format for
a specific version of the Gateway API.

### Properties

- Defined as a Python `@dataclass` in `plugins/plugin_utils/api/v<N>/`.
- Field names match the Gateway API field names exactly (often different from Ansible names).
- Reference fields use the API's integer ID type (`int`), not names.
- One API model per resource per API version.
- Often generated from OpenAPI specs using `datamodel-code-generator` or similar tools.

### Example: `APIUser_v1`

```python
@dataclass
class APIUser_v1:
    username: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None
    is_superuser: Optional[bool] = None
    is_platform_auditor: Optional[bool] = None
    organization_ids: Optional[List[int]] = None   # INTEGER IDs, not names
    id: Optional[int] = None
    created: Optional[str] = None
    modified: Optional[str] = None
    url: Optional[str] = None
```

Note the key difference: `AnsibleUser.organizations` is `List[str]` (names).
`APIUser_v1.organization_ids` is `List[int]` (integers). The transform mixin bridges
this gap.

### Versioning Strategy

When Gateway API v2 renames `organization_ids` to `orgs` and adds a new field:

```python
# api/v2/user.py — only the differences from v1
@dataclass
class APIUser_v2(APIUser_v1):
    orgs: Optional[List[int]] = None      # renamed
    last_login: Optional[str] = None      # new field
    organization_ids: None = field(       # deprecated
        default=None, repr=False
    )
```

The `APIVersionRegistry` discovers `api/v2/user.py` automatically. The `DynamicClassLoader`
routes API v2 requests to `APIUser_v2` and `UserTransformMixin_v2`. No framework changes.

### API Payload Example

When making an API request, the action plugin sends:

```json
{
  "username": "alice",
  "email": "alice@example.com",
  "organization_ids": [1, 2],
  "password": "secretpassword"
}
```

The Ansible model had `organizations: ["Red Hat", "Acme"]`. The mixin resolved those names
to IDs `[1, 2]` and produced this API payload.

---

## SECTION 4: The Transform Mixin

The transform mixin is where all the resource-specific business logic lives. It is the
**only** file a developer needs to write when adding support for a new API version.

### Core Responsibilities

1. **Field mapping:** Name and type conversion (Ansible ↔ API).
2. **ID resolution:** Name-to-ID lookups for reference fields.
3. **Conditional logic:** Don't send password on update unless explicitly changed.
4. **Null handling:** For state `enforced`, send `""` or explicit null to clear fields.
5. **Multi-endpoint orchestration:** Declare secondary endpoints and their ordering.

### Protocol

Every mixin must implement:

```python
class UserTransformMixin_v1:
    def from_ansible_data(
        self,
        ansible_instance: AnsibleUser,
        context: TransformContext
    ) -> APIUser_v1:
        """Forward: Ansible model → API wire format."""

    def from_api(
        self,
        api_data: dict,
        context: TransformContext
    ) -> AnsibleUser:
        """Reverse: API response dict → Ansible model."""

    @classmethod
    def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
        """Return the CRUD endpoint map for this resource and API version."""

    @classmethod
    def get_lookup_field(cls) -> str:
        """Return the field name used for find-by-key queries."""

    @classmethod
    def get_find_list_query_params(cls, ansible_instance) -> Dict[str, Any]:
        """Return query parameters for the list endpoint when searching."""

    @classmethod
    def get_fields_to_null_for_update(
        cls,
        old_value: Any,
        new_value: Any,
        field_name: str
    ) -> List[str]:
        """Return list of field names to null when a conditional field changes."""
```

### Forward Transform: `from_ansible_data`

Maps the Ansible model to the API model. This is where:
- Name-to-ID resolution happens (`organization name → organization ID`)
- Field renaming happens (`organizations → organization_ids`)
- Conditional field logic applies (don't send `password` on update unless changed)
- Null sentinel values are applied for `enforced` state (send `""` to clear a field)

```python
def from_ansible_data(self, ansible_instance: AnsibleUser, context: TransformContext) -> APIUser_v1:
    params = {}

    # Simple field copy (same name, same type)
    for field in ['username', 'email', 'first_name', 'last_name',
                  'is_superuser', 'is_platform_auditor']:
        val = getattr(ansible_instance, field, None)
        if val is not None:
            params[field] = val

    # Name-to-ID resolution
    if ansible_instance.organizations is not None:
        params['organization_ids'] = context.manager.lookup_resource_id(
            'organization', ansible_instance.organizations
        )

    # Conditional: don't send empty password
    if ansible_instance.password:
        params['password'] = ansible_instance.password

    return APIUser_v1(**params)
```

### Reverse Transform: `from_api`

Maps an API response dict back to the Ansible model. This is where:
- ID-to-name resolution happens (`organization_id → organization_name`)
- API field names are mapped back to Ansible field names
- Read-only fields (`id`, `created`, `url`) are populated
- Write-only fields are explicitly NOT populated

```python
def from_api(self, api_data: dict, context: TransformContext) -> AnsibleUser:
    org_names = []
    if api_data.get('organization_ids'):
        org_names = context.manager.lookup_organization_names(
            api_data['organization_ids']
        )

    return AnsibleUser(
        id=api_data.get('id'),
        username=api_data.get('username'),
        email=api_data.get('email'),
        organizations=org_names,
        created=api_data.get('created'),
        modified=api_data.get('modified'),
        url=api_data.get('url'),
        # NOTE: password is NOT populated — write-only field
    )
```

### Endpoint Operations

The mixin declares all API endpoints for the resource. This is a dict mapping
operation names to `EndpointOperation` objects:

```python
@classmethod
def get_endpoint_operations(cls) -> Dict[str, EndpointOperation]:
    return {
        'create': EndpointOperation(
            method='POST',
            path='/api/gateway/v1/users/',
        ),
        'update': EndpointOperation(
            method='PATCH',
            path='/api/gateway/v1/users/{id}/',
        ),
        'delete': EndpointOperation(
            method='DELETE',
            path='/api/gateway/v1/users/{id}/',
        ),
        'get': EndpointOperation(
            method='GET',
            path='/api/gateway/v1/users/{id}/',
        ),
        'list': EndpointOperation(
            method='GET',
            path='/api/gateway/v1/users/',
        ),
        # Secondary: runs after create, order=2
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

## SECTION 5: Case Study — Simple Resource (organization)

The `organization` resource is a clean fit: every Ansible field maps directly to a
Gateway API field with the same name and same type.

### Field Mapping

```
AnsibleOrganization           APIOrganization_v1
─────────────────────         ──────────────────────
name: str                 →   name: str
description: Optional[str]→   description: Optional[str]
id: Optional[int]         ←   id: int  (read-only)
```

### Transform Mixin Implementation

The transform mixin for `organization` is trivial:

```python
def from_ansible_data(self, ansible_instance, context):
    return APIOrganization_v1(
        name=ansible_instance.name,
        description=ansible_instance.description,
    )

def from_api(self, api_data, context):
    return AnsibleOrganization(
        id=api_data['id'],
        name=api_data['name'],
        description=api_data.get('description'),
    )
```

### Why This Is Simple

- No ID resolution needed.
- No nested structures.
- No conditional fields.
- No write-only fields.
- One endpoint per operation.

### Idempotency

The action plugin finds the organization by name:

```python
find_result = manager.execute('find', 'organization', {'name': 'Red Hat'})

if find_result and find_result == desired_state:
    return dict(changed=False)

if find_result:
    manager.execute('update', 'organization', {**desired, 'id': find_result['id']})
else:
    manager.execute('create', 'organization', desired)
```

---

## SECTION 6: Case Study — Reference Fields (service_node)

The `service_node` resource has a `service_cluster` field that the user specifies by
**name** but the API expects an **ID**.

### Field Mapping

```
AnsibleServiceNode          APIServiceNode_v1
─────────────────────       ──────────────────────
name: str               →   name: str
address: str            →   address: str
service_cluster: str    →   service_cluster: int  ← name→ID resolution!
```

### Transform Mixin with Name-to-ID Resolution

```python
def from_ansible_data(self, ansible_instance, context):
    cluster_id = None
    if ansible_instance.service_cluster:
        cluster_id = context.manager.lookup_resource_id(
            'service_cluster',
            ansible_instance.service_cluster
        )
    return APIServiceNode_v1(
        name=ansible_instance.name,
        address=ansible_instance.address,
        service_cluster=cluster_id,
    )

def from_api(self, api_data, context):
    cluster_name = None
    if api_data.get('service_cluster'):
        cluster_name = context.manager.lookup_resource_name(
            'service_cluster',
            api_data['service_cluster']
        )
    return AnsibleServiceNode(
        id=api_data['id'],
        name=api_data['name'],
        address=api_data['address'],
        service_cluster=cluster_name,
    )
```

### Idempotency with Reference Fields

The idempotency check for reference fields requires special handling. When checking
whether a node needs updating, the existing node has `service_cluster: 42` (an ID)
but the desired state has `service_cluster: "my-cluster"` (a name). A naive string
comparison would always report a difference.

The correct approach: **resolve the desired name to an ID before comparing**:

```python
desired_cluster_name = ansible_instance.service_cluster
if desired_cluster_name:
    desired_cluster_id = context.manager.lookup_resource_id(
        'service_cluster', desired_cluster_name
    )
    existing_cluster_id = find_result.get('service_cluster')
    if desired_cluster_id == existing_cluster_id:
        # No change needed
        return dict(changed=False, ...)
```

This pattern is critical for all `ref_fields` in the collection. See the action plugins
for `service_node.py` and `service_key.py` for concrete implementations.

### Handling Lookup Failures

If a name cannot be resolved to an ID:

```python
try:
    cluster_id = context.manager.lookup_resource_id(
        'service_cluster',
        ansible_instance.service_cluster
    )
except LookupError as e:
    raise ValueError(
        f"service_cluster '{ansible_instance.service_cluster}' not found. "
        f"Available clusters: {e.available}"
    )
```

---

## SECTION 7: Case Study — List URI Fields (application)

The `application` resource has fields that accept a list of URIs (redirect URIs,
post-logout URIs). The user provides them as a Python list; the API expects a
space-separated string.

### Field Mapping

```
AnsibleApplication                    APIApplication_v1
─────────────────────────────         ──────────────────────────────
redirect_uris: Optional[List[str]]→   redirect_uris: Optional[str]
                                       "https://a.com https://b.com"
```

### Transform Mixin with List-to-String Conversion

```python
def _join_uri_list(uris):
    """Convert list of URIs to space-separated string."""
    if uris is None:
        return None
    if isinstance(uris, list):
        return " ".join(uris)
    return uris

def _split_uri_string(uri_string):
    """Convert space-separated string to list of URIs."""
    if uri_string is None:
        return None
    if isinstance(uri_string, str):
        return uri_string.split()
    return uri_string

def from_ansible_data(self, ansible_instance, context):
    return APIApplication_v1(
        name=ansible_instance.name,
        redirect_uris=_join_uri_list(ansible_instance.redirect_uris),
        post_logout_uris=_join_uri_list(ansible_instance.post_logout_uris),
    )

def from_api(self, api_data, context):
    return AnsibleApplication(
        id=api_data['id'],
        name=api_data['name'],
        redirect_uris=_split_uri_string(api_data.get('redirect_uris')),
        post_logout_uris=_split_uri_string(api_data.get('post_logout_uris')),
    )
```

### Idempotency with List Fields

List comparison requires normalization. The API may return URIs in any order:

```python
desired_uris = set(ansible_instance.redirect_uris or [])
existing_uris = set(api_data.get('redirect_uris', '').split())

if desired_uris == existing_uris:
    # No change needed despite potential order difference
    return dict(changed=False, ...)
```

### Round-Trip Validation

Ensure that transformations are reversible:

```python
original_list = ["https://a.com", "https://b.com"]
api_string = _join_uri_list(original_list)  # "https://a.com https://b.com"
reconstructed = _split_uri_string(api_string)  # ["https://a.com", "https://b.com"]
assert original_list == reconstructed  # Must hold for idempotency
```

---

## SECTION 8: Case Study — Conditional Fields with fields_to_null (authenticator_map)

The `authenticator_map` resource has a `map_type` field that determines which other
fields are valid. When `map_type` changes, certain fields must be explicitly set to
null in the PATCH request (sending an empty string `""`) to clear them from the API.

### Scenario: Type Change Requires Null-Out

**Before:** `map_type: "saml"` with SAML-specific fields populated.
```python
AnsibleAuthenticatorMap(
    name="corporate-sso",
    map_type="saml",
    saml_entity_id="https://example.com/saml",
    saml_metadata_url="https://example.com/saml/metadata",
    ldap_server=None,
)
```

**Desired change:** Switch to `map_type: "ldap"`.
```python
AnsibleAuthenticatorMap(
    name="corporate-sso",
    map_type="ldap",
    saml_entity_id=None,           # Must be explicitly nulled
    saml_metadata_url=None,        # Must be explicitly nulled
    ldap_server="ldap.example.com",
)
```

**API requirement:** When changing map_type, the PATCH body must explicitly set SAML fields to `""`:
```json
{
  "map_type": "ldap",
  "saml_entity_id": "",
  "saml_metadata_url": "",
  "ldap_server": "ldap.example.com"
}
```

### The `get_fields_to_null_for_update()` Classmethod

The mixin provides a classmethod that returns which fields to null when a specific
field changes:

```python
@classmethod
def get_fields_to_null_for_update(
    cls,
    old_value: Any,
    new_value: Any,
    field_name: str
) -> List[str]:
    """
    When field_name changes from old_value to new_value, return the
    list of field names that must be explicitly nulled in the PATCH.

    Args:
        old_value: The current value (from API or existing state).
        new_value: The desired value (from user input).
        field_name: The name of the field that changed.

    Returns:
        List of field names that should be set to "" (empty string) in PATCH.
    """
    if field_name == 'map_type':
        if old_value == 'saml' and new_value == 'ldap':
            # When switching FROM saml TO ldap, clear all SAML fields
            return ['saml_entity_id', 'saml_metadata_url', 'saml_cert']
        elif old_value == 'ldap' and new_value == 'saml':
            # When switching FROM ldap TO saml, clear all LDAP fields
            return ['ldap_server', 'ldap_user_dn', 'ldap_password']
        elif old_value == 'saml' and new_value == 'radius':
            return ['saml_entity_id', 'saml_metadata_url', 'saml_cert']
        elif old_value == 'ldap' and new_value == 'radius':
            return ['ldap_server', 'ldap_user_dn', 'ldap_password']
    return []
```

### Forward Transform with Conditional Null-Out

```python
def from_ansible_data(self, ansible_instance, context):
    params = {
        'name': ansible_instance.name,
        'map_type': ansible_instance.map_type,
    }

    # Determine which fields to null based on the map_type transition
    if context.operation == 'update':
        # Fetch existing state to detect transitions
        existing = context.manager.lookup_resource_id(
            'authenticator_map', ansible_instance.name
        )
        if existing:
            existing_state = context.manager.execute(
                'get', 'authenticator_map', {'id': existing}
            )
            fields_to_null = self.get_fields_to_null_for_update(
                existing_state.get('map_type'),
                ansible_instance.map_type,
                'map_type'
            )
            for field in fields_to_null:
                params[field] = ""  # Explicit empty string to clear

    # Add type-specific fields if present
    if ansible_instance.map_type == 'saml':
        if ansible_instance.saml_entity_id:
            params['saml_entity_id'] = ansible_instance.saml_entity_id
        if ansible_instance.saml_metadata_url:
            params['saml_metadata_url'] = ansible_instance.saml_metadata_url
    elif ansible_instance.map_type == 'ldap':
        if ansible_instance.ldap_server:
            params['ldap_server'] = ansible_instance.ldap_server

    return APIAuthenticatorMap_v1(**params)
```

### Testing the Pattern

```python
def test_map_type_transition_nulls_old_fields():
    """Verify that changing map_type nulls out fields of the old type."""
    old_state = {
        'map_type': 'saml',
        'saml_entity_id': 'https://example.com/saml',
        'saml_metadata_url': 'https://example.com/saml/metadata',
    }
    new_config = AnsibleAuthenticatorMap(
        name="corporate-sso",
        map_type="ldap",
        ldap_server="ldap.example.com",
    )
    context = TransformContext(
        manager=manager,
        operation='update',
        api_version='1',
    )
    mixin = AuthenticatorMapTransformMixin_v1()
    api_data = mixin.from_ansible_data(new_config, context)
    
    # Verify SAML fields are explicitly nulled
    assert api_data.saml_entity_id == ""
    assert api_data.saml_metadata_url == ""
    # And LDAP field is set
    assert api_data.ldap_server == "ldap.example.com"
```

---

## SECTION 9: Case Study — Write-Only Fields (user)

The `user` resource has a `password` field that is write-only: it is sent during create
or explicit password change, but the API never returns it in GET/PATCH responses for
security reasons. The idempotency check must never compare password fields.

### Field Handling

```
AnsibleUser.password: Optional[str]     ← User can provide on create or change
APIUser_v1.password: Optional[str]      ← Sent to API on create/patch
API GET response                         ← Never includes password (dropped by API)
AnsibleUser (from_api)                  ← password is NOT populated (always None)
```

### Forward Transform: `from_ansible_data`

```python
def from_ansible_data(self, ansible_instance, context):
    params = {}

    for field in ['username', 'email', 'first_name', 'last_name',
                  'is_superuser', 'is_platform_auditor']:
        val = getattr(ansible_instance, field, None)
        if val is not None:
            params[field] = val

    # CRITICAL: Only send password on create or if explicitly changing
    if context.operation in ('create', 'password_change'):
        if ansible_instance.password:
            params['password'] = ansible_instance.password
    # On update/merge, never send password unless we're doing a password change
    elif context.operation == 'update':
        # If user provided a password, this is an explicit password change
        if ansible_instance.password:
            params['password'] = ansible_instance.password
        # Otherwise, omit password from PATCH

    return APIUser_v1(**params)
```

### Reverse Transform: `from_api`

```python
def from_api(self, api_data, context):
    return AnsibleUser(
        id=api_data.get('id'),
        username=api_data.get('username'),
        email=api_data.get('email'),
        first_name=api_data.get('first_name'),
        last_name=api_data.get('last_name'),
        is_superuser=api_data.get('is_superuser'),
        is_platform_auditor=api_data.get('is_platform_auditor'),
        organizations=org_names,
        # NOTE: password is NEVER populated from API response
        # Even if api_data contained it (it won't), we don't expose it
        password=None,
    )
```

### Idempotency with Write-Only Fields

The idempotency check must exclude write-only fields:

```python
def is_user_idempotent(desired: AnsibleUser, existing: AnsibleUser) -> bool:
    """Compare users, ignoring write-only fields like password."""
    # Compare all fields EXCEPT password
    fields_to_compare = [
        'username', 'email', 'first_name', 'last_name',
        'is_superuser', 'is_platform_auditor', 'organizations'
    ]
    for field in fields_to_compare:
        if getattr(desired, field) != getattr(existing, field):
            return False
    # Password is never compared — it's write-only
    return True
```

### Scenario: Password Change Only

User wants to change password without changing other fields:

```yaml
- name: Change user password
  ansible.platform.user:
    username: alice
    password: "new_password_123"
    state: present
```

The action plugin:
1. Finds alice in the system.
2. Detects that only `password` changed (other fields match).
3. Sends a PATCH with `{ "password": "new_password_123" }`.
4. Returns `changed: true` even though no other fields differed.

---

## SECTION 10: Write-Only Fields Pattern

Write-only fields are commonly used for sensitive data. The collection handles them
with a specific pattern to maintain idempotency and security.

### Definition

A **write-only field** is one that:
- The user can provide during resource creation or modification.
- The API accepts and stores (in a hashed or secured form).
- The API **never returns** in GET/PATCH responses.
- Should never be included in idempotency comparisons.

### Common Write-Only Fields

| Field | Resource | Why Write-Only |
|-------|----------|---|
| `password` | `user` | Security: API stores hashed, never returns |
| `api_key` | `token` | Security: Only returned once, on creation |
| `secret` | `oauth_app` | Security: Never returned after creation |
| `pem_certificate` | `cert` | Security: May be sensitive key material |

### Implementation Rules

1. **In Ansible model:** Include as `Optional[str] = None`, documented as write-only.
2. **In API model:** Include the same way (API accepts it on POST/PATCH).
3. **In reverse transform (`from_api`):** Always set to `None` — never copy from API response.
4. **In action plugin:** Never compare write-only fields during idempotency checks.
5. **In module documentation:** Clearly mark as write-only in DOCUMENTATION.

### Code Pattern

```python
# Ansible model
@dataclass
class AnsibleUser:
    username: str
    password: Optional[str] = None  # write-only

# Reverse transform
def from_api(self, api_data, context):
    return AnsibleUser(
        username=api_data['username'],
        # ... other fields ...
        password=None,  # Never populated from API
    )

# Idempotency check in action plugin
def is_idempotent(desired, existing):
    # Compare all fields except password
    for field in ['username', 'email', 'first_name']:
        if getattr(desired, field) != getattr(existing, field):
            return False
    # password is never compared
    return True
```

### User Experience

When a user provides a password:

```yaml
- name: Create user
  ansible.platform.user:
    username: alice
    password: initial_password
    state: present
```

The first run reports `changed: true` and creates the user. A second run without
changing password still returns `changed: false` (password is not re-compared).

---

## SECTION 11: Fields to Null on Update Pattern

When a resource has conditional fields (fields whose validity depends on another field's value),
changing the condition often requires explicitly nulling the conditional fields in the API
request. This pattern handles that scenario.

### When to Use This Pattern

Use `get_fields_to_null_for_update()` when:
- A field's validity depends on another field's value.
- The API requires explicit null (`""` or `null`) to clear dependent fields.
- Changing the controlling field should automatically null out old dependent fields.

### Example: Authenticator Map

```
map_type: "saml"
├── saml_entity_id: "https://example.com/saml"
├── saml_metadata_url: "https://example.com/saml/metadata"
└── saml_cert: "-----BEGIN CERTIFICATE-----"

map_type: "ldap"
├── ldap_server: "ldap.example.com"
├── ldap_user_dn: "cn=admin,dc=example,dc=com"
└── ldap_password: "secret"
```

When changing from SAML to LDAP, the API must receive explicit nulls for SAML fields,
otherwise they persist and cause validation errors.

### Implementation Checklist

- [ ] Define `get_fields_to_null_for_update()` in the mixin.
- [ ] Call it in `from_ansible_data()` before building the API payload.
- [ ] Return a list of field names to null (strings).
- [ ] In the payload, set those fields to `""` (empty string).
- [ ] Document in module DOCUMENTATION which transitions cause null-outs.
- [ ] Test the transition in molecule scenarios.

### Testing Transitions

```python
def test_saml_to_ldap_transition():
    # Given existing SAML config
    existing = {
        'map_type': 'saml',
        'saml_entity_id': 'https://example.com/saml',
    }
    
    # When user changes to LDAP
    desired = AnsibleAuthenticatorMap(
        name="sso",
        map_type="ldap",
        ldap_server="ldap.example.com",
    )
    
    # Then the PATCH payload must null out SAML fields
    api_payload = mixin.from_ansible_data(desired, context)
    assert api_payload.saml_entity_id == ""
    assert api_payload.ldap_server == "ldap.example.com"
```

---

## SECTION 12: Backward-Compatible Flat Keys

The action plugin spreads `**validated_output` into the result dict so that 2.x test suites
that expect flat key access (`result.username`) continue to work alongside the nested
`result.user.username` format.

### The Problem

A module like `ansible.platform.user` can return the user resource. Over time, the module
may restructure to nest the user object:

**Old format (2.x tests expect this):**
```python
result = {
    'user': {
        'username': 'alice',
        'email': 'alice@example.com',
        'id': 123,
    }
}
```

**But tests access it as:**
```python
assert result['user']['username'] == 'alice'
```

When refactoring to a flatter output, **we must not break those tests**.

### Solution: Flatten in Action Plugin

The action plugin flattens the user object into the result dict:

```python
class ActionModule(BaseResourceActionPlugin):
    def run(self, tmp=None, task_vars=None):
        # ... do work ...
        result = super().run(tmp, task_vars)
        
        # Get the nested user object
        user_obj = result.get('user')
        
        # Flatten for backward compatibility
        if user_obj:
            result.update(user_obj)  # Spreads user.username → username, etc.
        
        return result
```

Now the result dict has **both** formats:
```python
result = {
    'user': {
        'username': 'alice',
        'email': 'alice@example.com',
    },
    'username': 'alice',         # ← backward compat
    'email': 'alice@example.com', # ← backward compat
}
```

### Test Compatibility

Old tests written against 2.x can still use flat keys:
```python
assert result['username'] == 'alice'  # Still works
```

New tests can use the nested format:
```python
assert result['user']['username'] == 'alice'  # Also works
```

### When to Use This Pattern

- **Major version boundaries.** When restructuring module output for v3.
- **Long-lived collections.** When backward compatibility is critical.
- **Large test suites.** When migrating tests gradually.

---

## SECTION 13: The TransformContext Object

The context object is passed to both `from_ansible_data` and `from_api`. It provides
access to the manager process for operations that require additional API calls (like
name-to-ID lookups), and communicates operational state like check_mode.

### Context Definition

```python
@dataclass
class TransformContext:
    manager: PlatformService   # the live manager instance
    operation: str             # 'create', 'update', 'delete', 'find', 'enforced'
    api_version: str           # e.g. '1'
    check_mode: bool = False   # if True, no mutations allowed
```

### Manager Reference

The manager reference allows the mixin to call methods for secondary operations:

```python
# Name-to-ID lookup
cluster_id = context.manager.lookup_resource_id(
    'service_cluster',
    cluster_name
)

# ID-to-name lookup
cluster_name = context.manager.lookup_resource_name(
    'service_cluster',
    cluster_id
)

# Execute secondary operations
orgs = context.manager.execute(
    'list', 'organization', {'filter': 'name=Red Hat'}
)
```

### Operation Field

Tells the mixin what operation is being performed:

| Operation | Context | Behavior |
|-----------|---------|----------|
| `'create'` | Creating new resource | Can use default field values; don't worry about existing state |
| `'update'` | Updating existing resource | May need to compare old vs. new; conditional logic applies |
| `'delete'` | Deleting resource | Only used in reverse (`from_api`); metadata only |
| `'find'` | Searching for resource | Reverse transform only; used to match against user query |
| `'enforced'` | Replacing entire resource | May need to null out fields |

### Check Mode

When `context.check_mode == True`, the mixin must NOT perform any mutations that would
affect external systems (like calling `context.manager.lookup_resource_id()` if it
makes API calls). However, most transformations are safe:

```python
def from_ansible_data(self, ansible_instance, context):
    params = {}
    
    # Safe: just copying fields
    params['name'] = ansible_instance.name
    
    # Potentially unsafe in check_mode if lookup makes API calls
    if context.check_mode:
        # In check_mode, don't resolve names to IDs (may fail if API unavailable)
        # Or cache lookups if possible
        params['cluster_id'] = ansible_instance.service_cluster  # Use name as proxy
    else:
        # Normal path: resolve names to IDs
        cluster_id = context.manager.lookup_resource_id(
            'service_cluster', ansible_instance.service_cluster
        )
        params['cluster_id'] = cluster_id
    
    return APIServiceNode_v1(**params)
```

---

## SECTION 14: Agent Automation Boundary

The three-tier pattern defines where AI-assisted code generation is safe to automate:

| Layer | Generated from | Human review needed? | Rationale |
|-------|----------------|---------------------|-----------|
| `AnsibleFoo` dataclass | `DOCUMENTATION` string | No — mechanical mapping | Field names and types are declarative |
| `APIFoo_vN` dataclass | OpenAPI spec / API docs | No — mechanical mapping | Generated from schema tools |
| `FooTransformMixin_vN` skeleton | Both above | **Minimal** — boilerplate | Class structure and imports |
| Endpoint operations map | API docs | Minimal — verify paths | Double-check HTTP method and path |
| `from_ansible_data` skeleton | DOCUMENTATION + API spec | **YES** — business logic | Field mappings; name-to-ID lookups |
| `from_api` skeleton | API spec + DOCUMENTATION | **YES** — business logic | ID-to-name lookups; write-only field handling |

### What Can Be Auto-Generated

1. **Dataclass structure** — Field names, types, defaults from schema.
2. **Endpoint paths and methods** — From OpenAPI spec.
3. **Boilerplate mixin class** — Imports, method signatures, docstrings.
4. **Simple 1:1 field mappings** — When Ansible name == API name.

### What Requires Human Review

1. **Field name normalization** — Choosing snake_case equivalents for camelCase API names.
2. **Name-to-ID resolution logic** — Which lookups are needed, how to handle failures.
3. **Conditional field logic** — When to send/exclude fields based on operation or state.
4. **Write-only field handling** — Which fields are write-only; ensuring they're never compared.
5. **`fields_to_null_for_update()` implementation** — Mapping field transitions to null-outs.
6. **Multi-endpoint orchestration** — Ordering, dependencies, batching.
7. **Edge cases and error handling** — Duplicate names, missing references, API quirks.

### Review Checklist

Before merging a transform mixin:

- [ ] All field names normalized (snake_case, descriptive).
- [ ] Name-to-ID and ID-to-name lookups implemented.
- [ ] Write-only fields handled correctly (never returned, never compared).
- [ ] Conditional field logic matches API requirements.
- [ ] `fields_to_null_for_update()` covers all transitions.
- [ ] Endpoint operations declared with correct methods and paths.
- [ ] Error messages are actionable (not generic "lookup failed").
- [ ] Tests cover the common paths: create, update, delete, find.
- [ ] Tests cover edge cases: missing references, name transitions, null-outs.

---

## Summary

The three-tier pattern — Ansible model, transform mixin, API model — isolates vendor-specific complexity from the user-facing interface. The Ansible model is stable across API versions. The transform mixin handles all business logic: field mapping, name-to-ID resolution, conditional fields, write-only fields, and null-outs. The API model mirrors the wire format exactly, enabling mechanical generation from OpenAPI specs.

**Key takeaways:**

1. **Users see stable, human-readable names.** The Ansible model never changes across API versions.
2. **The mixin is the human-in-the-loop boundary.** Generators can scaffold it, but business logic requires expert review.
3. **Idempotency is built-in.** The pattern enables finding existing resources by name, comparing state, and applying only necessary changes.
4. **Write-only fields stay hidden.** Passwords and secrets are handled securely, never exposed or compared.
5. **Conditional fields are orchestrated.** Changing a field that controls others automatically nulls dependent fields.

