# Module Documentation: ansible.platform.service_cluster

**Status:** NEW in 2.7 (ANSTRAT-1640)
**Module:** `ansible.platform.service_cluster`

---

## Summary

The `service_cluster` module is **NEW in 2.7**. It manages service clusters (grouped sets of service nodes) for high-availability service deployment. No migration needed from 2.6 (module did not exist).

This module handles defining clusters of service nodes.

---

## 1. Module Arguments

| Argument | Type | Required | Choices / Default | Description |
|----------|------|----------|-------------------|-------------|
| `name` | str | **yes** | — | Cluster name (unique) |
| `service` | str | **yes** | — | Service name or ID |
| `description` | str | no | — | Cluster description |
| `state` | str | no | `present` (default), `absent`, `exists` | Desired state |

---

## 2. Result Structure

### After (2.7.x) — nested under `service_cluster` key

```json
{
    "changed": true,
    "service_cluster": {
        "id": 1,
        "name": "api_cluster_us_east",
        "service": 1,
        "description": "API cluster for US East region",
        "created": "2025-04-06T12:34:56.000Z",
        "modified": "2025-04-06T12:34:56.000Z"
    },
}
```

### Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Numeric primary key |
| `name` | str | Cluster name |
| `service` | int | Associated service ID |
| `description` | str | Cluster description |
| `created` | str | ISO 8601 timestamp when record was created |
| `modified` | str | ISO 8601 timestamp of last modification |

---

## 3. Examples

```yaml
# Create a service cluster
- name: Create service cluster
  ansible.platform.service_cluster:
    name: "api_cluster_us_east"
    service: "api_service"
    description: "API cluster for US East region"
    state: present
  register: created_cluster

# Update cluster description
- name: Update cluster
  ansible.platform.service_cluster:
    name: "api_cluster_us_east"
    description: "Updated: API cluster for US East (HA)"
    state: present

# Delete a cluster
- name: Delete cluster
  ansible.platform.service_cluster:
    name: "api_cluster_us_east"
    state: absent
```

---

## 4. Notes

- **New in 2.7:** This module did not exist in 2.6
- **No migration needed:** New functionality only
- **Regional organization:** Clusters often represent geographic or logical regions
- **Node grouping:** Nodes are added to clusters separately (via `service_node` module)
- **HA deployment:** Enables redundancy within regions

---

## 5. First-use Checklist

- [ ] Plan cluster topology (regions, HA groups)
- [ ] Create services first (clusters reference services)
- [ ] Create clusters for each regional or logical group
- [ ] Add service_node entries to clusters
- [ ] Check result at `result.service_cluster.*` (nested key structure)
