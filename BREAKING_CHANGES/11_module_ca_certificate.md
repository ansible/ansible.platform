# Module: ansible.platform.ca_certificate

Manage CA Certificates in the Automation Platform Gateway.

## Note: Module is new in 2.7.x

This module did not exist in 2.5.x. No migration needed — use directly in new playbooks.

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | str | yes | The name of the CA Certificate |
| `pem_data` | str | no | The PEM encoded certificate data. Required when creating/updating |
| `sha256` | str | no | The SHA256 fingerprint of the certificate. Required when creating/updating |
| `related_id_reference` | str | no | Used to track the related EDA credential (UUID) |
| `state` | str | no | Desired state: `present` (default), `absent`, or `exists` |

## Result structure

### Example result (2.7.x)

```json
{
    "changed": true,
    "ca_certificate": {
        "id": "42",
        "name": "My CA Certificate",
        "pem_data": "-----BEGIN CERTIFICATE-----\nMIIC...\n-----END CERTIFICATE-----",
        "sha256": "a1b2c3d4e5f6789012345678901234567890123456789012345678901234567890",
        "related_id_reference": null,
        "created_at": "2025-01-15T10:30:00Z",
        "modified_at": "2025-01-15T10:30:00Z"
    },
}
```

## State: present — create example

```yaml
- name: Add a CA Certificate
  ansible.platform.ca_certificate:
    name: "My CA Certificate"
    pem_data: "{{ lookup('file', 'ca_cert.pem') }}"
    sha256: "a1b2c3d4e5f6789012345678901234567890123456789012345678901234567890"
    state: present
  register: result

# result.ca_certificate.id = "42"
```

## State: absent — example

```yaml
- name: Remove a CA Certificate
  ansible.platform.ca_certificate:
    name: "My CA Certificate"
    state: absent
  register: result

# result.changed = true
```

## State: exists — example

```yaml
- name: Check if certificate exists
  ansible.platform.ca_certificate:
    name: "My CA Certificate"
    state: exists
  register: result

# result:
# {
#   "changed": false,
#   "ca_certificate": {
#     "id": "42",
#     "name": "My CA Certificate",
#     "sha256": "a1b2c3d4e5f6..."
#   }
# }
```

## Full example playbook

```yaml
---
- name: Manage CA Certificates
  hosts: localhost
  gather_facts: false

  module_defaults:
    group/ansible.platform.gateway:
      gateway_url: https://gateway.example.com
      gateway_username: admin
      gateway_password: "{{ vault_pw }}"

  tasks:
    - name: Load certificate from file
      set_fact:
        ca_cert_pem: "{{ lookup('file', 'certs/ca.pem') }}"
        ca_cert_sha256: "{{ lookup('file', 'certs/ca.sha256') }}"

    - name: Add CA Certificate
      ansible.platform.ca_certificate:
        name: "Production CA"
        pem_data: "{{ ca_cert_pem }}"
        sha256: "{{ ca_cert_sha256 }}"
        state: present
      register: ca_result

    - name: Print certificate ID
      debug:
        msg: "Created CA certificate with ID: {{ ca_result.ca_certificate.id }}"

    - name: Add CA Certificate with EDA tracking
      ansible.platform.ca_certificate:
        name: "EDA CA Certificate"
        pem_data: "{{ lookup('file', 'certs/eda_ca.pem') }}"
        sha256: "b2c3d4e5f6789012345678901234567890123456789012345678901234567890a1"
        related_id_reference: "12345678-1234-1234-1234-123456789012"
        state: present

    - name: Remove outdated certificate
      ansible.platform.ca_certificate:
        name: "Old CA Certificate"
        state: absent
```

## Common patterns

### Batch import certificates

```yaml
- name: Import multiple CA certificates
  ansible.platform.ca_certificate:
    name: "{{ item.name }}"
    pem_data: "{{ item.pem_data }}"
    sha256: "{{ item.sha256 }}"
    state: present
  loop:
    - name: "Internal CA"
      pem_data: "{{ lookup('file', 'certs/internal.pem') }}"
      sha256: "hash1"
    - name: "External CA"
      pem_data: "{{ lookup('file', 'certs/external.pem') }}"
      sha256: "hash2"
  register: cert_results

- name: Print all certificate IDs
  debug:
    msg: "{{ cert_results.results | map(attribute='ca_certificate.id') | list }}"
```

### Verify certificate before import

```yaml
- name: Check if certificate already exists
  ansible.platform.ca_certificate:
    name: "Production CA"
    state: exists
  register: existing_cert

- name: Update certificate if hashes differ
  ansible.platform.ca_certificate:
    name: "Production CA"
    pem_data: "{{ new_cert_pem }}"
    sha256: "{{ new_cert_sha256 }}"
    state: present
  when: existing_cert.ca_certificate.sha256 != new_cert_sha256
```
