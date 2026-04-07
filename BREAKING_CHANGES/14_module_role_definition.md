# Module: ansible.platform.role_definition

Configure a gateway role definition.

## Note: Module is new in 2.7.x

This module did not exist in 2.5.x. No migration needed — use directly in new playbooks.

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | str | yes | Role definition name (must be unique) |
| `new_name` | str | no | Rename the role by changing the existing name |
| `description` | str | no | Description of the role definition |
| `content_type` | str | yes | Content type for which role applies (e.g., `awx.inventory`) |
| `permissions` | list of str | yes | List of permission strings (e.g., `awx.view_inventory`) |
| `state` | str | no | Desired state: `present` (default), `absent`, `exists`, or `enforced` |

## Result structure

### Example result (2.7.x)

```json
{
    "changed": true,
    "role_definition": {
        "id": 5,
        "name": "Organization Inventory Admin",
        "description": "Grants full inventory access",
        "content_type": "awx.inventory",
        "permissions": [
            "awx.view_inventory",
            "awx.change_inventory",
            "awx.delete_inventory",
            "awx.add_inventory"
        ],
        "created_at": "2025-01-15T10:30:00Z",
        "modified_at": "2025-01-15T10:30:00Z"
    },
}
```

## State: present — create example

```yaml
- name: Create a role definition
  ansible.platform.role_definition:
    name: Organization Inventory Admin
    description: Grants full inventory access
    content_type: awx.inventory
    permissions:
      - awx.view_inventory
      - awx.change_inventory
      - awx.delete_inventory
      - awx.add_inventory
    state: present
  register: result

# result.role_definition.id = 5
```

## State: absent — delete example

```yaml
- name: Delete a role definition
  ansible.platform.role_definition:
    name: Organization Inventory Admin
    state: absent
  register: result

# result.changed = true
```

## State: exists — check example

```yaml
- name: Check if role definition exists
  ansible.platform.role_definition:
    name: Organization Inventory Admin
    state: exists
  register: result

# result:
# {
#   "changed": false,
#   "role_definition": {
#     "id": 5,
#     "name": "Organization Inventory Admin",
#     "content_type": "awx.inventory"
#   }
# }
```

## State: enforced — example

```yaml
- name: Enforce role definition exact state
  ansible.platform.role_definition:
    name: Organization Inventory Admin
    description: Full inventory control
    content_type: awx.inventory
    permissions:
      - awx.view_inventory
      - awx.change_inventory
    state: enforced
  register: result
```

## Full example playbook

```yaml
---
- name: Configure role definitions
  hosts: localhost
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_pw }}"

  tasks:
    - name: Create inventory admin role
      ansible.platform.role_definition:
        name: Inventory Administrator
        description: Full control over inventories
        content_type: awx.inventory
        permissions:
          - awx.view_inventory
          - awx.add_inventory
          - awx.change_inventory
          - awx.delete_inventory
        state: present
      register: inv_admin_role

    - name: Create template viewer role
      ansible.platform.role_definition:
        name: Template Viewer
        description: Read-only access to job templates
        content_type: awx.jobtemplate
        permissions:
          - awx.view_jobtemplate
        state: present
      register: template_viewer_role

    - name: Create organization admin role
      ansible.platform.role_definition:
        name: Organization Administrator
        description: Full organization management
        content_type: awx.organization
        permissions:
          - awx.view_organization
          - awx.change_organization
          - awx.delete_organization
        state: present
      register: org_admin_role

    - name: Print created role IDs
      debug:
        msg:
          - "Inventory Admin Role ID: {{ inv_admin_role.role_definition.id }}"
          - "Template Viewer Role ID: {{ template_viewer_role.role_definition.id }}"
          - "Org Admin Role ID: {{ org_admin_role.role_definition.id }}"

    - name: Update role with additional permissions
      ansible.platform.role_definition:
        name: Inventory Administrator
        permissions:
          - awx.view_inventory
          - awx.add_inventory
          - awx.change_inventory
          - awx.delete_inventory
          - awx.manage_rbac
        state: present
```

## Common patterns

### Setup RBAC hierarchy with roles

```yaml
- name: Create tiered role definitions
  ansible.platform.role_definition:
    name: "{{ item.name }}"
    description: "{{ item.description }}"
    content_type: "{{ item.content_type }}"
    permissions: "{{ item.permissions }}"
    state: present
  loop:
    - name: "Viewer"
      description: "Read-only access"
      content_type: "awx.inventory"
      permissions:
        - "awx.view_inventory"
    - name: "Editor"
      description: "Read and modify access"
      content_type: "awx.inventory"
      permissions:
        - "awx.view_inventory"
        - "awx.change_inventory"
    - name: "Administrator"
      description: "Full control"
      content_type: "awx.inventory"
      permissions:
        - "awx.view_inventory"
        - "awx.add_inventory"
        - "awx.change_inventory"
        - "awx.delete_inventory"
  register: role_results
```

### Conditional role creation by environment

```yaml
- name: Create development roles with broader permissions
  ansible.platform.role_definition:
    name: "{{ item.name }}"
    content_type: "{{ item.content_type }}"
    permissions: "{{ item.permissions }}"
    state: present
  loop: "{{ dev_roles }}"
  when: environment == 'development'
  vars:
    dev_roles:
      - name: "Developer"
        content_type: "awx.jobtemplate"
        permissions:
          - "awx.view_jobtemplate"
          - "awx.change_jobtemplate"
          - "awx.launch_job"

- name: Create production roles with restricted permissions
  ansible.platform.role_definition:
    name: "{{ item.name }}"
    content_type: "{{ item.content_type }}"
    permissions: "{{ item.permissions }}"
    state: present
  loop: "{{ prod_roles }}"
  when: environment == 'production'
  vars:
    prod_roles:
      - name: "Operator"
        content_type: "awx.jobtemplate"
        permissions:
          - "awx.view_jobtemplate"
          - "awx.launch_job"
```

### Validate role permissions before assignment

```yaml
- name: Check if role exists
  ansible.platform.role_definition:
    name: "Custom Inventory Role"
    state: exists
  register: role_check

- name: Assign role only if it has required permissions
  ansible.platform.role_user_assignment:
    role_definition: "{{ role_check.role_definition.id }}"
    user: "jdoe"
    state: present
  when:
    - role_check.role_definition is defined
    - 'awx.view_inventory' in role_check.role_definition.permissions
```

### Cleanup obsolete roles

```yaml
- name: Remove deprecated roles
  ansible.platform.role_definition:
    name: "{{ item }}"
    state: absent
  loop:
    - "Old Viewer Role"
    - "Deprecated Custom Role"
    - "Legacy Permission Set"
  ignore_errors: true  # OK if roles don't exist
```
