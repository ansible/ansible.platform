# Module Documentation: ansible.platform.service_node

**Status:** NEW in 2.7 (ANSTRAT-1640)
**Module:** `ansible.platform.service_node`

---

## Summary

The `service_node` module is **NEW in 2.7**. It manages individual nodes within service clusters for distributed service deployment. No migration needed from 2.6 (module did not exist).

This module handles registering service nodes in clusters.

---

## 1. Module Arguments

| Argument | Type | Required | Choices / Default | Description |
|----------|------|----------|-------------------|-------------|
| `hostname` | str | **yes** | — | Node hostname or IP address |
| `service_cluster` | str | **yes** | — | Service cluster name or ID |
| `port` | int | no | — | Node listening port |
| `description` | str | no | — | Node description |
| `state` | str | no | `present` (default), `absent`, `exists` | Desired state |

---

## 2. Result Structure

### After (2.7.x) — nested under `service_node` key

```json
{
    "changed": true,
    "service_node": {
        "id": 3,
        "hostname": "api-node-1.internal",
        "service_cluster": 1,
        "port": 8000,
        "description": "API node 1 (US East)",
        "created": "2025-04-06T12:34:56.000Z",
        "modified": "2025-04-06T12:34:56.000Z"
    },
}
```

### Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Numeric primary key |
| `hostname` | str | Node hostname or IP |
| `service_cluster` | int | Associated cluster ID |
| `port` | int | Node listening port |
| `description` | str | Node description |
| `created` | str | ISO 8601 timestamp when record was created |
| `modified` | str | ISO 8601 timestamp of last modification |

---

## 3. Examples

```yaml
# Add a node to a cluster
- name: Add service node to cluster
  ansible.platform.service_node:
    hostname: "api-node-1.internal"
    service_cluster: "api_cluster_us_east"
    port: 8000
    description: "API node 1 (US East)"
    state: present

# Add multiple nodes (loop pattern)
- name: Add multiple nodes
  ansible.platform.service_node:
    hostname: "{{ item.hostname }}"
    service_cluster: "api_cluster_us_east"
    port: "{{ item.port }}"
    state: present
  loop:
    - hostname: "api-node-1.internal"
      port: 8000
    - hostname: "api-node-2.internal"
      port: 8000
    - hostname: "api-node-3.internal"
      port: 8000

# Remove a node
- name: Remove service node
  ansible.platform.service_node:
    hostname: "api-node-1.internal"
    service_cluster: "api_cluster_us_east"
    state: absent
```

---

## 4. Notes

- **New in 2.7:** This module did not exist in 2.6
- **No migration needed:** New functionality only
- **DNS/IP:** Hostname can be DNS name or IP address
- **Load balancing:** Multiple nodes enable traffic distribution
- **Cluster hierarchy:** Nodes belong to clusters, which belong to services
- **Port flexibility:** Each node can listen on different ports if needed

---

## 5. First-use Checklist

- [ ] Plan service cluster topology
- [ ] Ensure nodes are reachable at specified hostnames/ports
- [ ] Create clusters first (nodes reference clusters)
- [ ] Add nodes one by one or via loop
- [ ] Verify connectivity to each node
- [ ] Check result at `result.service_node.*` (nested key structure)
