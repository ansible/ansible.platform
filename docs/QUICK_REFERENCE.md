# Quick Reference - Ansible Platform Collection

## For AI Agents

This document provides quick reference for AI agents working with the Ansible Platform Collection. Read this first to get immediate context.

## System Overview

**Architecture**: Client-Manager pattern with persistent service
- **Client**: Action plugins (thin, stateless)
- **Manager**: Persistent service (heavy, stateful)
- **Communication**: RPC over Unix socket
- **Transformations**: All in manager, not client

## Key Files and Locations

### Foundation Components

| Component | Location | Purpose |
|-----------|----------|---------|
| BaseTransformMixin | `plugins/plugin_utils/platform/base_transform.py` | Universal transformation logic |
| APIVersionRegistry | `plugins/plugin_utils/platform/registry.py` | Version discovery |
| DynamicClassLoader | `plugins/plugin_utils/platform/loader.py` | Runtime class loading |
| EndpointOperation | `plugins/plugin_utils/platform/types.py` | API endpoint config |
| PlatformService | `plugins/plugin_utils/manager/platform_manager.py` | Persistent service |
| ManagerRPCClient | `plugins/plugin_utils/manager/rpc_client.py` | RPC client |
| BaseResourceActionPlugin | `plugins/action/base_action.py` | Base action plugin |

### Data Models

| Type | Location | Purpose |
|------|----------|---------|
| Ansible Dataclasses | `plugins/plugin_utils/ansible_models/` | User-facing (stable) |
| API Dataclasses | `plugins/plugin_utils/api/v1/generated/` | API models (generated) |
| Transform Mixins | `plugins/plugin_utils/api/v1/` | Transformation logic |
| Documentation | `plugins/plugin_utils/docs/` | DOCUMENTATION strings |

## Key Concepts

### 1. Manager-Side Transformations

**All transformations happen in the manager, not the client.**

- Client sends Ansible dataclass to manager
- Manager transforms to API format
- Manager calls API
- Manager transforms back to Ansible format
- Client receives Ansible dataclass

### 2. Round-Trip Data Contract

**Output format matches input format.**

- Input: `organizations=['Engineering']` (names)
- Output: `organizations=['Engineering']` (names, not IDs)
- API format (`organization_ids=[1]`) is internal to manager

### 3. Generic Manager

**Manager is resource-agnostic.**

- One manager works for all resources
- Resource logic in dataclass mixins
- Manager just orchestrates

### 4. Dynamic Version Management

**Filesystem-based discovery.**

- Scan `api/` directory for `v1/`, `v2/`, etc.
- Discover modules in each version
- Automatic fallback logic

### 5. Persistent Connections

**Manager maintains HTTP session across tasks.**

- First task spawns manager
- Subsequent tasks reuse same manager
- 50-75% faster execution

## Common Patterns

### Adding a New Resource

1. Write DOCUMENTATION (`plugins/plugin_utils/docs/{resource}.py`)
2. Generate Ansible dataclass (automated)
3. Generate API models (automated, if OpenAPI available)
4. Create transform mixin (`plugins/plugin_utils/api/v1/{resource}.py`)
5. Create action plugin (`plugins/action/{resource}.py`)
6. Write tests

### Transform Mixin Pattern

```python
class ResourceTransformMixin_v1(BaseTransformMixin):
    _field_mapping = {
        'simple_field': 'simple_field',  # 1:1 mapping
        'complex_field': {                # Complex mapping
            'api_field': 'api_field_name',
            'forward_transform': 'transform_func',
            'reverse_transform': 'reverse_transform_func',
        }
    }
    
    _transform_registry = {
        'transform_func': lambda value, ctx: ctx['manager'].helper(value),
    }
    
    @classmethod
    def get_endpoint_operations(cls):
        return {
            'create': EndpointOperation(...),
        }
```

### Action Plugin Pattern

```python
class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = 'resource'
    
    def run(self, tmp=None, task_vars=None):
        # 1. Validate input
        argspec = self._build_argspec_from_docs(DOCUMENTATION)
        validated = self._validate_data(self._task.args, argspec, 'input')
        
        # 2. Get manager
        manager = self._get_or_spawn_manager(task_vars)
        
        # 3. Create dataclass
        resource_data = AnsibleResource(**validated)
        
        # 4. Execute
        operation = self._detect_operation(self._task.args)
        result = manager.execute(operation, self.MODULE_NAME, resource_data)
        
        # 5. Validate output
        validated_result = self._validate_data(result, argspec, 'output')
        
        # 6. Return
        return {'changed': True, 'failed': False, self.MODULE_NAME: validated_result}
```

## Data Flow

```
Playbook → Action Plugin → Manager (RPC) → Platform API
                ↓              ↓
         Validate Input   Transform (Ansible→API)
                ↓              ↓
         Create Dataclass  Execute API Call
                ↓              ↓
         Send to Manager   Transform (API→Ansible)
                ↓              ↓
         Receive Result    Return Ansible Dataclass
                ↓
         Validate Output
                ↓
         Return to Playbook
```

## Important Methods

### BaseTransformMixin
- `to_api(context)` - Transform Ansible → API
- `to_ansible(context)` - Transform API → Ansible

### PlatformService
- `execute(operation, module_name, ansible_data_dict)` - Main entry point

### BaseResourceActionPlugin
- `_get_or_spawn_manager(task_vars)` - Get or spawn manager
- `_validate_data(data, argspec, direction)` - Validate input/output
- `_build_argspec_from_docs(documentation)` - Parse DOCUMENTATION

## Common Issues and Solutions

### Manager Connection Issues
- Check socket file exists
- Verify authentication credentials
- Check manager process is running

### Transformation Issues
- Verify `_field_mapping` is correct
- Check transform functions are registered
- Verify context contains required keys

### Version Issues
- Verify version directory exists
- Check module file exists in version directory
- Review registry discovery logs

## Documentation Files

1. **ARCHITECTURE.md** - Complete system architecture
2. **IMPLEMENTATION_GUIDE.md** - Step-by-step implementation
3. **API_REFERENCE.md** - Component API reference
4. **DEVELOPER_GUIDE.md** - Developer workflow
5. **QUICK_REFERENCE.md** - This file

## When Helping Developers

1. **Understand the task**: What resource/module are they working on?
2. **Check existing patterns**: Look at similar implementations
3. **Reference documentation**: Point to specific sections
4. **Follow architecture**: Ensure changes align with principles
5. **Test thoroughly**: Verify changes work end-to-end

## Code Standards

- **Type hints**: Required on all functions
- **Docstrings**: Google-style for all public functions
- **Imports**: Standard library → Third-party → Local
- **Error handling**: Explicit with informative messages

## Testing

- **Unit tests**: `tests/unit/` - Test components in isolation
- **Integration tests**: `tests/integration/` - Test with real API
- **Run tests**: `ansible-test units -v --docker default`

---

**For detailed information, see the full documentation files in this directory.**


