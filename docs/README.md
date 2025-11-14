# Ansible Platform Collection - Documentation

## Overview

This directory contains comprehensive documentation for the Ansible Platform Collection architecture and implementation.

## Documentation Files

### For Understanding the System

1. **[ARCHITECTURE.md](ARCHITECTURE.md)** - Complete system architecture
   - High-level architecture diagrams
   - Component responsibilities
   - Data flow diagrams
   - Key design decisions
   - Migration from legacy architecture

2. **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** - Step-by-step implementation guide
   - Foundation components details
   - Adding new resources
   - Code generation
   - Testing
   - Troubleshooting

3. **[API_REFERENCE.md](API_REFERENCE.md)** - Complete API reference
   - All component APIs
   - Method signatures
   - Parameters and return values
   - Usage examples

### For Developers

4. **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - Developer workflow guide
   - Getting started
   - Project structure
   - Development workflow
   - Code standards
   - Testing and debugging

## Quick Start

### For New Developers

1. **Start Here**: Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand the system
2. **Implementation**: Read [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) for details
3. **Development**: Read [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) for workflow
4. **Reference**: Use [API_REFERENCE.md](API_REFERENCE.md) as needed

### For AI Agents

1. **Context Loading**: Read all documentation files in order:
   - ARCHITECTURE.md (system overview)
   - IMPLEMENTATION_GUIDE.md (implementation details)
   - API_REFERENCE.md (component APIs)
   - DEVELOPER_GUIDE.md (workflow patterns)

2. **Key Concepts to Understand**:
   - Manager-side transformations
   - Round-trip data contract
   - Generic manager pattern
   - Dynamic version management
   - Persistent connections

3. **When Helping Developers**:
   - Reference specific sections in documentation
   - Follow patterns from examples
   - Check API reference for method signatures
   - Verify against architecture principles

## Documentation Structure

```
docs/
├── README.md                 # This file
├── ARCHITECTURE.md           # System architecture
├── IMPLEMENTATION_GUIDE.md   # Implementation details
├── API_REFERENCE.md          # API documentation
└── DEVELOPER_GUIDE.md        # Developer workflow
```

## Key Architecture Principles

1. **Manager-Side Transformations**: All transformations happen in the persistent manager
2. **Round-Trip Data Contract**: Output format matches input format
3. **Generic Manager**: Resource-agnostic, works for all modules
4. **Dynamic Version Management**: Filesystem-based discovery
5. **Persistent Connections**: Reuse HTTP sessions across tasks

## Component Locations

- **Platform Components**: `plugins/plugin_utils/platform/`
- **Manager Components**: `plugins/plugin_utils/manager/`
- **Action Plugins**: `plugins/action/`
- **Data Models**: `plugins/plugin_utils/ansible_models/` and `plugins/plugin_utils/api/`
- **Documentation**: `plugins/plugin_utils/docs/`

## Related Resources

- **Collection README**: `README.md` (root directory)
- **Changelog**: `CHANGELOG.rst`
- **Requirements**: `requirements/requirements_dev.txt`
- **Tests**: `tests/`

## Contributing

When adding new features or components:

1. Update relevant documentation files
2. Add examples to implementation guide
3. Update API reference if adding new APIs
4. Add troubleshooting tips if common issues arise

## Questions?

- **Architecture Questions**: See [ARCHITECTURE.md](ARCHITECTURE.md)
- **Implementation Questions**: See [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)
- **API Questions**: See [API_REFERENCE.md](API_REFERENCE.md)
- **Development Questions**: See [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)


