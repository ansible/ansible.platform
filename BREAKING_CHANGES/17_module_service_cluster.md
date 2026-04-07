# Module: ansible.platform.service_cluster

Configure a gateway service cluster.

## Note: Module is new in 2.7.x

This module did not exist in 2.5.x. No migration needed — use directly in new playbooks.

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | str | yes | Service cluster name (must be unique) |
| `new_name` | str | no | Rename the service cluster |
| `service_type` | str | no | Service Type name or ID. Required when creating |
| `auth_type` | str | no | Authentication type: JWT (default), BASIC, or TOKEN |
| `upstream_hostname` | str | no | Hostname for SNI and host header |
| `dns_discovery_type` | str | no | STRICT_DNS (default) or LOGICAL_DNS |
| `dns_lookup_family` | str | no | ALL, V4_ONLY, V6_ONLY, V4_PREFERRED, or AUTO |
| `outlier_detection_enabled` | bool | no | Enable outlier detection |
| `outlier_detection_consecutive_5xx` | int | no | Consecutive 5xx before unhealthy |
| `outlier_detection_interval_seconds` | int | no | Time between ejection analysis sweeps |
| `outlier_detection_base_ejection_time_seconds` | int | no | Base time for node ejection |
| `outlier_detection_max_ejection_percent` | int | no | Max percent of nodes to eject |
| `health_checks_enabled` | bool | no | Enable health checks |
| `health_check_timeout_seconds` | int | no | Health check timeout |
| `health_check_interval_seconds` | int | no | Time between health checks |
| `health_check_unhealthy_threshold` | int | no | Failed checks before unhealthy |
| `health_check_healthy_threshold` | int | no | Successful checks before healthy |
| `healthy_panic_threshold` | int | no | Panic threshold percentage (0 to disable) |
| `state` | str | no | Desired state: `present` (default), `absent`, or `exists` |

## Result structure

### Example result (2.7.x)

```json
{
    "changed": true,
    "service_cluster": {
        "id": 10,
        "name": "Automation Controller",
        "service_type": 1,
        "auth_type": "JWT",
        "upstream_hostname": "controller.example.com",
        "dns_discovery_type": "STRICT_DNS",
        "dns_lookup_family": "AUTO",
        "outlier_detection_enabled": true,
        "outlier_detection_consecutive_5xx": 5,
        "outlier_detection_interval_seconds": 10,
        "outlier_detection_base_ejection_time_seconds": 30,
        "outlier_detection_max_ejection_percent": 50,
        "health_checks_enabled": true,
        "health_check_timeout_seconds": 5,
        "health_check_interval_seconds": 10,
        "health_check_unhealthy_threshold": 3,
        "health_check_healthy_threshold": 2,
        "healthy_panic_threshold": 50,
        "created_at": "2025-01-15T10:30:00Z",
        "modified_at": "2025-01-15T10:30:00Z"
    },
    "elapsed_ms": 201,
    "api_version": "1"
}
```

## State: present — create example

```yaml
- name: Add service cluster
  ansible.platform.service_cluster:
    name: Automation Controller
    service_type: controller
    auth_type: JWT
    upstream_hostname: controller.example.com
    dns_discovery_type: STRICT_DNS
    health_checks_enabled: true
    state: present
  register: result

# result.service_cluster.id = 10
```

## State: absent — delete example

```yaml
- name: Delete service cluster
  ansible.platform.service_cluster:
    name: Automation Controller
    state: absent
  register: result

# result.changed = true
```

## State: exists — check example

```yaml
- name: Check if cluster exists
  ansible.platform.service_cluster:
    name: Automation Controller
    state: exists
  register: result

# result:
# {
#   "changed": false,
#   "service_cluster": {
#     "id": 10,
#     "name": "Automation Controller",
#     "service_type": 1
#   }
# }
```

## Full example playbook

```yaml
---
- name: Configure service clusters
  hosts: localhost
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_pw }}"

  tasks:
    - name: Create controller service cluster
      ansible.platform.service_cluster:
        name: Automation Controller
        service_type: controller
        auth_type: JWT
        upstream_hostname: controller.example.com
        dns_discovery_type: STRICT_DNS
        health_checks_enabled: true
        health_check_interval_seconds: 10
        health_check_timeout_seconds: 5
        outlier_detection_enabled: true
        state: present
      register: controller_cluster

    - name: Create EDA service cluster
      ansible.platform.service_cluster:
        name: Event Driven Automation
        service_type: eda
        auth_type: JWT
        upstream_hostname: eda.example.com
        dns_discovery_type: STRICT_DNS
        health_checks_enabled: true
        outlier_detection_enabled: true
        state: present
      register: eda_cluster

    - name: Create Hub service cluster
      ansible.platform.service_cluster:
        name: Automation Hub
        service_type: hub
        auth_type: BASIC
        upstream_hostname: hub.example.com
        dns_discovery_type: LOGICAL_DNS
        health_checks_enabled: true
        state: present
      register: hub_cluster

    - name: Print cluster IDs
      debug:
        msg:
          - "Controller cluster ID: {{ controller_cluster.service_cluster.id }}"
          - "EDA cluster ID: {{ eda_cluster.service_cluster.id }}"
          - "Hub cluster ID: {{ hub_cluster.service_cluster.id }}"
```

## Common patterns

### Create cluster with health checks and outlier detection

```yaml
- name: Create resilient service cluster
  ansible.platform.service_cluster:
    name: "{{ cluster_name }}"
    service_type: "{{ service_type }}"
    auth_type: JWT
    upstream_hostname: "{{ upstream_host }}"
    health_checks_enabled: true
    health_check_interval_seconds: 5
    health_check_timeout_seconds: 3
    health_check_unhealthy_threshold: 3
    health_check_healthy_threshold: 2
    outlier_detection_enabled: true
    outlier_detection_consecutive_5xx: 5
    outlier_detection_interval_seconds: 10
    outlier_detection_base_ejection_time_seconds: 30
    outlier_detection_max_ejection_percent: 50
    state: present
  vars:
    cluster_name: "Production Cluster"
    service_type: "controller"
    upstream_host: "controller.prod.example.com"
```

### Setup DNS-based discovery for multiple zones

```yaml
- name: Create DNS-based cluster for zone failover
  ansible.platform.service_cluster:
    name: "{{ item.name }}"
    service_type: "{{ item.type }}"
    auth_type: JWT
    upstream_hostname: "{{ item.hostname }}"
    dns_discovery_type: STRICT_DNS       # Load balance all addresses
    dns_lookup_family: AUTO              # Prefer IPv6
    health_checks_enabled: true
    state: present
  loop:
    - name: "Zone A Cluster"
      type: "controller"
      hostname: "controller-a.example.com"
    - name: "Zone B Cluster"
      type: "controller"
      hostname: "controller-b.example.com"
```

### Create cluster with aggressive outlier detection

```yaml
- name: Create cluster with fast failover
  ansible.platform.service_cluster:
    name: "Critical Service Cluster"
    service_type: "critical"
    auth_type: JWT
    upstream_hostname: "critical.example.com"
    outlier_detection_enabled: true
    outlier_detection_consecutive_5xx: 2        # Fast detection
    outlier_detection_base_ejection_time_seconds: 10
    outlier_detection_max_ejection_percent: 50
    healthy_panic_threshold: 0                   # Never panic-route
    state: present
```

### Setup cluster with token-based auth

```yaml
- name: Create service cluster with token auth
  ansible.platform.service_cluster:
    name: "Token Auth Service"
    service_type: "custom"
    auth_type: TOKEN
    upstream_hostname: "custom.example.com"
    dns_discovery_type: STRICT_DNS
    health_checks_enabled: false              # May not be supported for this auth type
    state: present
```

### Verify and update cluster configuration

```yaml
- name: Check cluster health check settings
  ansible.platform.service_cluster:
    name: "Production Cluster"
    state: exists
  register: cluster_check

- name: Enable health checks if disabled
  ansible.platform.service_cluster:
    name: "Production Cluster"
    health_checks_enabled: true
    health_check_interval_seconds: 10
    state: present
  when: not cluster_check.service_cluster.health_checks_enabled
```
