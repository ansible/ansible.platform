# Dataclass Architecture Explained

This document explains the three types of dataclasses in the platform collection and why we have this architecture.

## The Three Dataclass Types

### 1. AnsibleUser (Ansible Dataclass) - Stable Interface

**Location**: `plugins/plugin_utils/ansible_models/user.py`

**What it is**:
- **User-facing, stable interface** that playbooks interact with
- **Version-agnostic** - field names and types remain consistent across API versions
- Represents the **Ansible format** (what users see in playbooks)

**Example**:
```python
@dataclass
class AnsibleUser:
    username: str
    email: Optional[str] = None
    organizations: Optional[List[str]] = None  # Names, not IDs!
    # ... other fields
```

**Key Characteristics**:
- ✅ **Stable**: Field names don't change when API version changes
- ✅ **User-friendly**: Uses names (e.g., `organizations=['Engineering']`) not IDs
- ✅ **Action plugin uses this**: Created in `action/user.py:117`
- ❌ **NOT version-specific**: Same structure for all API versions

**Where it's used**:
- Action plugin creates `AnsibleUser` from playbook input
- Manager receives `AnsibleUser` (as dict via RPC)
- Manager reconstructs `AnsibleUser` instance
- Manager transforms it to API format

### 2. APIUser_v1 (API Dataclass) - Version-Specific

**Location**: `plugins/plugin_utils/api/v1/user.py`

**What it is**:
- **API-facing, version-specific** dataclass
- Represents the **exact format** the API expects
- **Versioned**: Different structure for v1, v2, etc.

**Example**:
```python
@dataclass
class APIUser_v1(BaseTransformMixin):
    username: str
    email: Optional[str] = None
    organization_ids: Optional[List[int]] = None  # IDs, not names!
    # ... other fields
```

**Key Characteristics**:
- ✅ **Version-specific**: `APIUser_v1` for API v1, `APIUser_v2` for API v2, etc.
- ✅ **API format**: Matches exactly what the API expects
- ✅ **Uses IDs**: `organization_ids=[1, 2]` not names
- ❌ **NOT used in action plugin**: Only used in manager

**Where it's used**:
- Manager transforms `AnsibleUser` → `APIUser_v1`
- Manager sends `APIUser_v1` to API endpoints
- Manager receives `APIUser_v1` from API responses
- Manager transforms `APIUser_v1` → `AnsibleUser` (dict)

### 3. UserTransformMixin_v1 (Transform Mixin) - The Bridge

**Location**: `plugins/plugin_utils/api/v1/user.py`

**What it is**:
- **Transformation logic** that converts between Ansible and API formats
- **Version-specific**: Each API version has its own mixin
- Defines field mappings and transformations

**Example**:
```python
class UserTransformMixin_v1(BaseTransformMixin):
    _field_mapping = {
        'username': 'username',  # 1:1 mapping
        'organizations': {       # Complex mapping
            'api_field': 'organization_ids',
            'forward_transform': 'names_to_ids',  # Ansible → API
            'reverse_transform': 'ids_to_names',  # API → Ansible
        }
    }
    
    @classmethod
    def from_ansible_data(cls, ansible_instance, context):
        # Convert AnsibleUser → APIUser_v1
        # Handles: organizations=['Engineering'] → organization_ids=[1]
        # context is TransformContext dataclass (type-safe, not dict)
```

**Key Characteristics**:
- ✅ **Version-specific**: `UserTransformMixin_v1` for v1, `UserTransformMixin_v2` for v2
- ✅ **Transformation logic**: Knows how to convert formats
- ✅ **Context-aware**: Can access manager for lookups (names ↔ IDs)
- ✅ **Type-safe context**: Uses `TransformContext` dataclass (not dict) for better mypy support
- ❌ **NOT a dataclass**: It's a mixin class with methods

**Where it's used**:
- Manager loads version-specific mixin based on detected API version
- Manager calls `mixin.from_ansible_data()` to transform Ansible → API
- Manager calls `mixin.from_api()` to transform API → Ansible

## Why This Architecture?

### Problem: API Versions Change

When the platform API changes from v1 to v2:
- Field names might change: `first_name` → `given_name`
- Field types might change: `organizations` (list) → `org_memberships` (dict)
- Endpoints might change: `/api/gateway/v1/users/` → `/api/gateway/v2/users/`

### Solution: Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────┐
│ ACTION PLUGIN (action/user.py)                         │
│                                                         │
│ Uses: AnsibleUser (stable, version-agnostic)          │
│                                                         │
│ user = AnsibleUser(username='jdoe',                    │
│                    organizations=['Engineering'])      │
└───────────────────────┬─────────────────────────────────┘
                        │
                        │ RPC (dict)
                        ▼
┌─────────────────────────────────────────────────────────┐
│ MANAGER (platform_manager.py)                          │
│                                                         │
│ 1. Loads version-specific classes:                     │
│    - AnsibleUser (from ansible_models/)                │
│    - APIUser_v1 (from api/v1/)                        │
│    - UserTransformMixin_v1 (from api/v1/)             │
│                                                         │
│ 2. Reconstructs: AnsibleUser(**dict)                   │
│                                                         │
│ 3. Transforms: AnsibleUser → APIUser_v1                │
│    via UserTransformMixin_v1.from_ansible_data()       │
│                                                         │
│ 4. Sends: APIUser_v1 to API                           │
│                                                         │
│ 5. Receives: APIUser_v1 from API                      │
│                                                         │
│ 6. Transforms: APIUser_v1 → AnsibleUser (dict)        │
│    via UserTransformMixin_v1.from_api()               │
└───────────────────────┬─────────────────────────────────┘
                        │
                        │ HTTP/HTTPS
                        ▼
┌─────────────────────────────────────────────────────────┐
│ PLATFORM API (Gateway)                                  │
│                                                         │
│ Receives: APIUser_v1 format                            │
│ {username: 'jdoe', organization_ids: [1]}              │
└─────────────────────────────────────────────────────────┘
```

## Answering Your Questions

### Q1: What is "Ansible dataclass"?

**Answer**: `AnsibleUser` is the **stable, user-facing dataclass** that:
- Represents data in **Ansible format** (what playbooks use)
- Is **version-agnostic** (same structure regardless of API version)
- Uses **user-friendly formats** (names instead of IDs)
- Is created in the **action plugin** (`action/user.py:117`)

**Example**:
```python
# In action/user.py:117
user = AnsibleUser(
    username='jdoe',
    email='jdoe@example.com',
    organizations=['Engineering', 'DevOps']  # Names, not IDs!
)
```

### Q2: What do we do in transform mixin?

**Answer**: The transform mixin (`UserTransformMixin_v1`) **converts between formats**:

1. **Forward Transform** (Ansible → API):
   ```python
   # Input: AnsibleUser(organizations=['Engineering'])
   # Output: APIUser_v1(organization_ids=[1])
   
   UserTransformMixin_v1.from_ansible_data(ansible_user, context)
   ```
   - Maps fields: `username` → `username` (1:1)
   - Transforms: `organizations=['Engineering']` → `organization_ids=[1]` (lookup)
   - Returns: `APIUser_v1` instance

2. **Reverse Transform** (API → Ansible):
   ```python
   # Input: APIUser_v1(organization_ids=[1, 2])
   # Output: {'organizations': ['Engineering', 'DevOps']}
   
   UserTransformMixin_v1.from_api(api_user_dict, context)
   ```
   - Maps fields: `organization_ids` → `organizations`
   - Transforms: `organization_ids=[1, 2]` → `organizations=['Engineering', 'DevOps']` (lookup)
   - Returns: Dict in Ansible format

### Q3: Aren't we supposed to have dataclass models based on API version?

**Answer**: **YES! We DO have version-specific dataclasses!** But they're used in the **manager**, not the action plugin.

**The Architecture**:

1. **Action Plugin** (version-agnostic):
   - Uses `AnsibleUser` (stable, never changes)
   - Doesn't know about API versions
   - Creates `AnsibleUser` from playbook input

2. **Manager** (version-aware):
   - Loads version-specific classes dynamically:
     ```python
     # In platform_manager.py:224-227
     AnsibleClass, APIClass, MixinClass = self.loader.load_classes_for_module(
         module_name,
         self.api_version  # e.g., '1' → loads APIUser_v1, UserTransformMixin_v1
     )
     ```
   - Uses `APIUser_v1` for API v1, `APIUser_v2` for API v2, etc.
   - Uses `UserTransformMixin_v1` for v1, `UserTransformMixin_v2` for v2, etc.

**Directory Structure**:
```
plugins/plugin_utils/
├── ansible_models/
│   └── user.py              # AnsibleUser (stable, version-agnostic)
│
└── api/
    ├── v1/
    │   └── user.py          # APIUser_v1 + UserTransformMixin_v1
    └── v2/
        └── user.py          # APIUser_v2 + UserTransformMixin_v2 (future)
```

## Complete Flow Example

### Step 1: Action Plugin Creates AnsibleUser
```python
# action/user.py:117
user = AnsibleUser(
    username='jdoe',
    organizations=['Engineering', 'DevOps']  # Names!
)
```

### Step 2: Manager Loads Version-Specific Classes
```python
# platform_manager.py:224-227
AnsibleClass, APIClass, MixinClass = self.loader.load_classes_for_module(
    'user',
    '1'  # Detected API version
)
# Returns: (AnsibleUser, APIUser_v1, UserTransformMixin_v1)
```

### Step 3: Manager Transforms Ansible → API
```python
# platform_manager.py:293
api_data = ansible_user.to_api(context)
# Calls: UserTransformMixin_v1.from_ansible_data(ansible_user, context)
# Returns: APIUser_v1(organization_ids=[1, 2])  # IDs!
```

### Step 4: Manager Sends to API
```python
# Uses APIUser_v1 format
POST /api/gateway/v1/users/
{
    "username": "jdoe",
    "organization_ids": [1, 2]  # API format
}
```

### Step 5: Manager Receives from API
```python
# Receives APIUser_v1 format
{
    "id": 123,
    "username": "jdoe",
    "organization_ids": [1, 2]
}
```

### Step 6: Manager Transforms API → Ansible
```python
# platform_manager.py:307
ansible_result = mixin_class.from_api(api_result, context)
# Calls: UserTransformMixin_v1.from_api(api_result, context)
# Returns: {'organizations': ['Engineering', 'DevOps']}  # Names!
```

## Summary

| Component | Type | Version-Specific? | Where Used |
|-----------|------|-------------------|------------|
| `AnsibleUser` | Ansible dataclass | ❌ No (stable) | Action plugin |
| `APIUser_v1` | API dataclass | ✅ Yes (v1) | Manager |
| `APIUser_v2` | API dataclass | ✅ Yes (v2) | Manager (future) |
| `UserTransformMixin_v1` | Transform mixin | ✅ Yes (v1) | Manager |
| `UserTransformMixin_v2` | Transform mixin | ✅ Yes (v2) | Manager (future) |

**Key Insight**: 
- Action plugin is **version-agnostic** (uses stable `AnsibleUser`)
- Manager is **version-aware** (loads version-specific `APIUser_v1` and `UserTransformMixin_v1`)
- Transform mixin **bridges** the gap between stable Ansible format and version-specific API format

