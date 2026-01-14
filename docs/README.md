# Ansible Platform Collection - Documentation

## Overview

This directory contains comprehensive documentation for the Ansible Platform Collection architecture and implementation.

## Documentation Files

### Core Architecture Documentation

1. **[ARCHITECTURE.md](ARCHITECTURE.md)** - Complete system architecture
   - High-level architecture diagrams
   - Component responsibilities
   - Data flow diagrams
   - Key design decisions
   - Dual-mode connection support (standard vs experimental)

2. **[ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md)** - Visual architecture diagrams
   - High-level architecture diagrams
   - Component architecture
   - Data flow diagrams
   - Sequence diagrams

3. **[FLOW_EXPLANATION.md](FLOW_EXPLANATION.md)** - Detailed flow explanation
   - Complete request flow (step-by-step)
   - Component interactions
   - Data transformation flow
   - Version management

4. **[CODE_WALKTHROUGH.md](CODE_WALKTHROUGH.md)** - Detailed code walkthrough
   - Step-by-step execution flow with code snippets
   - Line-by-line explanation of user module execution
   - File locations and key functions
   - Debugging tips and code examples

### Developer Documentation

5. **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - Developer workflow guide
   - Getting started
   - Project structure
   - Development workflow
   - Code standards
   - Testing and debugging

6. **[API_REFERENCE.md](API_REFERENCE.md)** - Complete API reference
   - All component APIs
   - Method signatures
   - Parameters and return values
   - Usage examples

### Feature-Specific Documentation

7. **[CREDENTIAL_HANDLING.md](CREDENTIAL_HANDLING.md)** - Credential management architecture
   - Secure credential storage
   - Credential isolation per process/namespace
   - Token rotation and expiration
   - Security threat assessment

8. **[ERROR_TAXONOMY.md](ERROR_TAXONOMY.md)** - Error classification and retry logic
   - Error taxonomy (PlatformError, AuthenticationError, etc.)
   - Retry logic with exponential backoff
   - Error message formatting
   - Configurable retry settings

9. **[SOCKET_SECURITY_FIXES.md](SOCKET_SECURITY_FIXES.md)** - Socket security implementation
   - Socket directory permissions (0700)
   - User ID in socket paths
   - Security fixes for shared environments

10. **[DATACLASS_ARCHITECTURE.md](DATACLASS_ARCHITECTURE.md)** - Dataclass design
    - Ansible dataclasses vs API dataclasses
    - Type safety and validation
    - Data transformation patterns

11. **[MOCK_GATEWAY.md](MOCK_GATEWAY.md)** - Mock Gateway server for testing
    - Local HTTP server for API testing
    - Testing different API versions
    - Usage examples

12. **[TURBO_MODULE_COMPARISON.md](TURBO_MODULE_COMPARISON.md)** - Comparison with Ansible Turbo Module
    - Architecture comparison
    - Use case analysis
    - Decision rationale

13. **[PROPOSAL_IMPLEMENTATION_MAPPING.md](PROPOSAL_IMPLEMENTATION_MAPPING.md)** - Detailed mapping of proposal to POC code
    - Code snippets for each proposal requirement
    - File locations and implementations
    - Step-by-step code walkthrough
    - Verification checklist

14. **[POC_IMPLEMENTATION_GUIDE.md](POC_IMPLEMENTATION_GUIDE.md)** - POC implementation guide
    - Architecture components overview
    - Code walkthrough
    - Quality tooling setup
    - Demo guide

15. **[DEMO_GUIDE.md](DEMO_GUIDE.md)** - Step-by-step demo guide
    - Demo scripts and examples
    - Presentation tips
    - Troubleshooting

16. **[STANDARD_MODE_IMPLEMENTATION.md](STANDARD_MODE_IMPLEMENTATION.md)** - Standard mode implementation details
    - How proposal features work in DirectHTTPClient
    - Code flow diagrams
    - File locations and line numbers
    - Verification examples

17. **[API_VERSION_DISCOVERY_AND_CLASS_LOADING.md](API_VERSION_DISCOVERY_AND_CLASS_LOADING.md)** - Complete flow of API version discovery and dynamic class loading
    - How APIVersionRegistry discovers versions from filesystem
    - How DynamicClassLoader uses registry to load classes
    - Step-by-step execution flow with code examples
    - Real-world examples and scenarios

18. **[SERIALIZATION_DESERIALIZATION_STANDARD_MODE.md](SERIALIZATION_DESERIALIZATION_STANDARD_MODE.md)** - Serialization and deserialization in standard mode
    - Complete flow from Ansible input to API request and back
    - How transform mixins handle data transformation
    - JSON serialization/deserialization with requests library
    - Complex transformations (e.g., organizations names ↔ IDs)
    - Comparison with experimental mode

19. **[AUTH_PARAMS_VALIDATION.md](AUTH_PARAMS_VALIDATION.md)** - Authentication parameters and validation
    - Why auth params are not in module DOCUMENTATION
    - How documentation fragments work
    - Why auth params are excluded from module validation
    - How auth params are handled separately for connection configuration

20. **[ADDING_NEW_API_VERSION.md](ADDING_NEW_API_VERSION.md)** - Adding a new API version explained
    - What "No changes required to existing v1 code or action plugins" means
    - Why action plugins are version-agnostic
    - How automatic version discovery works
    - Step-by-step example of adding v2 support

## Quick Start

### For New Developers

1. **Start Here**: Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand the system
2. **Visual Overview**: Review [ARCHITECTURE_DIAGRAMS.md](ARCHITECTURE_DIAGRAMS.md) for visual diagrams
3. **Flow Overview**: Read [FLOW_EXPLANATION.md](FLOW_EXPLANATION.md) for high-level flow
4. **Code Details**: Read [CODE_WALKTHROUGH.md](CODE_WALKTHROUGH.md) for detailed step-by-step execution
5. **Development**: Read [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) for workflow
6. **Reference**: Use [API_REFERENCE.md](API_REFERENCE.md) as needed

### For AI Agents

1. **Context Loading**: Read all documentation files in order:
   - ARCHITECTURE.md (system overview)
   - ARCHITECTURE_DIAGRAMS.md (visual diagrams)
   - FLOW_EXPLANATION.md (high-level flow)
   - CODE_WALKTHROUGH.md (detailed step-by-step execution with code)
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
├── README.md                    # This file
├── ARCHITECTURE.md              # System architecture
├── ARCHITECTURE_DIAGRAMS.md     # Visual architecture diagrams
├── FLOW_EXPLANATION.md          # High-level flow explanation
├── CODE_WALKTHROUGH.md          # Detailed step-by-step code walkthrough
├── API_REFERENCE.md             # API documentation
├── DEVELOPER_GUIDE.md           # Developer workflow
├── CREDENTIAL_HANDLING.md       # Credential management
├── ERROR_TAXONOMY.md            # Error classification and retry logic
├── SOCKET_SECURITY_FIXES.md     # Socket security implementation
├── DATACLASS_ARCHITECTURE.md    # Dataclass design
├── MOCK_GATEWAY.md              # Mock Gateway server for testing
├── TURBO_MODULE_COMPARISON.md   # Comparison with Ansible Turbo Module
├── DOCUMENTATION_INDEX.md       # Complete documentation index
└── reusables/                   # Reusable documentation fragments
    └── variables.md
```

## Key Architecture Principles

1. **Dual-Mode Connections**: Support for both standard (direct HTTP) and experimental (persistent manager) modes
2. **Manager-Side Transformations**: All transformations happen in the connection layer (manager or direct client)
3. **Round-Trip Data Contract**: Output format matches input format
4. **Generic Manager**: Resource-agnostic, works for all modules
5. **Dynamic Version Management**: Filesystem-based API version discovery
6. **Shared Layers**: Both connection modes use the same layers (version detection, error handling, credentials, CRUD)

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
- **Flow Questions**: See [FLOW_EXPLANATION.md](FLOW_EXPLANATION.md) or [CODE_WALKTHROUGH.md](CODE_WALKTHROUGH.md)
- **API Questions**: See [API_REFERENCE.md](API_REFERENCE.md)
- **Development Questions**: See [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
- **Credential Questions**: See [CREDENTIAL_HANDLING.md](CREDENTIAL_HANDLING.md)
- **Error Handling Questions**: See [ERROR_TAXONOMY.md](ERROR_TAXONOMY.md)
- **Complete Index**: See [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) for all documentation

## Related Resources

- **Refactoring Plan**: `../REFACTORING_PLAN.md` - Dual-mode connection refactoring plan
- **Refactoring Summary**: `../REFACTORING_SUMMARY.md` - Refactoring implementation summary
- **Collection README**: `../README.md` - Main collection README
- **Changelog**: `../CHANGELOG.rst` - Collection changelog
- **Requirements**: `../requirements/requirements_dev.txt` - Development requirements
- **Tests**: `../tests/` - Test suite


