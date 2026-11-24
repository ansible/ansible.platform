# The AAP API Landscape: Gateway, EDA, Controller

This document maps the three AAP services and their resource coverage to help you choose the right spec when adding new modules and avoid naming conflicts.

## Quick Reference

| Service | Resources | Scope | Example Module Names |
|---------|-----------|-------|---------------|
| **Gateway** | 48 | AAP platform management (users, orgs, services) | `user`, `settings` |
| **EDA** | 37 | Event-driven automation (projects, rulebooks, activations) | `eda_project`, `rulebook_activation` |
| **Controller** | 93 | Ansible Controller (inventories, credentials, jobs) | `controller_project`, `inventory` |

---

## Service-by-Service Breakdown

### 1. Gateway API (Automation Platform Gateway)

**Purpose**: Core AAP platform management

**Key Resources** (36 unique):
- Identity: `users`, `organizations`, `teams`
- Authentication: `authenticators`, `authenticator_maps`, `authenticator_users`
- Access Control: `role_definitions`, `role_user_assignments`, `role_team_assignments`
- Services: `services`, `service_clusters`, `service_types`, `service_keys`, `service_nodes`
- Platform Config: `http_ports`, `routes`, `ui_plugin_routes`, `settings`, `feature_flags`
- Security: `ca_certificates`, `tokens`
- Applications: `applications`
- Infrastructure: `activity_stream`, `status`, `ping`

**Gateway Module Coverage**: 22 modules. This is the Gateway subset of the
[collection inventory](README.md#collection-scope-and-module-inventory), not all
Gateway API resources or the full collection.

**Spec**: `../aap-openapi-specs/gateway.json` (125 endpoints)

---

### 2. EDA API (Event-Driven Ansible)

**Purpose**: Event-driven automation and rulebook management

**Key Resources** (37 unique):
- Projects: `projects` (rulebook repositories)
- Rulebooks: `rulebooks`, `audit_rules`
- Execution: `activations`, `activation_instances`
- Configuration: `decision_environments`, `event_streams`, `credential_types`, `eda_credentials`
- Shared: `organizations`, `users`, `teams` (inherit from Gateway auth)

**EDA Module Coverage**: `eda_project`, `eda_credential`, `eda_credential_type`,
`eda_credential_input_source`, `eda_controller_token`, `decision_environment`,
`event_stream`, `rulebook_activation`, and `rulebook_activation_copy`.

**Spec**: `../aap-openapi-specs/eda.json` (83 endpoints)

---

### 3. Controller API (Ansible Controller)

**Purpose**: Controller job execution and resource management

**Key Resources** (93 unique):
- Infrastructure: `inventories`, `hosts`, `groups`, `variables`
- Automation: `job_templates`, `workflow_job_templates`, `ad_hoc_commands`, `jobs`
- Credentials: `credentials`, `credential_types`, `credential_input_sources`
- Projects: `projects` (playbook repositories)
- Organizations: `organizations`, `teams`, `users`
- Authentication: `authenticators`, `authenticator_map`
- Access Control: `role_definitions`, `role_user_assignments`, `role_team_assignments`
- Platform configuration: `settings` (exposed as `controller_settings` to distinguish it from Gateway settings)
- More: `labels`, `schedules`, `notifications`, `webhook_receivers`, etc.

**Controller Module Coverage**: Includes inventories, hosts, groups, projects,
credentials, execution environments, job and workflow operations, schedules,
notifications, settings, and licensing. See the
[collection inventory](README.md#collection-scope-and-module-inventory) and
[module sources](../plugins/modules/) for the current surface.

**Spec**: `../aap-openapi-specs/controller.json` (2.1MB, most comprehensive)

---

## Resource Overlap & Naming Conflicts

### All Three Services (21 resources)
These resources exist in Gateway, EDA, AND Controller:
- `organizations`, `users`, `teams`
- `feature_flags_state`
- `role_definitions`, `role_user_assignments`, `role_team_assignments`
- `credentials` (different schemas per service)
- `config`, `metadata`, `status`

**Ownership**: Shared authentication does not make service resources interchangeable.
Check the owning API and schema before selecting a module or resolving an ID.

### EDA + Controller Only (2 resources)

| Resource | Status |
|----------|--------|
| **`projects`** | ⚠️ **CONFLICT** — EDA projects are rulebook repos, Controller projects are playbook repos |
| **`config`** | Shared configuration |

**Naming Rule**:
- EDA: `eda_project`
- Controller: `controller_project`

### Gateway + Controller Only (2 resources)
- `ping`, `settings`

**Action**: Gateway settings remains `settings`; Controller settings is exposed as
`controller_settings` because the collection provides separate service-specific
implementations and preserves the legacy Controller module interface.

---

## How to Choose Which Spec to Use

When adding a new module, determine which service owns the resource:

```
1. Is it a platform management feature (users, orgs, roles, services)?
   → Use Gateway API (gateway.json)

2. Is it event-driven automation (projects, rulebooks, activations)?
   → Use EDA API (eda.json)

3. Is it Controller-specific (inventories, jobs, playbook projects)?
   → Use Controller API (controller.json)

4. Is the resource name used by multiple services?
   → Apply naming conflict checklist (see docs/07-adding-resources.md)
```

---

## Future-Proofing

When extending the existing multi-service collection:

1. **Service prefixes prevent collisions**
   - `gateway_*` (future, if needed for clarity)
   - `eda_*` (active)
   - `controller_*` (used for names such as `controller_project` and `controller_settings`)

2. **Naming consistency across the collection**
   - Prefixes resolve conflicts, but are not universal service identifiers.
   - EDA includes unprefixed modules such as `decision_environment` and `event_stream`.
   - Controller includes unprefixed modules such as `inventory` and `job_template`.
   - Check the module documentation and its service-specific API implementation.

3. **Schema isolation**
   - Each service has its own transform mixins in `api/{service}/v1/`, `api/{service}/v2/`, etc.
   - Keep service-specific schemas and transformations in their owning mixins.

---

## Checklist Before Starting a New Module

- [ ] Identified which service owns the resource (Gateway/EDA/Controller)
- [ ] Ran naming conflict check against all three specs
- [ ] Determined if service prefix is needed
- [ ] Found the correct OpenAPI spec file
- [ ] Located the resource's OpenAPI tag/path in the spec
- [ ] Documented naming decision in PR description

---

## Tools

**List all resources in all specs**:
```bash
for spec in gateway eda controller; do
  echo "=== $spec ===" 
  python3 -c "
import json
with open('../aap-openapi-specs/$spec.json') as f:
    spec = json.load(f)
    paths = [p.split('/')[1] for p in spec['paths'].keys() if '{' not in p and p != '/']
    print(len(set(paths)), 'unique resources')
    for r in sorted(set(paths))[:15]:
        print(f'  {r}')
  "
done
```

**Check if a resource name appears in any spec**:
```bash
resource="projects"
for spec in gateway eda controller; do
  python3 -c "
import json
with open('../aap-openapi-specs/$spec.json') as f:
    spec = json.load(f)
    found = [p for p in spec['paths'] if '$resource' in p.lower() and '{' not in p]
    if found:
        print(f'$spec: {found}')
  "
done
```
