# Data Model Transformation

> **Worked example**: [13-user-module-worked-example.md](13-user-module-worked-example.md)
> traces a complete `state: merged` user create through every tier with real data at
> each step. Read that first if you prefer concrete examples over abstract diagrams.

## The Three-Tier Data Flow

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

### Concrete Example: User Create (`state: merged`)

The same data as it appears at each tier for `ansible.platform.user`:

**Tier 1 — what the playbook author writes:**
```yaml
config:
  - username: "alice"
    email: "alice@example.com"
    first_name: "Alice"
    last_name: "Smith"
    password: "SecurePass123!"
    is_superuser: false
```
This becomes `AnsibleUser(username="alice", email="alice@example.com", ...)`

**Tier 1 → Tier 2 — `UserTransformMixin_v1.from_ansible_data()` output:**
```python
APIUser_v1(
    username="alice",
    email="alice@example.com",
    first_name="Alice",
    last_name="Smith",
    password="SecurePass123!",
    is_superuser=False,
    # None fields are NOT included in the HTTP body
)
# Serialised HTTP body:
# {"username":"alice","email":"alice@example.com","first_name":"Alice",
#  "last_name":"Smith","password":"SecurePass123!","is_superuser":false}
```

**Gateway API response (Tier 3 → Tier 2):**
```json
{
    "id": 42,
    "username": "alice",
    "email": "alice@example.com",
    "first_name": "Alice",
    "last_name": "Smith",
    "is_superuser": false,
    "url": "https://gateway.example.com/api/gateway/v1/users/42/",
    "created": "2025-06-01T10:00:00.000000Z",
    "modified": "2025-06-01T10:00:00.000000Z",
    "is_platform_auditor": false,
    "managed": false
}
```

**Tier 2 → Tier 1 — `UserTransformMixin_v1.from_api()` output:**
```python
AnsibleUser(
    id=42,
    username="alice",
    email="alice@example.com",
    first_name="Alice",
    last_name="Smith",
    password=None,         # ← API never returns passwords; field stays None
    is_superuser=False,
    url="https://gateway.example.com/api/gateway/v1/users/42/",
    created="2025-06-01T10:00:00.000000Z",
    modified="2025-06-01T10:00:00.000000Z",
    is_platform_auditor=False,
    managed=False,
)
```

**Final module output (`result.after[0]`):**
```yaml
id: 42
username: "alice"
email: "alice@example.com"
first_name: "Alice"
last_name: "Smith"
is_superuser: false
url: "https://gateway.example.com/api/gateway/v1/users/42/"
created: "2025-06-01T10:00:00.000000Z"
modified: "2025-06-01T10:00:00.000000Z"
is_platform_auditor: false
managed: false
```

## Tier 1: Ansible Model

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

### Example: `AnsibleUser`

```python
@dataclass
class AnsibleUser:
    username: str                           # required
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None
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

## Tier 2: API Model

The API model (`APIUser_v1`, `APIOrganization_v1`, etc.) defines the wire format for
a specific version of the Gateway API.

### Properties

- Defined as a Python `@dataclass` in `plugins/plugin_utils/api/v<N>/`.
- Field names match the Gateway API field names exactly (often different from Ansible names).
- Reference fields use the API's integer ID type (`int`), not names.
- One API model per resource per API version.

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

### Versioning

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

## The Transform Mixin

The transform mixin is where all the resource-specific business logic lives. It is the
**only** file a developer needs to write when adding support for a new API version.

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

## Case Study: Simple Resource — `organization`

The `organization` resource is a clean fit: every Ansible field maps directly to a
Gateway API field with the same name and same type.

```
AnsibleOrganization           APIOrganization_v1
─────────────────────         ──────────────────────
name: str                 →   name: str
description: Optional[str]→   description: Optional[str]
id: Optional[int]         ←   id: int  (read-only)
```

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

## Case Study: Reference Fields — `service_node`

The `service_node` resource has a `service_cluster` field that the user specifies by
**name** but the API expects an **ID**.

```
AnsibleServiceNode          APIServiceNode_v1
─────────────────────       ──────────────────────
name: str               →   name: str
address: str            →   address: str
service_cluster: str    →   service_cluster: int  ← name→ID resolution!
```

The transform mixin resolves the name to an ID:

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
```

### Idempotency with reference fields

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

## Case Study: List URI Fields — `application`

The `application` resource has fields that accept a list of URIs (redirect URIs,
post-logout URIs). The user provides them as a Python list; the API expects a
space-separated string.

```
AnsibleApplication                    APIApplication_v1
─────────────────────────────         ──────────────────────────────
redirect_uris: Optional[List[str]]→   redirect_uris: Optional[str]
                                       "https://a.com https://b.com"
```

The transform mixin joins and splits:

```python
def _join_uri_list(uris):
    if uris is None:
        return None
    if isinstance(uris, list):
        return " ".join(uris)
    return uris

def from_ansible_data(self, ansible_instance, context):
    return APIApplication_v1(
        redirect_uris=_join_uri_list(ansible_instance.redirect_uris),
        ...
    )
```

## The `TransformContext` Object

The context object is passed to both `from_ansible_data` and `from_api`. It provides
access to the manager process for operations that require additional API calls (like
name-to-ID lookups):

```python
@dataclass
class TransformContext:
    manager: PlatformService   # the live manager instance
    operation: str             # 'create', 'update', 'delete', 'find', 'enforced'
    api_version: str           # e.g. '1'
    check_mode: bool = False
```

The manager reference allows the mixin to call `context.manager.lookup_resource_id()`
to resolve names to IDs without making HTTP calls from the action plugin layer.

## Agent Automation Boundary

The three-tier pattern defines where AI-assisted code generation is safe to automate:

| Layer | Generated from | Human review needed? |
|-------|---------------|---------------------|
| `AnsibleFoo` dataclass | `DOCUMENTATION` string | No — mechanical mapping |
| `APIFoo_vN` dataclass | OpenAPI spec / API docs | No — mechanical mapping |
| `FooTransformMixin_vN` skeleton | Both above | **Yes** — business logic |
| Endpoint operations map | API docs | Minimal — verify paths |

The transform mixin is the human-in-the-loop boundary. Generators can produce the
skeleton and a first-pass implementation for simple 1:1 fields, but the developer must
review name-to-ID resolution, conditional field logic, and secondary operation ordering.
