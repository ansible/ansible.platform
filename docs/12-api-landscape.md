# The AAP API Landscape: Gateway, EDA, Controller

This document maps the three AAP services and their resource coverage to help you choose the right spec when adding new modules and avoid naming conflicts.

## Quick Reference

| Service | Resources | Scope | Module Prefix |
|---------|-----------|-------|---------------|
| **Gateway** | 48 | AAP platform management (users, orgs, services) | *(none currently)* |
| **EDA** | 37 | Event-driven automation (projects, rulebooks, activations) | `eda_` |
| **Controller** | 93 | Ansible Controller (inventories, credentials, jobs) | `controller_` |

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

**Current Collection Coverage**: 22 modules (all Gateway resources)

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

**Current Collection Coverage**: 1 module (`eda_project`)

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
- More: `labels`, `schedules`, `notifications`, `webhook_receivers`, etc.

**Current Collection Coverage**: 0 modules (planned)

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

**Naming Strategy**: Already handled via authentication federation. These are typically shared across services via Gateway auth.

### EDA + Controller Only (2 resources)

| Resource | Status |
|----------|--------|
| **`projects`** | ⚠️ **CONFLICT** — EDA projects are rulebook repos, Controller projects are playbook repos |
| **`config`** | Shared configuration |

**Naming Rule**:
- EDA: `eda_project`
- Controller: `controller_project` (when implemented)

### Gateway + Controller Only (2 resources)
- `ping`, `settings`

**Action**: No conflict expected; use unprefixed names if added from these specs.

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

As the collection grows to support multiple AAP services:

1. **Service prefixes prevent collisions**
   - `gateway_*` (future, if needed for clarity)
   - `eda_*` (active)
   - `controller_*` (planned)

2. **Naming consistency across the collection**
   - All EDA modules start with `eda_`
   - All Controller modules start with `controller_`
   - This makes discovery via `ansible.platform.eda_` or `ansible.platform.controller_` possible

3. **Schema isolation**
   - Each service has its own transform mixins in `api/v1/`, `api/v2/`, etc.
   - No risk of Gateway fields leaking into EDA modules (or vice versa)

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
