# Developer Guide - Ansible Platform Collection

## Overview

This guide helps developers understand how to work with the Ansible Platform Collection codebase, add new resources, and contribute to the project.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Project Structure](#project-structure)
3. [Development Workflow](#development-workflow)
4. [Adding a New Resource](#adding-a-new-resource)
5. [Code Standards](#code-standards)
6. [Testing](#testing)
7. [Debugging](#debugging)

---

## Getting Started

### Prerequisites

- Python 3.11+
- Ansible Core 2.16.0+
- Access to Ansible Automation Platform Gateway (for testing)

### Setup

1. **Clone the repository**:
```bash
git clone https://github.com/ansible/ansible.platform.git
cd ansible.platform
```

2. **Create virtual environment**:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements/requirements_dev.txt
```

4. **Install collection in development mode**:
```bash
ansible-galaxy collection install -f .
```

---

## Project Structure

```
ansible.platform/
├── plugins/
│   ├── action/                    # Action plugins (new architecture)
│   │   ├── base_action.py         # Base class for all action plugins
│   │   └── user.py                # Example: User action plugin
│   │
│   ├── modules/                   # Legacy modules (old architecture)
│   │   └── user.py                # Legacy user module
│   │
│   └── plugin_utils/              # Shared utilities
│       ├── platform/              # Core platform components
│       │   ├── base_transform.py  # Universal transformation logic
│       │   ├── types.py           # Shared types
│       │   ├── registry.py        # Version registry
│       │   └── loader.py          # Dynamic class loader
│       │
│       ├── manager/               # Manager service
│       │   ├── platform_manager.py # Persistent service
│       │   └── rpc_client.py      # RPC client
│       │
│       ├── ansible_models/        # Ansible dataclasses (stable)
│       │   └── user.py            # AnsibleUser dataclass
│       │
│       ├── api/                   # API dataclasses (versioned)
│       │   └── v1/
│       │       ├── generated/     # Generated from OpenAPI
│       │       │   └── models.py
│       │       └── user.py        # Transform mixin
│       │
│       └── docs/                  # Module documentation
│           └── user.py            # DOCUMENTATION string
│
├── tools/
│   └── generators/                # Code generation tools
│       ├── generate_ansible_dataclasses.py
│       └── generate_api_models.sh
│
└── tests/
    ├── unit/                      # Unit tests
    └── integration/               # Integration tests
```

---

## Development Workflow

### 1. Understanding the Architecture

**Read First**:
- `docs/ARCHITECTURE.md` - System architecture
- `docs/IMPLEMENTATION_GUIDE.md` - Implementation details

**Key Concepts**:
- **Client Layer**: Action plugins (thin, stateless)
- **Manager Layer**: Persistent service (heavy, stateful)
- **Platform Layer**: Core framework (generic, reusable)
- **Data Models**: Type-safe dataclasses

### 2. Adding a New Resource

**Complete Workflow**:

1. **Write Documentation** (`plugins/plugin_utils/docs/{resource}.py`)
2. **Generate Ansible Dataclass** (automated)
3. **Generate API Models** (automated, if OpenAPI spec available)
4. **Create Transform Mixin** (manual - this is where you add value)
5. **Create Action Plugin** (mostly boilerplate)
6. **Write Tests** (unit and integration)
7. **Update Documentation** (user-facing docs)

**See**: `docs/IMPLEMENTATION_GUIDE.md` for detailed steps

### 3. Making Changes

**Before Making Changes**:
1. Read relevant documentation
2. Understand existing patterns
3. Check for similar implementations
4. Plan your approach

**During Development**:
1. Write code following standards
2. Add type hints
3. Write docstrings
4. Test locally
5. Run linters

**After Changes**:
1. Run tests
2. Update documentation
3. Create/update changelog fragment
4. Submit PR

---

## Adding a New Resource

### Quick Start

**Time Estimate**: 1-4 hours (depending on complexity)

**Steps**:

1. **Documentation** (15-30 min)
   - Create `plugins/plugin_utils/docs/{resource}.py`
   - Write DOCUMENTATION string
   - Define user-facing interface

2. **Generate Dataclasses** (1 min)
   - Run generator for Ansible dataclass
   - Run generator for API models (if spec available)

3. **Transform Mixin** (30 min - 2 hours)
   - Create `plugins/plugin_utils/api/v1/{resource}.py`
   - Define field mappings
   - Add transformations (if needed)
   - Define endpoint operations

4. **Action Plugin** (10 min)
   - Create `plugins/action/{resource}.py`
   - Inherit from BaseResourceActionPlugin
   - Implement run() method

5. **Tests** (15-30 min)
   - Write unit tests
   - Write integration test playbook

### Example: Adding "Team" Resource

#### Step 1: Documentation

**File**: `plugins/plugin_utils/docs/team.py`

```python
DOCUMENTATION = """
---
module: team
short_description: Manage platform teams
options:
  name:
    description: Team name
    required: true
    type: str
  organization:
    description: Organization name
    required: true
    type: str
  description:
    description: Team description
    type: str
  id:
    description: Team ID (read-only)
    type: int
"""
```

#### Step 2: Generate

```bash
python tools/generators/generate_ansible_dataclasses.py \
    plugins/plugin_utils/docs/team.py
```

#### Step 3: Transform Mixin

**File**: `plugins/plugin_utils/api/v1/team.py`

```python
from dataclasses import dataclass
from ..platform.base_transform import BaseTransformMixin
from ..platform.types import EndpointOperation
from .generated.models import Team as GeneratedAPITeam

class TeamTransformMixin_v1(BaseTransformMixin):
    _field_mapping = {
        'name': 'name',
        'description': 'description',
        'organization': {
            'api_field': 'organization_id',
            'forward_transform': 'org_name_to_id',
            'reverse_transform': 'org_id_to_name',
        }
    }
    
    _transform_registry = {
        'org_name_to_id': lambda name, ctx: ctx['manager'].lookup_org_ids([name])[0],
        'org_id_to_name': lambda id, ctx: ctx['manager'].lookup_org_names([id])[0],
    }
    
    @classmethod
    def get_endpoint_operations(cls):
        return {
            'create': EndpointOperation(
                path='/api/gateway/v1/teams/',
                method='POST',
                fields=['name', 'description', 'organization_id'],
                order=1
            ),
        }
    
    @classmethod
    def _get_api_class(cls):
        return APITeam_v1
    
    @classmethod
    def _get_ansible_class(cls):
        from ...ansible_models.team import AnsibleTeam
        return AnsibleTeam

@dataclass
class APITeam_v1(TeamTransformMixin_v1, GeneratedAPITeam):
    pass
```

#### Step 4: Action Plugin

**File**: `plugins/action/team.py`

```python
from ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible.platform.plugins.plugin_utils.docs.team import DOCUMENTATION
from ansible.platform.plugins.plugin_utils.ansible_models.team import AnsibleTeam

class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = 'team'
    
    def run(self, tmp=None, task_vars=None):
        super(ActionModule, self).run(tmp, task_vars)
        
        if task_vars is None:
            task_vars = {}
        
        args = self._task.args.copy()
        
        try:
            argspec = self._build_argspec_from_docs(DOCUMENTATION)
            validated_args = self._validate_data(args, argspec, 'input')
            
            manager = self._get_or_spawn_manager(task_vars)
            team_data = AnsibleTeam(**validated_args)
            
            operation = self._detect_operation(args)
            result_dict = manager.execute(operation, self.MODULE_NAME, team_data)
            
            validated_result = self._validate_data(result_dict, argspec, 'output')
            
            return {
                'failed': False,
                'changed': True,
                self.MODULE_NAME: validated_result
            }
        except Exception as e:
            return {'failed': True, 'msg': str(e)}
```

---

## Code Standards

### Type Hints

**Required**: All functions and methods must have type hints.

```python
def transform_data(
    self,
    data: Dict[str, Any],
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """Transform data using context."""
    ...
```

### Docstrings

**Required**: Google-style docstrings for all public functions.

```python
def execute_operation(
    self,
    operation: str,
    module_name: str,
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute an operation on a resource.
    
    Args:
        operation: Operation type ('create', 'update', 'delete', 'find')
        module_name: Module name (e.g., 'user', 'organization')
        data: Resource data as dict
    
    Returns:
        Result dict with operation results
    
    Raises:
        ValueError: If operation is unknown
        RuntimeError: If execution fails
    """
    ...
```

### Imports

**Organization**:
1. Standard library
2. Third-party
3. Local imports

```python
# Standard library
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

# Third-party
import requests

# Local
from ..platform.base_transform import BaseTransformMixin
from ..platform.types import EndpointOperation
```

### Error Handling

**Pattern**: Explicit error handling with informative messages.

```python
try:
    result = self._execute_api_call(url, data)
except requests.RequestException as e:
    logger.error(f"API call failed: {e}", exc_info=True)
    raise ValueError(f"Failed to create resource: {e}") from e
```

---

## Testing

### Unit Tests

**Location**: `tests/unit/`

**Purpose**: Test individual components in isolation.

**Example**:
```python
def test_forward_transform():
    """Test Ansible → API transformation."""
    ansible_user = AnsibleUser(
        username='test',
        organizations=['Org1', 'Org2']
    )
    
    mock_manager = MockManager()
    context = {'manager': mock_manager}
    
    api_user = ansible_user.to_api(context)
    
    assert api_user.username == 'test'
    assert api_user.organization_ids == [1, 2]
```

### Integration Tests

**Location**: `tests/integration/`

**Purpose**: Test end-to-end with real API.

**Example**:
```yaml
---
- name: Test User Management
  hosts: localhost
  vars:
    gateway_url: "{{ gateway_url }}"
    gateway_username: "{{ gateway_username }}"
    gateway_password: "{{ gateway_password }}"
  
  tasks:
    - name: Create user
      ansible.platform.user:
        username: test_user
        email: test@example.com
      register: result
    
    - name: Verify creation
      assert:
        that:
          - result is not failed
          - result.changed
          - result.user.username == 'test_user'
```

### Running Tests

```bash
# Unit tests
ansible-test units -v --docker default

# Integration tests
ansible-test integration -v --docker fedora42

# Specific test
ansible-test units -v --docker default tests/unit/test_user_transform.py
```

---

## Debugging

### Logging

**Enable Debug Logging**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Component-Specific Logging**:
```python
logger = logging.getLogger(__name__)
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

### Common Issues

#### Manager Connection Issues

**Symptoms**: Cannot connect to manager

**Debug Steps**:
1. Check socket file exists: `ls /tmp/ansible_platform/`
2. Check permissions: `ls -l /tmp/ansible_platform/`
3. Check manager process: `ps aux | grep platform_manager`
4. Review logs for connection errors

#### Transformation Issues

**Symptoms**: Data not transforming correctly

**Debug Steps**:
1. Verify `_field_mapping` is correct
2. Check transform functions are registered
3. Verify context contains required keys
4. Add debug logging in transform functions

#### Version Detection Issues

**Symptoms**: Wrong API version used

**Debug Steps**:
1. Check registry discovery: `registry.get_supported_versions()`
2. Verify version directory exists
3. Check module file exists in version directory
4. Review version detection logs

---

## Contributing

### Pull Request Process

1. **Create Feature Branch**: `git checkout -b feature/new-resource`
2. **Make Changes**: Follow code standards
3. **Write Tests**: Unit and integration tests
4. **Update Documentation**: User and developer docs
5. **Create Changelog**: Add fragment in `changelogs/fragments/`
6. **Submit PR**: Include description and test results

### Changelog Fragments

**Format**: `changelogs/fragments/{issue_number}-{description}.yml`

**Example**:
```yaml
---
changelog:
  - section: "minor_changes"
    entries:
      - entry: "Added support for team resource management"
        links:
          - url: "https://github.com/ansible/ansible.platform/issues/123"
            name: "ansible.platform#123"
```

---

## Resources

- **Architecture**: `docs/ARCHITECTURE.md`
- **Implementation**: `docs/IMPLEMENTATION_GUIDE.md`
- **API Reference**: `docs/API_REFERENCE.md`
- **Ansible Docs**: https://docs.ansible.com/

---

## Getting Help

- **Issues**: https://github.com/ansible/ansible.platform/issues
- **Discussions**: GitHub Discussions
- **Documentation**: `docs/` directory


