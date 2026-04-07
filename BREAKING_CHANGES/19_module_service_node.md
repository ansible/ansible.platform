# Module: ansible.platform.service_node

Configure a gateway service node.

## Note: Module is new in 2.7.x

This module did not exist in 2.5.x. No migration needed — use directly in new playbooks.

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | str | yes | Service node name (must be unique) |
| `new_name` | str | no | Rename the service node |
| `address` | str | no | Network address to route traffic to (must be unique). Required when creating |
| `service_cluster` | str | no | Service cluster name or ID. Required when creating |
| `tags` | str | no | Comma-separated tags for traffic filtering |
| `state` | str | no | Desired state: `present` (default), `absent`, or `exists` |

## Result structure

### Example result (2.7.x)

```json
{
    "changed": true,
    "service_node": {
        "id": 3,
        "name": "Controller - Node 1",
        "address": "10.0.0.1",
        "service_cluster": 10,
        "tags": "primary,frontend",
        "created_at": "2025-01-15T10:30:00Z",
        "modified_at": "2025-01-15T10:30:00Z"
    },
}
```

## State: present — create example

```yaml
- name: Create service node
  ansible.platform.service_node:
    name: "Controller - Node 1"
    address: 10.0.0.1
    service_cluster: controller
    state: present
  register: result

# result.service_node.id = 3
```

## State: present — with tags example

```yaml
- name: Create tagged service node
  ansible.platform.service_node:
    name: "Controller - Worker Node"
    address: 10.0.0.2
    service_cluster: controller
    tags: "worker,secondary"
    state: present
  register: result
```

## State: absent — delete example

```yaml
- name: Delete service node
  ansible.platform.service_node:
    name: 3                           # ID can be used
    state: absent
  register: result

# result.changed = true
```

## State: exists — check example

```yaml
- name: Check if service node exists
  ansible.platform.service_node:
    name: "Controller - Node 1"
    state: exists
  register: result

# result:
# {
#   "changed": false,
#   "service_node": {
#     "id": 3,
#     "name": "Controller - Node 1",
#     "address": "10.0.0.1"
#   }
# }
```

## Full example playbook

```yaml
---
- name: Configure service nodes
  hosts: localhost
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_pw }}"

  tasks:
    - name: Create controller cluster nodes
      ansible.platform.service_node:
        name: "Controller - Node {{ item.num }}"
        address: "10.0.0.{{ item.num }}"
        service_cluster: Automation Controller
        tags: "{{ item.tags }}"
        state: present
      loop:
        - num: 1
          tags: "primary,frontend"
        - num: 2
          tags: "secondary,backend"
        - num: 3
          tags: "worker,background"
      register: controller_nodes

    - name: Create Hub cluster nodes
      ansible.platform.service_node:
        name: "Hub - Node {{ item.num }}"
        address: "10.0.1.{{ item.num }}"
        service_cluster: Automation Hub
        tags: "backend"
        state: present
      loop:
        - num: 1
        - num: 2
      register: hub_nodes

    - name: Create EDA cluster nodes
      ansible.platform.service_node:
        name: "EDA - Node {{ item.num }}"
        address: "10.0.2.{{ item.num }}"
        service_cluster: Event Driven Automation
        tags: "{{ item.tags }}"
        state: present
      loop:
        - num: 1
          tags: "event-processor"
        - num: 2
          tags: "event-processor"
      register: eda_nodes

    - name: Print created node IDs
      debug:
        msg:
          - "Controller nodes: {{ controller_nodes.results | map(attribute='service_node.id') | list }}"
          - "Hub nodes: {{ hub_nodes.results | map(attribute='service_node.id') | list }}"
          - "EDA nodes: {{ eda_nodes.results | map(attribute='service_node.id') | list }}"
```

## Common patterns

### Setup cluster with multiple tagged nodes

```yaml
- name: Create multi-tier cluster
  ansible.platform.service_node:
    name: "{{ item.name }}"
    address: "{{ item.address }}"
    service_cluster: "Main Cluster"
    tags: "{{ item.tags }}"
    state: present
  loop:
    - name: "API Server 1"
      address: "10.10.0.1"
      tags: "api,frontend"
    - name: "API Server 2"
      address: "10.10.0.2"
      tags: "api,frontend"
    - name: "Worker 1"
      address: "10.10.1.1"
      tags: "worker,backend"
    - name: "Worker 2"
      address: "10.10.1.2"
      tags: "worker,backend"
    - name: "Database Server"
      address: "10.10.2.1"
      tags: "database,internal"
```

### Create nodes from dynamic inventory

```yaml
- name: Create service nodes from inventory
  ansible.platform.service_node:
    name: "{{ hostvars[item].node_name | default(item) }}"
    address: "{{ hostvars[item].ansible_host }}"
    service_cluster: "{{ cluster_name }}"
    tags: "{{ hostvars[item].node_tags | default('') }}"
    state: present
  loop: "{{ groups['service_nodes'] }}"
  register: created_nodes
```

### Update node address and tags

```yaml
- name: Update service node's cluster
  ansible.platform.service_node:
    name: "Controller - Node 1"
    address: 10.0.0.1
    service_cluster: 2                # service cluster's name or ID
    tags: "primary,updated"
    state: present
```

### Rolling node update

```yaml
- name: Update nodes one by one
  block:
    - name: Get all nodes for cluster
      ansible.platform.service_node:
        name: "{{ item }}"
        state: exists
      loop: "{{ current_nodes }}"
      register: nodes_check

    - name: Update node address with minimal downtime
      ansible.platform.service_node:
        name: "{{ item.name }}"
        address: "{{ item.new_address }}"
        service_cluster: "{{ cluster_name }}"
        state: present
      loop: "{{ node_updates }}"
      pause: 10                       # 10 second pause between updates for graceful drain
```

### Cleanup and decommission nodes

```yaml
- name: Decommission nodes from cluster
  ansible.platform.service_node:
    name: "{{ item }}"
    state: absent
  loop:
    - "Deprecated Node 1"
    - "Deprecated Node 2"
    - "Old Backend Server"
  ignore_errors: true                 # OK if nodes don't exist
```

### Verify all nodes are in cluster

```yaml
- name: Validate all required nodes exist
  block:
    - name: Check each node
      ansible.platform.service_node:
        name: "{{ item.name }}"
        state: exists
      loop: "{{ required_nodes }}"
      register: node_checks

    - name: Create missing nodes
      ansible.platform.service_node:
        name: "{{ item.name }}"
        address: "{{ item.address }}"
        service_cluster: "{{ cluster_name }}"
        state: present
      loop: "{{ required_nodes }}"
      when: item.name not in (node_checks.results | map(attribute='service_node.name') | list)
```
