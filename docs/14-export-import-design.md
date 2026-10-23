# Export / Import Design — Controller Configuration as Data

**Jira**: AAP-95849
**Status**: Draft / Investigation
**Branch**: `feature/migration-testing`

---

## Problem Statement

The legacy `awx.awx.export` and `awx.awx.import` modules let users dump and
restore Controller configuration as a single Ansible task. Both modules are thin
wrappers around **awxkit** — they contain no direct REST API calls. All
orchestration logic (dependency ordering, natural-key resolution, FK traversal,
role assignment, related-object handling) lives in `awxkit.api.pages.api.ApiV2`:

- `export_assets()` — ~180 lines of client-side logic
- `import_assets()` — ~200 lines of client-side logic

There is **no** Controller API endpoint for bulk export or import. The
Controller OpenAPI spec (`controller.json`) has no `/export/` or `/import/`
path. Everything is client-side orchestration.

Migrating these modules to `ansible.platform` cannot follow the standard
seven-file CRUD resource pattern (Shape 1–6 in the migration skill). They are
**Shape 7 — whole-instance / query** modules that operate across all resource
types simultaneously.

---

## Design Constraints

1. **No awxkit dependency** — `ansible.platform` must not depend on awxkit at
   runtime. The whole point of the migration is to use the platform SDK.
2. **SDK architecture compliance** — no HTTP in action plugins; all network I/O
   through the manager process.
3. **Leverage existing modules** — all 13 exportable resource types already have
   fully functional CRUD modules on this branch with name-based FK resolution.
4. **Backward compatibility** — users with existing awxkit exports (from `awx
   export` CLI or the legacy module) should be able to import them.

---

## Approach: Ansible Role + Filter Plugin

Rather than reimplementing awxkit's ~400 lines of orchestration in a monolithic
action plugin, use **Ansible roles** that call the existing CRUD modules in
dependency order. This approach:

- Reuses all existing module logic (FK resolution, association management,
  idempotency, check mode)
- Is transparent — users can read the role's tasks to understand what happens
- Is extensible — adding a new resource type means adding one task file
- Avoids a new SDK-layer bulk API that doesn't map to any real Controller
  endpoint

### Components

| Component | Location | Purpose |
|---|---|---|
| Import role | `roles/controller_import/` | Import assets using CRUD modules in dependency order |
| Legacy adapter filter | `plugins/filter/controller_export.py` | Convert awxkit export format → native import format |
| Native format spec | This document (Section: Native Format) | Module-parameter-native YAML/JSON schema |

### What is NOT included (Phase 1)

- **Export role** — deferred. Users can export using `awx export` CLI or the
  legacy module and convert via the adapter filter. Export requires solving
  FK-ID-to-name reverse resolution and related-object traversal, which is
  significant additional complexity.
- **Workflow job template nodes** — the legacy export includes WF nodes as
  related objects. Importing these requires the `workflow_job_template_node`
  module (not yet confirmed on this branch). Tracked as a gap.

---

## SECTION 1: Native Import Format

The native format is designed around module parameter names. Each top-level key
is a resource type; values are lists of dicts where keys match the corresponding
module's `options:` exactly. FK references use **names** (not IDs) — the modules
handle resolution internally.

### Schema

```yaml
# ansible.platform native import format v1
format_version: 1

organizations:
  - name: Default
    description: "Default organization"

users:
  - username: admin
    email: admin@example.com
    first_name: Admin
    last_name: User
    is_superuser: true

teams:
  - name: Ops Team
    organization: Default              # FK by name
    description: "Operations team"

credential_types:
  - name: Custom Cloud
    kind: cloud
    inputs:
      fields:
        - id: api_key
          type: string
          label: API Key
    injectors:
      extra_vars:
        api_key: "{{ api_key }}"

credentials:
  - name: AWS Prod
    credential_type: Amazon Web Services  # FK by name
    organization: Default                 # FK by name
    inputs:
      username: AKIAIOSFODNN7EXAMPLE
      password: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

execution_environments:
  - name: Custom EE
    image: quay.io/ansible/awx-ee:latest
    organization: Default
    pull: missing

notification_templates:
  - name: Slack Notify
    organization: Default
    notification_type: slack
    notification_configuration:
      token: xoxb-example
      channels:
        - "#deployments"

projects:
  - name: Demo Project
    organization: Default
    scm_type: git
    scm_url: https://github.com/ansible/ansible-tower-samples
    scm_branch: main
    notification_templates_started: []
    notification_templates_success: [Slack Notify]  # association by name
    notification_templates_error: [Slack Notify]

labels:
  - name: Production
    organization: Default

inventory:
  - name: Production
    organization: Default
    description: "Production servers"
    # Hosts and groups are inline under the inventory for import ordering
    hosts:
      - name: web01.example.com
        enabled: true
        variables:
          ansible_host: 10.0.1.10
      - name: db01.example.com
        enabled: true
    groups:
      - name: webservers
        hosts: [web01.example.com]       # association by name
      - name: databases
        hosts: [db01.example.com]

inventory_sources:
  - name: AWS Source
    inventory: Production                # FK by name
    source: ec2
    credential: AWS Prod                 # FK by name
    overwrite: true

job_templates:
  - name: Deploy App
    project: Demo Project                # FK by name
    inventory: Production                # FK by name
    playbook: deploy.yml
    job_type: run
    credentials: [AWS Prod]              # association by name
    labels: [Production]                 # association by name
    instance_groups: []
    notification_templates_started: []
    notification_templates_success: [Slack Notify]
    notification_templates_error: [Slack Notify]
    survey_spec: {}                      # dict, passed directly
    survey_enabled: false

workflow_job_templates:
  - name: Full Deploy
    organization: Default
    description: "End-to-end deployment"
    survey_enabled: false
    labels: [Production]
    notification_templates_success: [Slack Notify]

schedules:
  - name: Nightly Deploy
    unified_job_template: Deploy App     # FK by name
    rrule: "DTSTART:20250101T000000Z RRULE:FREQ=DAILY;INTERVAL=1"
    enabled: true
```

### Design Decisions

1. **Names, not IDs** — every FK reference and association uses resource names.
   The modules resolve names to IDs via `lookup_resource_id()`. This makes the
   format human-readable and portable across Controller instances.

2. **Hosts and groups nested under inventory** — in the legacy format, hosts and
   groups are `related` objects of inventory. The native format inlines them
   under the inventory entry for clarity. The import role extracts and creates
   them as separate tasks after the parent inventory.

3. **No `state` field** — import always means `state: present`. The format does
   not encode deletion; that is a separate operational concern.

4. **No `new_name` / `copy_from`** — these are mutation operations, not relevant
   to restoring configuration from an export.

5. **`format_version: 1`** — enables future format evolution without breaking
   existing imports.

---

## SECTION 2: Import Role Design

### Directory Structure

```
roles/
  controller_import/
    defaults/main.yml       # Default variable values
    meta/main.yml           # Role metadata, dependencies
    tasks/
      main.yml              # Orchestrator — includes per-type tasks in order
      organizations.yml
      users.yml
      teams.yml
      credential_types.yml
      credentials.yml
      execution_environments.yml
      notification_templates.yml
      projects.yml
      labels.yml
      inventory.yml         # Also handles hosts and groups
      inventory_sources.yml
      job_templates.yml
      workflow_job_templates.yml
      schedules.yml
```

### Role Variables

```yaml
# defaults/main.yml

# The assets to import — native format dict (see Section 1)
controller_import_assets: {}

# Subset of resource types to import (default: all present in assets)
# Example: [organizations, credentials, job_templates]
controller_import_types: []

# Error handling
controller_import_on_error: fail    # fail | skip | warn
```

### Dependency Order

The import role processes resource types in this order, matching the dependency
graph that awxkit's `_dependent_resources()` computes:

```
1.  organizations      — no dependencies
2.  users              — no dependencies (org association deprecated)
3.  teams              — depends on: organizations
4.  credential_types   — no dependencies
5.  credentials        — depends on: credential_types, organizations, users, teams
6.  execution_environments — depends on: organizations, credentials
7.  notification_templates — depends on: organizations
8.  projects           — depends on: organizations, credentials, execution_environments
9.  labels             — depends on: organizations
10. inventory          — depends on: organizations, instance_groups
    10a. hosts         — depends on: inventory
    10b. groups        — depends on: inventory, hosts
11. inventory_sources  — depends on: inventory, credentials, projects, execution_environments
12. job_templates      — depends on: projects, inventory, credentials, labels, execution_environments
13. workflow_job_templates — depends on: organizations, inventory, labels
14. schedules          — depends on: job_templates, workflow_job_templates, credentials, labels
```

### Task Pattern (per resource type)

Each task file follows the same pattern:

```yaml
# tasks/credentials.yml
---
- name: Import credentials
  ansible.platform.controller_credential:
    name: "{{ item.name }}"
    description: "{{ item.description | default(omit) }}"
    credential_type: "{{ item.credential_type }}"
    organization: "{{ item.organization | default(omit) }}"
    user: "{{ item.user | default(omit) }}"
    team: "{{ item.team | default(omit) }}"
    inputs: "{{ item.inputs | default(omit) }}"
    state: present
  loop: "{{ controller_import_assets.credentials | default([]) }}"
  loop_control:
    label: "{{ item.name }}"
  when: >-
    controller_import_assets.credentials is defined and
    (controller_import_types | length == 0 or 'credentials' in controller_import_types)
  register: _credential_results
  ignore_errors: "{{ controller_import_on_error == 'skip' }}"
...
```

### Inventory Task (special case — hosts and groups)

```yaml
# tasks/inventory.yml
---
- name: Import inventories
  ansible.platform.inventory:
    name: "{{ item.name }}"
    description: "{{ item.description | default(omit) }}"
    organization: "{{ item.organization }}"
    kind: "{{ item.kind | default(omit) }}"
    variables: "{{ item.variables | default(omit) }}"
    instance_groups: "{{ item.instance_groups | default(omit) }}"
    state: present
  loop: "{{ controller_import_assets.inventory | default([]) }}"
  loop_control:
    label: "{{ item.name }}"
  when: controller_import_assets.inventory is defined
  register: _inventory_results

- name: Import hosts for each inventory
  ansible.platform.host:
    name: "{{ host_item.1.name }}"
    inventory: "{{ host_item.0.name }}"
    description: "{{ host_item.1.description | default(omit) }}"
    enabled: "{{ host_item.1.enabled | default(omit) }}"
    variables: "{{ host_item.1.variables | default(omit) }}"
    state: present
  loop: >-
    {{ controller_import_assets.inventory | default([])
       | subelements('hosts', skip_missing=True) }}
  loop_control:
    loop_var: host_item
    label: "{{ host_item.0.name }}/{{ host_item.1.name }}"

- name: Import groups for each inventory
  ansible.platform.group:
    name: "{{ group_item.1.name }}"
    inventory: "{{ group_item.0.name }}"
    description: "{{ group_item.1.description | default(omit) }}"
    variables: "{{ group_item.1.variables | default(omit) }}"
    hosts: "{{ group_item.1.hosts | default(omit) }}"
    children: "{{ group_item.1.children | default(omit) }}"
    state: present
  loop: >-
    {{ controller_import_assets.inventory | default([])
       | subelements('groups', skip_missing=True) }}
  loop_control:
    loop_var: group_item
    label: "{{ group_item.0.name }}/{{ group_item.1.name }}"
...
```

### Idempotency

The role is idempotent by design — every module it calls is idempotent. Running
the import role twice with the same data produces `changed: false` on the second
run. This is a significant improvement over the legacy `import_assets()` which
always reports `changed: true` because it unconditionally PUTs every resource.

### Check Mode

Full check mode support inherited from the underlying modules. Running with
`--check` shows what would change without modifying the Controller.

---

## SECTION 3: Legacy Format Adapter

A Jinja2 filter plugin that converts awxkit's natural-key export format to the
native import format.

### Usage

```yaml
- name: Load legacy export
  set_fact:
    legacy_data: "{{ lookup('file', 'awxkit_export.json') | from_json }}"

- name: Convert to native format
  set_fact:
    native_data: "{{ legacy_data | ansible.platform.from_awxkit_export }}"

- name: Import converted data
  ansible.builtin.include_role:
    name: ansible.platform.controller_import
  vars:
    controller_import_assets: "{{ native_data }}"
```

### Transformation Rules

The filter performs these transformations:

| awxkit format | native format | Notes |
|---|---|---|
| `natural_key: {type: "organization", name: "Foo"}` | `organization: "Foo"` | FK references simplified to name strings |
| `natural_key` on each object | Stripped | Used only for identification, not needed in import |
| `related.credentials` (list of natural keys) | `credentials: ["Cred A", "Cred B"]` | Association lists simplified |
| `related.survey_spec` (dict) | `survey_spec: {…}` | Inlined as top-level field |
| `related.hosts` / `related.groups` | Nested under parent inventory | Restructured for import role |
| `related.roles` | Omitted (Phase 1) | Platform RBAC model differs; needs separate design |
| `related.notification_templates` | Split by event type | `notification_templates_started/success/error` |
| Top-level `inventory` key | `inventory` | Same key name, different object structure |
| `credential_types` | `credential_types` | Key name matches |

### Natural Key Resolution

The legacy export uses natural keys like:

```json
{
  "name": "My Template",
  "project": {
    "type": "project",
    "name": "Demo",
    "organization": {"type": "organization", "name": "Default"}
  }
}
```

The adapter flattens these to just the name:

```yaml
name: My Template
project: Demo
```

This works because the platform modules resolve names internally. For ambiguous
names (e.g., two projects named "Demo" in different orgs), the adapter preserves
the organization context when the module supports it (e.g., `job_template` has
an `organization` field for project disambiguation).

---

## SECTION 4: Resource Type Mapping

Complete mapping between legacy awxkit export keys and `ansible.platform`
modules on the `feature/migration-testing` branch:

| awxkit key | Platform module | Service | FK references (by name) | Association fields |
|---|---|---|---|---|
| `organizations` | `organization` | gateway | — | — |
| `users` | `user` | gateway | — | — |
| `teams` | `team` | gateway | organization | — |
| `credential_types` | `controller_credential_type` | controller | — | — |
| `credentials` | `controller_credential` | controller | credential_type, organization, user, team | — |
| `execution_environments` | `execution_environment` | controller | organization, credential | — |
| `notification_templates` | `notification_template` | controller | organization | — |
| `projects` | `controller_project` | controller | credential, default_environment, organization, signature_validation_credential | notification_templates_* |
| `inventory` | `inventory` | controller | organization | instance_groups, input_inventories |
| `inventory_sources` | `inventory_source` | controller | inventory, credential, execution_environment, source_project | notification_templates_* |
| `job_templates` | `job_template` | controller | inventory, project, organization, execution_environment, webhook_credential | credentials, labels, instance_groups, notification_templates_*, survey_spec |
| `workflow_job_templates` | `workflow_job_template` | controller | organization, inventory, webhook_credential | labels, notification_templates_*, survey_spec |
| `schedules` | `schedule` | controller | unified_job_template, inventory, execution_environment, organization | credentials, labels, instance_groups |

**Supporting resources** (not top-level in awxkit, but needed):

| Resource | Module | Parent | Notes |
|---|---|---|---|
| hosts | `host` | inventory | Related object in awxkit export |
| groups | `group` | inventory | Related object, has host/child associations |
| labels | `label` | — | Cannot be deleted, only created. Auto-cleaned by API |

---

## SECTION 5: Known Gaps and Limitations

### Phase 1 gaps

1. **No export role** — users must use `awx export` CLI or the legacy module to
   generate export data, then convert with the filter.

2. **Workflow job template nodes** — the legacy export includes WF nodes as
   related objects of workflow_job_templates. Importing these requires a node
   module that handles the DAG structure (predecessors, success/failure/always
   nodes). This is complex enough to warrant its own design.

3. **RBAC / role assignments** — the legacy export includes `related.roles`
   with content-object-based role assignments. The platform uses a different
   RBAC model (`role_user_assignment` / `role_team_assignment` /
   `role_definition`). A mechanical port of the legacy role format is actively
   wrong. Needs separate design aligned with the platform RBAC model.

4. **Credential inputs (secrets)** — exported credentials have encrypted input
   values (`$encrypted$`). The import role passes these through, but the
   Controller API will reject `$encrypted$` as an actual value on create. Users
   must supply real secrets for new resources. This matches the legacy behavior
   (awxkit's `remove_encrypted()` strips these).

5. **Project sync wait** — the legacy import waits up to 300s for a project's
   first update to complete before creating dependent JTs. The import role does
   not currently implement this wait. Projects that need an SCM sync before
   their playbooks are available may cause JT creation to fail on playbook
   validation. Mitigation: run the import role twice, or add a
   `project_update` + `job_wait` task between projects and job_templates.

6. **Constructed inventory `input_inventories`** — requires the input
   inventories to already exist. The dependency ordering handles this for
   inventories within the same import, but external references will fail.

### Legacy format edge cases

1. **Labels with `NoContent` response** — awxkit handles a `NoContent` exception
   on label POST (already exists). The `label` module handles this natively.

2. **User passwords** — awxkit sets a default password (`abc123`) for new users.
   The import role does NOT do this — users without a password in the import data
   will be created without one (matching the module's behavior).

3. **Special `all` keyword** — the legacy export accepts `"all"` as a resource
   name to export all items of that type. Not applicable to import.

---

## SECTION 6: Testing Strategy

### Unit tests

- Filter plugin: round-trip tests with sample awxkit export JSON → verify
  native format output matches expected structure for each resource type.
- Edge cases: empty exports, missing resource types, resources with no
  related objects, encrypted credential inputs.

### Molecule mock scenarios

- `controller_import_mock/` — import a small set of resources (org, credential
  type, credential, project, inventory with hosts/groups, job template) against
  the mock gateway server.
- Verify idempotency: run import twice, assert `changed: false` on second run.
- Verify selective import: set `controller_import_types` to a subset.
- Verify error handling: import with a missing FK reference, verify behavior
  matches `controller_import_on_error` setting.

### Integration tests

Current CI provides a full AAP environment (Gateway + Controller + EDA + Hub),
so live integration testing is available — unlike many other Controller module
tests, this is not blocked by infrastructure.

- Full round-trip: export from a live Controller with `awx export`, convert
  with filter, import with role, verify resources exist.
- Idempotency: run the import role twice against live AAP, assert
  `changed: false` on the second run.
- Conflict handling: pre-create resources with different field values, run
  import, verify they are updated correctly.
- Dependency ordering: import a full asset set (org → cred type → cred →
  project → inventory → JT) and verify all FK references resolve.
- Encrypted credentials: verify imported credentials with `$encrypted$` inputs
  are created successfully (with empty/placeholder secrets).

---

## SECTION 7: Future Work (Phase 2+)

### Export role

An export role using the `gateway_api` lookup plugin to fetch resources and
produce the native format. Challenges:

- **FK-ID-to-name resolution** — API responses return FK fields as IDs. Each
  ID needs a reverse lookup to get the name. The `gateway_api` lookup can do
  this but it's O(n) additional API calls per FK field per resource.
- **Related objects** — survey_spec, credentials, labels, notification template
  associations each require a sub-endpoint query per parent resource.
- **Performance** — many sequential API calls. Could be mitigated by caching
  resource-type → {id: name} maps.

### RBAC export/import

Design a format for role assignments compatible with the platform's unified
RBAC model. This is a separate design effort — the legacy format's
content-object-based roles don't map 1:1 to `role_definition` +
`role_user_assignment` + `role_team_assignment`.

### Workflow job template nodes

Design import support for the WF node DAG structure. Needs:
- A `workflow_job_template_node` module (or support in the WF module)
- DAG ordering logic (topological sort of node dependencies)
- Support for approval nodes, which have a different creation endpoint

---

## Appendix A: awxkit Export Format Reference

For reference, the legacy awxkit export produces this structure:

```json
{
  "organizations": [
    {
      "name": "Default",
      "description": "",
      "natural_key": {
        "type": "organization",
        "name": "Default"
      },
      "related": {
        "notification_templates": [],
        "roles": [
          {
            "name": "Admin",
            "content_object": {
              "type": "organization",
              "name": "Default"
            }
          }
        ]
      }
    }
  ],
  "job_templates": [
    {
      "name": "Demo",
      "job_type": "run",
      "inventory": {
        "type": "inventory",
        "name": "Demo Inventory",
        "organization": {
          "type": "organization",
          "name": "Default"
        }
      },
      "project": {
        "type": "project",
        "name": "Demo Project",
        "organization": {
          "type": "organization",
          "name": "Default"
        }
      },
      "playbook": "hello_world.yml",
      "natural_key": {
        "type": "job_template",
        "name": "Demo",
        "organization": {
          "type": "organization",
          "name": "Default"
        }
      },
      "related": {
        "credentials": [
          {
            "type": "credential",
            "name": "Demo Credential",
            "credential_type": {
              "type": "credential_type",
              "name": "Machine",
              "kind": "ssh"
            }
          }
        ],
        "labels": [],
        "survey_spec": {}
      }
    }
  ]
}
```
