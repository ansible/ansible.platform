# Module Documentation: ansible.platform.ca_certificate

**Status:** NEW in 2.7 (ANSTRAT-1640)
**Module:** `ansible.platform.ca_certificate`

---

## Summary

The `ca_certificate` module is **NEW in 2.7**. It manages CA certificates in the platform for SSL/TLS verification. No migration needed from 2.6 (module did not exist).

This module handles:
- Creating and updating CA certificates
- Managing PEM-encoded certificate data
- Tracking certificate SHA256 fingerprints
- Linking to external credential systems (EDA)

---

## 1. Module Arguments

| Argument | Type | Required | Choices / Default | Description |
|----------|------|----------|-------------------|-------------|
| `name` | str | **yes** | — | CA certificate name (unique) |
| `pem_data` | str | no | — | PEM-encoded certificate data |
| `sha256` | str | no | — | SHA256 fingerprint of the certificate |
| `related_id_reference` | str | no | — | UUID for EDA credential tracking |
| `state` | str | no | `present` (default), `absent`, `exists` | Desired state |

---

## 2. Result Structure

### After (2.7.x) — nested under `ca_certificate` key

```json
{
    "changed": true,
    "ca_certificate": {
        "id": 3,
        "name": "My CA Certificate",
        "pem_data": "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----",
        "sha256": "a1b2c3d4e5f6789012345678901234567890123456789012345678901234567890",
        "related_id_reference": null,
        "created": "2025-04-06T12:34:56.000Z",
        "modified": "2025-04-06T12:34:56.000Z"
    },
}
```

### Result Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Numeric primary key assigned by the gateway |
| `name` | str | The certificate name |
| `pem_data` | str | The PEM-encoded certificate content |
| `sha256` | str | The SHA256 fingerprint hash |
| `related_id_reference` | str or null | UUID reference to external credential (if set) |
| `created` | str | ISO 8601 timestamp when record was created |
| `modified` | str | ISO 8601 timestamp of last modification |

---

## 3. Documentation

The module documentation includes:
- Examples of loading certificates from files
- SHA256 fingerprint calculation
- EDA integration with UUID references
- State descriptions

---

## 4. Examples

```yaml
# Create CA certificate from file
- name: Add a CA Certificate
  ansible.platform.ca_certificate:
    name: "My CA Certificate"
    pem_data: "{{ lookup('file', 'ca_cert.pem') }}"
    sha256: "a1b2c3d4e5f6789012345678901234567890123456789012345678901234567890"
    state: present
  register: created_cert

# Create with EDA credential tracking
- name: Add a CA Certificate with EDA reference
  ansible.platform.ca_certificate:
    name: "EDA CA Certificate"
    pem_data: "{{ lookup('file', 'eda_ca_cert.pem') }}"
    sha256: "b2c3d4e5f6789012345678901234567890123456789012345678901234567890a1"
    related_id_reference: "12345678-1234-1234-1234-123456789012"
    state: present

# Verify certificate exists
- name: Check if certificate exists
  ansible.platform.ca_certificate:
    name: "My CA Certificate"
    state: exists
  register: cert_check
```

---

## 5. Internal Implementation

| Aspect | Details |
|--------|---------|
| Execution | Action plugin via manager process |
| Module type | Doc-only stub (2.7) |
| Dataclass | `AnsibleCACertificate` |
| Lookup field | `name` |

---

## 6. Notes

- **New in 2.7:** This module did not exist in 2.6
- **No migration needed:** If you're upgrading from 2.6, this module provides new functionality
- **Certificate validation:** Both pem_data and sha256 should be provided for new certificates
- **File loading:** Use `lookup('file', 'path/to/cert.pem')` to load from files
- **Fingerprint:** SHA256 can be calculated with `openssl x509 -noout -fingerprint -sha256 -in cert.pem`

---

## 7. First-use Checklist

- [ ] Prepare PEM-encoded certificate data
- [ ] Calculate SHA256 fingerprint of the certificate
- [ ] Test with a non-production certificate first
- [ ] If using EDA integration, prepare UUID reference
- [ ] Check result at `result.ca_certificate.*` (nested key structure)
