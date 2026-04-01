#!/usr/bin/env python3
"""
tools/generate_integration_tests.py
====================================
Generates molecule integration-test scenarios for ansible.platform modules.

Each generated scenario covers all supported states in order:
  merged → replaced → overridden → gathered → deleted

The generator reads the Ansible model class to discover:
  - MODULE_NAME        (e.g. "team")
  - CANONICAL_KEY      (e.g. "name", "username", or None)
  - SUPPORTS_DELETE    (bool)
  - VALID_STATES       (frozenset)

And uses a per-module fixture map (FIXTURES) to produce meaningful test data
instead of generic placeholder values.

Usage
-----
  # Generate one module:
  python tools/generate_integration_tests.py team

  # Generate all modules:
  python tools/generate_integration_tests.py --all

  # Dry-run (print converge.yml to stdout):
  python tools/generate_integration_tests.py team --dry-run

  # Overwrite existing scenarios:
  python tools/generate_integration_tests.py team --force

Output
------
  extensions/molecule/<module>_integration/
    molecule.yml  inventory.yml  converge.yml  verify.yml  cleanup.yml

Skipped automatically:
  - Modules with CANONICAL_KEY=None (singleton/category-C: settings,
    role_team_assignment, role_user_assignment)
  - Modules without a FIXTURES entry
  - Modules already having a hand-crafted scenario (unless --force)
"""

from __future__ import annotations

import argparse
import importlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import jinja2

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
COLLECTION_ROOT = Path(__file__).resolve().parent.parent
MOLECULE_DIR = COLLECTION_ROOT / "extensions" / "molecule"
MODELS_PKG = "plugins.plugin_utils.ansible_models"

# Scenarios already hand-crafted — skip unless --force
HAND_CRAFTED = {"organization", "user"}

# ---------------------------------------------------------------------------
# Per-module fixture data
# ---------------------------------------------------------------------------

@dataclass
class ModuleFixture:
    """Test data for one module."""
    canonical_field: str          # e.g. "name" or "username"
    prefix: str                   # used in before-empty assertions, e.g. "int-team-"
    resources: List[Dict]         # [r0, r1] — 2 primary test resources
    update_config: Dict           # partial update applied to r0 in merged test
    replaced_config: Dict         # full object sent for replaced test on r0
    extra_seeds: List[Dict]       # seeded before overridden test (must be deleted)
    supports_delete: bool = True
    supports_overridden: bool = True
    # Prerequisite support — for modules that depend on another resource existing first
    # (e.g. authenticator_map requires an authenticator).
    prepare_all_states: bool = False   # generate prepare.yml for ALL states, not just the usual ones
    prereq_yaml: str = ""              # indented YAML task(s) to prepend to prepare.yml tasks section
    cleanup_prereq_yaml: str = ""      # indented YAML task(s) to append to cleanup.yml (remove prereq)


FIXTURES: Dict[str, ModuleFixture] = {
    "organization": ModuleFixture(
        canonical_field="name",
        prefix="int-org-",
        resources=[
            {"name": "int-org-alpha", "description": "Alpha initial"},
            {"name": "int-org-beta",  "description": "Beta initial"},
        ],
        update_config={"name": "int-org-alpha", "description": "Alpha updated"},
        replaced_config={"name": "int-org-alpha", "description": "Alpha replaced"},
        extra_seeds=[
            {"name": "int-org-gamma", "description": "Gamma seed"},
            {"name": "int-org-delta", "description": "Delta seed"},
        ],
    ),
    "user": ModuleFixture(
        canonical_field="username",
        prefix="int-user-",
        resources=[
            {
                "username": "int-user-alice",
                "first_name": "Alice",
                "last_name": "Smith",
                "email": "int-alice@test.example",
                "password": "TestPass123!",
                "is_superuser": False,
            },
            {
                "username": "int-user-bob",
                "first_name": "Bob",
                "last_name": "Jones",
                "email": "int-bob@test.example",
                "password": "TestPass123!",
                "is_superuser": False,
            },
        ],
        update_config={
            "username": "int-user-alice",
            "last_name": "Johnson",
            "email": "int-alice-updated@test.example",
        },
        replaced_config={
            "username": "int-user-alice",
            "first_name": "Alice",
            "last_name": "Johnson",
            "email": "int-alice-updated@test.example",
            "is_superuser": True,
        },
        extra_seeds=[
            {
                "username": "int-user-carol",
                "first_name": "Carol",
                "last_name": "White",
                "email": "int-carol@test.example",
                "password": "TestPass123!",
                "is_superuser": False,
            },
            {
                "username": "int-user-dave",
                "first_name": "Dave",
                "last_name": "Brown",
                "email": "int-dave@test.example",
                "password": "TestPass123!",
                "is_superuser": False,
            },
        ],
    ),
    "team": ModuleFixture(
        canonical_field="name",
        prefix="int-team-",
        resources=[
            {"name": "int-team-alpha", "description": "Alpha team initial"},
            {"name": "int-team-beta",  "description": "Beta team initial"},
        ],
        update_config={"name": "int-team-alpha", "description": "Alpha team updated"},
        replaced_config={"name": "int-team-alpha", "description": "Alpha team replaced"},
        extra_seeds=[
            {"name": "int-team-gamma", "description": "Gamma seed"},
            {"name": "int-team-delta", "description": "Delta seed"},
        ],
    ),
    "role_definition": ModuleFixture(
        canonical_field="name",
        prefix="int-roledef-",
        resources=[
            {
                "name": "int-roledef-alpha",
                "description": "Alpha role definition",
                "content_type": "shared.team",
                "permissions": ["view_organization"],
            },
            {
                "name": "int-roledef-beta",
                "description": "Beta role definition",
                "content_type": "shared.team",
                "permissions": ["view_organization"],
            },
        ],
        update_config={"name": "int-roledef-alpha", "description": "Alpha role definition updated"},
        replaced_config={
            "name": "int-roledef-alpha",
            "description": "Alpha role definition replaced",
            "content_type": "shared.team",
            "permissions": ["view_organization"],
        },
        extra_seeds=[
            {
                "name": "int-roledef-gamma",
                "description": "Gamma seed",
                "content_type": "shared.team",
                "permissions": ["view_organization"],
            },
        ],
    ),
    "token": ModuleFixture(
        canonical_field="name",
        prefix="int-token-",
        resources=[
            {"name": "int-token-alpha", "description": "Alpha token", "scope": "read"},
            {"name": "int-token-beta",  "description": "Beta token",  "scope": "read"},
        ],
        update_config={"name": "int-token-alpha", "description": "Alpha token updated"},
        replaced_config={"name": "int-token-alpha", "description": "Alpha token replaced", "scope": "write"},
        extra_seeds=[
            {"name": "int-token-gamma", "description": "Gamma seed", "scope": "read"},
        ],
    ),
    "application": ModuleFixture(
        canonical_field="name",
        prefix="int-app-",
        # organization: 1 = "Default" org, always seeded by mock_gateway_server.seed_defaults()
        resources=[
            {"name": "int-app-alpha", "description": "Alpha application", "organization": 1},
            {"name": "int-app-beta",  "description": "Beta application",  "organization": 1},
        ],
        update_config={"name": "int-app-alpha", "description": "Alpha application updated", "organization": 1},
        replaced_config={"name": "int-app-alpha", "description": "Alpha application replaced", "organization": 1},
        extra_seeds=[
            {"name": "int-app-gamma", "description": "Gamma seed", "organization": 1},
        ],
    ),
    "service_cluster": ModuleFixture(
        canonical_field="name",
        prefix="int-cluster-",
        resources=[
            {"name": "int-cluster-alpha"},
            {"name": "int-cluster-beta"},
        ],
        update_config={"name": "int-cluster-alpha"},
        replaced_config={"name": "int-cluster-alpha"},
        extra_seeds=[{"name": "int-cluster-gamma"}],
    ),
    "service_type": ModuleFixture(
        canonical_field="name",
        prefix="int-stype-",
        resources=[
            {"name": "int-stype-alpha"},
            {"name": "int-stype-beta"},
        ],
        update_config={"name": "int-stype-alpha"},
        replaced_config={"name": "int-stype-alpha"},
        extra_seeds=[{"name": "int-stype-gamma"}],
    ),
    "http_port": ModuleFixture(
        canonical_field="name",
        prefix="int-port-",
        resources=[
            {"name": "int-port-alpha"},
            {"name": "int-port-beta"},
        ],
        update_config={"name": "int-port-alpha"},
        replaced_config={"name": "int-port-alpha"},
        extra_seeds=[{"name": "int-port-gamma"}],
    ),
    "route": ModuleFixture(
        canonical_field="name",
        prefix="int-route-",
        resources=[
            {"name": "int-route-alpha"},
            {"name": "int-route-beta"},
        ],
        update_config={"name": "int-route-alpha"},
        replaced_config={"name": "int-route-alpha"},
        extra_seeds=[{"name": "int-route-gamma"}],
    ),
    "ui_plugin_route": ModuleFixture(
        canonical_field="name",
        prefix="int-uipr-",
        resources=[
            {"name": "int-uipr-alpha"},
            {"name": "int-uipr-beta"},
        ],
        update_config={"name": "int-uipr-alpha"},
        replaced_config={"name": "int-uipr-alpha"},
        extra_seeds=[{"name": "int-uipr-gamma"}],
    ),
    "ca_certificate": ModuleFixture(
        canonical_field="name",
        prefix="int-cert-",
        resources=[
            {"name": "int-cert-alpha"},
            {"name": "int-cert-beta"},
        ],
        update_config={"name": "int-cert-alpha"},
        replaced_config={"name": "int-cert-alpha"},
        extra_seeds=[{"name": "int-cert-gamma"}],
    ),
    "authenticator": ModuleFixture(
        canonical_field="name",
        prefix="int-auth-",
        resources=[
            {"name": "int-auth-alpha", "type": "ansible_base.authentication.authenticator_plugins.local", "enabled": True},
            {"name": "int-auth-beta",  "type": "ansible_base.authentication.authenticator_plugins.local", "enabled": True},
        ],
        # enabled: False differs from seeded enabled: True — triggers changed=True in merged/check tests
        update_config={"name": "int-auth-alpha", "enabled": False},
        replaced_config={"name": "int-auth-alpha", "type": "ansible_base.authentication.authenticator_plugins.local", "enabled": True},
        extra_seeds=[
            {"name": "int-auth-gamma", "type": "ansible_base.authentication.authenticator_plugins.local", "enabled": True},
        ],
    ),
    "authenticator_map": ModuleFixture(
        canonical_field="name",
        prefix="int-authmap-",
        # authenticator: 3100 = first ID in mock server's authenticator range (start_id=3100).
        # The prereq_yaml below creates "int-prereq-authn" which gets ID 3100 on a fresh mock server.
        resources=[
            {"name": "int-authmap-alpha", "authenticator": 3100},
            {"name": "int-authmap-beta",  "authenticator": 3100},
        ],
        update_config={"name": "int-authmap-alpha", "authenticator": 3100},
        replaced_config={"name": "int-authmap-alpha", "authenticator": 3100},
        extra_seeds=[{"name": "int-authmap-gamma", "authenticator": 3100}],
        prepare_all_states=True,
        prereq_yaml="""\
  - name: Seed prerequisite authenticator (required by all authenticator_map tests)
    ansible.platform.authenticator:
      config:
      - name: "int-prereq-authn"
        type: "ansible_base.authentication.authenticator_plugins.local"
      state: merged
      gateway_hostname: "{{ gateway_hostname }}"
      gateway_username: "{{ gateway_username }}"
      gateway_password: "{{ gateway_password }}"
      gateway_validate_certs: "{{ gateway_validate_certs }}"
""",
        cleanup_prereq_yaml="""\
  - name: Remove prerequisite authenticator (test teardown)
    ansible.platform.authenticator:
      config:
      - name: "int-prereq-authn"
      state: deleted
      gateway_hostname: "{{ gateway_hostname }}"
      gateway_username: "{{ gateway_username }}"
      gateway_password: "{{ gateway_password }}"
      gateway_validate_certs: "{{ gateway_validate_certs }}"
    ignore_errors: true
""",
    ),
    "service": ModuleFixture(
        canonical_field="name",
        prefix="int-svc-",
        resources=[
            {"name": "int-svc-alpha"},
            {"name": "int-svc-beta"},
        ],
        update_config={"name": "int-svc-alpha"},
        replaced_config={"name": "int-svc-alpha"},
        extra_seeds=[{"name": "int-svc-gamma"}],
    ),
    "service_key": ModuleFixture(
        canonical_field="name",
        prefix="int-skey-",
        resources=[
            {"name": "int-skey-alpha"},
            {"name": "int-skey-beta"},
        ],
        update_config={"name": "int-skey-alpha"},
        replaced_config={"name": "int-skey-alpha"},
        extra_seeds=[{"name": "int-skey-gamma"}],
    ),
    "service_node": ModuleFixture(
        canonical_field="name",
        prefix="int-snode-",
        resources=[
            {"name": "int-snode-alpha"},
            {"name": "int-snode-beta"},
        ],
        update_config={"name": "int-snode-alpha"},
        replaced_config={"name": "int-snode-alpha"},
        extra_seeds=[{"name": "int-snode-gamma"}],
    ),
}


# ---------------------------------------------------------------------------
# Model introspection
# ---------------------------------------------------------------------------

def load_model_class(module_name: str):
    sys.path.insert(0, str(COLLECTION_ROOT))
    model_module = f"{MODELS_PKG}.{module_name}"
    class_name = "Ansible" + "".join(p.capitalize() for p in module_name.split("_"))
    try:
        mod = importlib.import_module(model_module)
        return getattr(mod, class_name)
    except (ModuleNotFoundError, AttributeError) as exc:
        raise SystemExit(f"Cannot load model for '{module_name}': {exc}") from exc


def get_all_module_names() -> List[str]:
    models_dir = COLLECTION_ROOT / "plugins" / "plugin_utils" / "ansible_models"
    return sorted(
        p.stem
        for p in models_dir.glob("*.py")
        if not p.stem.startswith("_") and p.stem != "base_transform"
    )


# ---------------------------------------------------------------------------
# Jinja2 template helpers
# ---------------------------------------------------------------------------

def _yaml_val(v: Any) -> str:
    """Render a Python value as inline YAML (for assert that: lines)."""
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, str):
        return f"'{v}'"
    return str(v)


def _config_to_yaml(config: dict, base_indent: int) -> str:
    """Render a dict as a YAML list item with correct indentation.

    base_indent: number of spaces before the opening '- ' marker.
    e.g. base_indent=8 → first key at col 8 ('        - key: val')
    """
    pad = " " * base_indent
    item_pad = " " * (base_indent + 2)
    lines = []
    for i, (k, v) in enumerate(config.items()):
        prefix = f"{pad}- " if i == 0 else item_pad
        if isinstance(v, bool):
            lines.append(f"{prefix}{k}: {str(v).lower()}")
        elif isinstance(v, list):
            lines.append(f"{prefix}{k}:")
            for item in v:
                lines.append(f"{item_pad}  - {item}")
        elif isinstance(v, str):
            lines.append(f"{prefix}{k}: \"{v}\"")
        else:
            lines.append(f"{prefix}{k}: {v}")
    return "\n".join(lines)


def _configs_to_yaml(configs: List[dict], base_indent: int) -> str:
    return "\n".join(_config_to_yaml(c, base_indent) for c in configs)


def _diff_field(r0: dict, update: dict, cf: str):
    """Find the first field that differs between r0 and update (excluding canonical field)."""
    for k in update:
        if k != cf and k in r0 and update[k] != r0.get(k):
            return k
    for k in update:
        if k != cf:
            return k
    return None


# ---------------------------------------------------------------------------
# Jinja2 templates
# ---------------------------------------------------------------------------

CONVERGE_TEMPLATE = """\
---
# ============================================================================
# Integration test: ansible.platform.{{ module_name }}
# Covers all supported resource-module states:
#   merged → replaced → overridden → gathered → deleted
# Runs against the mock Gateway (no real AAP required).
# Connection-mode coverage is owned by {{ module_name }}_mock.
# ============================================================================

# ============================================================================
# Play 0 — Setup: wait for mock Gateway
# ============================================================================
- name: "Setup — wait for mock Gateway"
  hosts: localhost
  connection: local
  gather_facts: false
  vars:
    gateway_hostname: "http://127.0.0.1:8000"
  tasks:
    - name: "Wait for mock Gateway health endpoint"
      ansible.builtin.uri:
        url: "{{ '{{' }} gateway_hostname {{ '}}' }}/health"
        method: GET
        status_code: 200
      register: health
      retries: 12
      delay: 5
      until: health.status == 200

    - name: "Ensure /tmp/ap directory exists"
      ansible.builtin.file:
        path: /tmp/ap
        state: directory
        mode: "0755"

    - name: "Create manager survive flag"
      ansible.builtin.file:
        path: /tmp/ap/.survive
        state: touch
        mode: "0600"

{% if 'merged' in valid_states %}
# ============================================================================
# Play 1 — state: merged  (CREATE + UPDATE + idempotency)
# Starting state: empty
# Creates {{ r0_key }} and {{ r1_key }}, then updates {{ r0_key }}.
# {{ r1_key }} must remain untouched during the update.
# ============================================================================
- name: "Integration — {{ module_name }} state:merged"
  hosts: localhost
  connection: local
  gather_facts: false
  vars:
    gateway_hostname: "http://127.0.0.1:8000"
    gateway_username: mock
    gateway_password: testpass
    gateway_validate_certs: false
  tasks:
    # ── CREATE ──────────────────────────────────────────────────────────────
    - name: "merged | CREATE {{ r0_key }} and {{ r1_key }}"
      ansible.platform.{{ module_name }}:
        config:
{{ resources_yaml }}
        state: merged
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      register: create_result
      vars:
        ansible_connection: local

    - name: "merged | Assert create reported changed"
      ansible.builtin.assert:
        that:
          - create_result is changed
        fail_msg: "merged create should report changed. got: {{ '{{' }} create_result {{ '}}' }}"

    - name: "merged | Assert before had no {{ prefix }}* resources (starting from clean state)"
      ansible.builtin.assert:
        that:
          - create_result.before | selectattr('{{ cf }}', 'search', '^{{ prefix }}') | list | length == 0
        fail_msg: "before should be empty. before={{ '{{' }} create_result.before {{ '}}' }}"

    - name: "merged | Assert after contains both created resources"
      ansible.builtin.assert:
        that:
          - create_result.after | selectattr('{{ cf }}', 'equalto', '{{ r0_key }}') | list | length == 1
          - create_result.after | selectattr('{{ cf }}', 'equalto', '{{ r1_key }}') | list | length == 1
        fail_msg: "after should contain {{ r0_key }} and {{ r1_key }}. after={{ '{{' }} create_result.after {{ '}}' }}"

    # ── IDEMPOTENT CREATE ──────────────────────────────────────────────────
    - name: "merged | IDEMPOTENT — run create again (no password to avoid false diff)"
      ansible.platform.{{ module_name }}:
        config:
{{ idem_resources_yaml }}
        state: merged
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      register: create_idem
      vars:
        ansible_connection: local

    - name: "merged | Assert idempotent create reported no change"
      ansible.builtin.assert:
        that:
          - create_idem is not changed
        fail_msg: "merged idempotent create should NOT report changed. got: {{ '{{' }} create_idem {{ '}}' }}"

    # ── UPDATE ──────────────────────────────────────────────────────────────
    - name: "merged | UPDATE {{ r0_key }}"
      ansible.platform.{{ module_name }}:
        config:
{{ update_yaml }}
        state: merged
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      register: update_result
      vars:
        ansible_connection: local

    - name: "merged | Assert update reported changed"
      ansible.builtin.assert:
        that:
          - update_result is changed
        fail_msg: "merged update should report changed. got: {{ '{{' }} update_result {{ '}}' }}"

{% if diff_field %}
    - name: "merged | Assert before captured {{ r0_key }}.{{ diff_field }} == {{ diff_v1 | yaml_val }}"
      ansible.builtin.assert:
        that:
          - (update_result.before | selectattr('{{ cf }}', 'equalto', '{{ r0_key }}') | first).{{ diff_field }} == {{ diff_v1 | yaml_val }}
        fail_msg: "before should show old {{ diff_field }} for {{ r0_key }}. before={{ '{{' }} update_result.before {{ '}}' }}"

    - name: "merged | Assert after shows {{ r0_key }}.{{ diff_field }} == {{ diff_v2 | yaml_val }}"
      ansible.builtin.assert:
        that:
          - (update_result.after | selectattr('{{ cf }}', 'equalto', '{{ r0_key }}') | first).{{ diff_field }} == {{ diff_v2 | yaml_val }}
        fail_msg: "after should show new {{ diff_field }} for {{ r0_key }}. after={{ '{{' }} update_result.after {{ '}}' }}"
{% else %}
    - name: "merged | Assert {{ r0_key }} is present in after"
      ansible.builtin.assert:
        that:
          - update_result.after | selectattr('{{ cf }}', 'equalto', '{{ r0_key }}') | list | length == 1
        fail_msg: "after should contain {{ r0_key }}. after={{ '{{' }} update_result.after {{ '}}' }}"
{% endif %}

    - name: "merged | VERIFY {{ r1_key }} is untouched (gather — not in update config)"
      ansible.platform.{{ module_name }}:
        config:
          - {{ cf }}: "{{ r1_key }}"
        state: gathered
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      register: r1_check_merged
      vars:
        ansible_connection: local

    - name: "merged | Assert {{ r1_key }} is untouched (not in update config)"
      ansible.builtin.assert:
        that:
          - r1_check_merged.gathered | length == 1
          - r1_check_merged.gathered[0].{{ cf }} == '{{ r1_key }}'
        fail_msg: "merged must not affect {{ r1_key }}. gathered={{ '{{' }} r1_check_merged.gathered {{ '}}' }}"

    # ── IDEMPOTENT UPDATE ──────────────────────────────────────────────────
    - name: "merged | IDEMPOTENT — run update again"
      ansible.platform.{{ module_name }}:
        config:
{{ update_yaml }}
        state: merged
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      register: update_idem
      vars:
        ansible_connection: local

    - name: "merged | Assert idempotent update reported no change"
      ansible.builtin.assert:
        that:
          - update_idem is not changed
        fail_msg: "merged idempotent update should NOT report changed. got: {{ '{{' }} update_idem {{ '}}' }}"

{% endif %}
{% if 'replaced' in valid_states and canonical_key %}
# ============================================================================
# Play 2 — state: replaced  (ITEM-LEVEL REPLACEMENT + idempotency)
# {{ r1_key }} is NOT in config → must be preserved (replaced ≠ overridden)
# ============================================================================
- name: "Integration — {{ module_name }} state:replaced"
  hosts: localhost
  connection: local
  gather_facts: false
  vars:
    gateway_hostname: "http://127.0.0.1:8000"
    gateway_username: mock
    gateway_password: testpass
    gateway_validate_certs: false
  tasks:
    - name: "replaced | REPLACE {{ r0_key }} (full object replacement)"
      ansible.platform.{{ module_name }}:
        config:
{{ replaced_yaml }}
        state: replaced
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      register: replaced_result
      vars:
        ansible_connection: local

    - name: "replaced | Assert replace reported changed"
      ansible.builtin.assert:
        that:
          - replaced_result is changed
        fail_msg: "replaced should report changed. got: {{ '{{' }} replaced_result {{ '}}' }}"

{% if replaced_diff_field %}
    - name: "replaced | Assert before shows pre-replace {{ r0_key }}.{{ replaced_diff_field }} == {{ replaced_v1 | yaml_val }}"
      ansible.builtin.assert:
        that:
          - (replaced_result.before | selectattr('{{ cf }}', 'equalto', '{{ r0_key }}') | first).{{ replaced_diff_field }} == {{ replaced_v1 | yaml_val }}
        fail_msg: "before should show old value for {{ r0_key }}. before={{ '{{' }} replaced_result.before {{ '}}' }}"

    - name: "replaced | Assert after shows {{ r0_key }}.{{ replaced_diff_field }} == {{ replaced_v2 | yaml_val }}"
      ansible.builtin.assert:
        that:
          - (replaced_result.after | selectattr('{{ cf }}', 'equalto', '{{ r0_key }}') | first).{{ replaced_diff_field }} == {{ replaced_v2 | yaml_val }}
        fail_msg: "after should show replaced value for {{ r0_key }}. after={{ '{{' }} replaced_result.after {{ '}}' }}"
{% endif %}

    - name: "replaced | VERIFY {{ r1_key }} still present (gather — item-level, not set-level)"
      ansible.platform.{{ module_name }}:
        config:
          - {{ cf }}: "{{ r1_key }}"
        state: gathered
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      register: r1_check_replaced
      vars:
        ansible_connection: local

    - name: "replaced | Assert {{ r1_key }} still present and untouched (item-level, not set-level)"
      ansible.builtin.assert:
        that:
          - r1_check_replaced.gathered | length == 1
          - r1_check_replaced.gathered[0].{{ cf }} == '{{ r1_key }}'
        fail_msg: "replaced must NOT delete {{ r1_key }}. gathered={{ '{{' }} r1_check_replaced.gathered {{ '}}' }}"

    - name: "replaced | IDEMPOTENT — run replace again"
      ansible.platform.{{ module_name }}:
        config:
{{ replaced_yaml }}
        state: replaced
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      register: replaced_idem
      vars:
        ansible_connection: local

    - name: "replaced | Assert idempotent replace reported no change"
      ansible.builtin.assert:
        that:
          - replaced_idem is not changed
        fail_msg: "replaced idempotent run should NOT report changed. got: {{ '{{' }} replaced_idem {{ '}}' }}"

{% endif %}
{% if 'overridden' in valid_states and canonical_key %}
# ============================================================================
# Play 3 — state: overridden  (SET-LEVEL ENFORCEMENT + idempotency)
# Seeds {{ extra_seeds | length }} extra resource(s) that overridden must delete.
# After override: only {{ r0_key }} and {{ r1_key }} must remain.
# ============================================================================
- name: "Integration — {{ module_name }} state:overridden"
  hosts: localhost
  connection: local
  gather_facts: false
  vars:
    gateway_hostname: "http://127.0.0.1:8000"
    gateway_username: mock
    gateway_password: testpass
    gateway_validate_certs: false
  tasks:
    - name: "overridden | SEED extra resources (overridden must delete these)"
      ansible.platform.{{ module_name }}:
        config:
{{ seeds_yaml }}
        state: merged
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      register: seed_result
      vars:
        ansible_connection: local

    - name: "overridden | Assert seed created extra resources"
      ansible.builtin.assert:
        that:
          - seed_result is changed
        fail_msg: "Seed step failed. got: {{ '{{' }} seed_result {{ '}}' }}"

    # State now: {{ r0_key }}, {{ r1_key }}, {% for s in extra_seeds %}{{ s[cf] }}{% if not loop.last %}, {% endif %}{% endfor %} ({{ 2 + extra_seeds | length }} total)

    - name: "overridden | OVERRIDE to exactly [{{ r0_key }}, {{ r1_key }}]"
      ansible.platform.{{ module_name }}:
        config:
{{ override_yaml }}
        state: overridden
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      register: overridden_result
      vars:
        ansible_connection: local

    - name: "overridden | Assert override reported changed"
      ansible.builtin.assert:
        that:
          - overridden_result is changed
        fail_msg: "overridden should report changed. got: {{ '{{' }} overridden_result {{ '}}' }}"

    - name: "overridden | Assert before had all {{ 2 + extra_seeds | length }} {{ prefix }}* resources"
      ansible.builtin.assert:
        that:
          - overridden_result.before | selectattr('{{ cf }}', 'search', '^{{ prefix }}') | list | length == {{ 2 + extra_seeds | length }}
        fail_msg: "before should show all {{ 2 + extra_seeds | length }} resources. before={{ '{{' }} overridden_result.before {{ '}}' }}"

    - name: "overridden | Assert after contains ONLY {{ r0_key }} and {{ r1_key }}"
      ansible.builtin.assert:
        that:
          - overridden_result.after | selectattr('{{ cf }}', 'equalto', '{{ r0_key }}') | list | length == 1
          - overridden_result.after | selectattr('{{ cf }}', 'equalto', '{{ r1_key }}') | list | length == 1
{% for s in extra_seeds %}
          - overridden_result.after | selectattr('{{ cf }}', 'equalto', '{{ s[cf] }}') | list | length == 0
{% endfor %}
          - overridden_result.after | selectattr('{{ cf }}', 'search', '^{{ prefix }}') | list | length == 2
        fail_msg: >-
          after should contain ONLY {{ r0_key }} and {{ r1_key }}.
          Seeded extras should be deleted.
          after={{ '{{' }} overridden_result.after {{ '}}' }}

    - name: "overridden | IDEMPOTENT — run override again"
      ansible.platform.{{ module_name }}:
        config:
{{ override_yaml }}
        state: overridden
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      register: overridden_idem
      vars:
        ansible_connection: local

    - name: "overridden | Assert idempotent override reported no change"
      ansible.builtin.assert:
        that:
          - overridden_idem is not changed
        fail_msg: "overridden idempotent run should NOT report changed. got: {{ '{{' }} overridden_idem {{ '}}' }}"

{% endif %}
{% if 'gathered' in valid_states %}
# ============================================================================
# Play 4 — state: gathered  (READ-ONLY — 3 cases)
# ============================================================================
- name: "Integration — {{ module_name }} state:gathered"
  hosts: localhost
  connection: local
  gather_facts: false
  vars:
    gateway_hostname: "http://127.0.0.1:8000"
    gateway_username: mock
    gateway_password: testpass
    gateway_validate_certs: false
  tasks:
    # ── case A: gather all ─────────────────────────────────────────────────
    - name: "gathered | A) Gather ALL {{ module_name }} resources"
      ansible.platform.{{ module_name }}:
        config: []
        state: gathered
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      register: gathered_all
      vars:
        ansible_connection: local

    - name: "gathered | Assert gather-all returned expected resources (changed=false)"
      ansible.builtin.assert:
        that:
          - gathered_all is not changed
          - gathered_all is not failed
          - gathered_all.gathered | selectattr('{{ cf }}', 'equalto', '{{ r0_key }}') | list | length == 1
          - gathered_all.gathered | selectattr('{{ cf }}', 'equalto', '{{ r1_key }}') | list | length == 1
        fail_msg: >-
          gather-all should return {{ r0_key }} and {{ r1_key }}, changed=false.
          gathered={{ '{{' }} gathered_all.gathered {{ '}}' }}

    # ── case B: gather specific ────────────────────────────────────────────
    - name: "gathered | B) Gather {{ r0_key }} by {{ cf }}"
      ansible.platform.{{ module_name }}:
        config:
          - {{ cf }}: "{{ r0_key }}"
        state: gathered
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      register: gathered_one
      vars:
        ansible_connection: local

    - name: "gathered | Assert specific gather returned exactly {{ r0_key }}"
      ansible.builtin.assert:
        that:
          - gathered_one is not changed
          - gathered_one is not failed
          - gathered_one.gathered | length == 1
          - gathered_one.gathered[0].{{ cf }} == '{{ r0_key }}'
        fail_msg: >-
          gathered by {{ cf }} should return exactly 1 result for {{ r0_key }}.
          gathered={{ '{{' }} gathered_one.gathered {{ '}}' }}

    # ── case C: gather non-existent ────────────────────────────────────────
    - name: "gathered | C) Gather resource that does not exist"
      ansible.platform.{{ module_name }}:
        config:
          - {{ cf }}: "{{ prefix }}does-not-exist"
        state: gathered
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      register: gathered_missing
      vars:
        ansible_connection: local

    - name: "gathered | Assert missing resource returns empty list (not a failure)"
      ansible.builtin.assert:
        that:
          - gathered_missing is not changed
          - gathered_missing is not failed
          - gathered_missing.gathered | length == 0
        fail_msg: >-
          gathered for missing resource should return empty list.
          gathered={{ '{{' }} gathered_missing.gathered {{ '}}' }}

{% endif %}
{% if 'deleted' in valid_states and supports_delete %}
# ============================================================================
# Play 5 — state: deleted  (3 cases: delete / idempotent / non-existent)
# {{ r1_key }} is left for cleanup to verify.
# ============================================================================
- name: "Integration — {{ module_name }} state:deleted"
  hosts: localhost
  connection: local
  gather_facts: false
  vars:
    gateway_hostname: "http://127.0.0.1:8000"
    gateway_username: mock
    gateway_password: testpass
    gateway_validate_certs: false
  tasks:
    # ── case A: delete existing resource ──────────────────────────────────
    - name: "deleted | A) DELETE {{ r0_key }}"
      ansible.platform.{{ module_name }}:
        config:
          - {{ cf }}: "{{ r0_key }}"
        state: deleted
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      register: deleted_result
      vars:
        ansible_connection: local

    - name: "deleted | Assert delete reported changed"
      ansible.builtin.assert:
        that:
          - deleted_result is changed
        fail_msg: "deleted should report changed. got: {{ '{{' }} deleted_result {{ '}}' }}"

    - name: "deleted | Assert before shows {{ r0_key }} was present before deletion"
      ansible.builtin.assert:
        that:
          - deleted_result.before | selectattr('{{ cf }}', 'equalto', '{{ r0_key }}') | list | length == 1
        fail_msg: "before should contain {{ r0_key }}. before={{ '{{' }} deleted_result.before {{ '}}' }}"

    - name: "deleted | Assert after does not contain {{ r0_key }}"
      ansible.builtin.assert:
        that:
          - deleted_result.after | selectattr('{{ cf }}', 'equalto', '{{ r0_key }}') | list | length == 0
        fail_msg: "after should NOT contain {{ r0_key }}. after={{ '{{' }} deleted_result.after {{ '}}' }}"

    - name: "deleted | VERIFY {{ r1_key }} still present (gather — delete is selective)"
      ansible.platform.{{ module_name }}:
        config:
          - {{ cf }}: "{{ r1_key }}"
        state: gathered
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      register: r1_check_deleted
      vars:
        ansible_connection: local

    - name: "deleted | Assert {{ r1_key }} still present (delete is selective)"
      ansible.builtin.assert:
        that:
          - r1_check_deleted.gathered | length == 1
          - r1_check_deleted.gathered[0].{{ cf }} == '{{ r1_key }}'
        fail_msg: "deleted must not remove {{ r1_key }}. gathered={{ '{{' }} r1_check_deleted.gathered {{ '}}' }}"

    # ── case B: idempotent delete ──────────────────────────────────────────
    - name: "deleted | B) IDEMPOTENT — delete {{ r0_key }} again (already gone)"
      ansible.platform.{{ module_name }}:
        config:
          - {{ cf }}: "{{ r0_key }}"
        state: deleted
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      register: deleted_idem
      vars:
        ansible_connection: local

    - name: "deleted | Assert idempotent delete reported no change"
      ansible.builtin.assert:
        that:
          - deleted_idem is not changed
        fail_msg: "deleted idempotent run should NOT report changed. got: {{ '{{' }} deleted_idem {{ '}}' }}"

    # ── case C: delete non-existent resource ──────────────────────────────
    - name: "deleted | C) DELETE resource that was never created"
      ansible.platform.{{ module_name }}:
        config:
          - {{ cf }}: "{{ prefix }}never-existed"
        state: deleted
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      register: deleted_missing
      vars:
        ansible_connection: local

    - name: "deleted | Assert delete of non-existent resource is a no-op"
      ansible.builtin.assert:
        that:
          - deleted_missing is not changed
          - deleted_missing is not failed
        fail_msg: "delete of non-existent resource should not fail. got: {{ '{{' }} deleted_missing {{ '}}' }}"

{% endif %}
...
"""

VERIFY_TEMPLATE = """\
---
# Verify: {{ r1_key }} must still exist; {{ r0_key }} must be gone.
- name: "Verify — final state after all {{ module_name }} integration tests"
  hosts: localhost
  connection: local
  gather_facts: false
  vars:
    gateway_hostname: "http://127.0.0.1:8000"
    gateway_username: mock
    gateway_password: testpass
    gateway_validate_certs: false
  tasks:
    - name: "Verify {{ r1_key }} still exists"
      ansible.platform.{{ module_name }}:
        config:
          - {{ cf }}: "{{ r1_key }}"
        state: gathered
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      register: final_r1
      vars:
        ansible_connection: local

    - name: "Assert {{ r1_key }} exists"
      ansible.builtin.assert:
        that:
          - final_r1.gathered | length == 1
          - final_r1.gathered[0].{{ cf }} == '{{ r1_key }}'
        fail_msg: "{{ r1_key }} should still exist. gathered={{ '{{' }} final_r1.gathered {{ '}}' }}"

    - name: "Verify {{ r0_key }} is gone (was deleted in Play 5)"
      ansible.platform.{{ module_name }}:
        config:
          - {{ cf }}: "{{ r0_key }}"
        state: gathered
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      register: final_r0
      vars:
        ansible_connection: local

    - name: "Assert {{ r0_key }} does not exist"
      ansible.builtin.assert:
        that:
          - final_r0.gathered | length == 0
        fail_msg: "{{ r0_key }} should have been deleted. gathered={{ '{{' }} final_r0.gathered {{ '}}' }}"
...
"""

CLEANUP_TEMPLATE = """\
---
- name: "Cleanup — remove all {{ module_name }} integration test resources"
  hosts: localhost
  connection: local
  gather_facts: false
  vars:
    gateway_hostname: "http://127.0.0.1:8000"
    gateway_username: mock
    gateway_password: testpass
    gateway_validate_certs: false
  tasks:
{% for res in all_resources %}
    - name: "Cleanup: delete {{ res[cf] }}"
      ansible.platform.{{ module_name }}:
        config:
          - {{ cf }}: "{{ res[cf] }}"
        state: deleted
        gateway_hostname: "{{ '{{' }} gateway_hostname {{ '}}' }}"
        gateway_username: "{{ '{{' }} gateway_username {{ '}}' }}"
        gateway_password: "{{ '{{' }} gateway_password {{ '}}' }}"
        gateway_validate_certs: "{{ '{{' }} gateway_validate_certs {{ '}}' }}"
      failed_when: false
      vars:
        ansible_connection: local

{% endfor %}
    - name: "Remove manager survive flag"
      ansible.builtin.file:
        path: /tmp/ap/.survive
        state: absent
      vars:
        ansible_connection: local
...
"""


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def _make_jinja_env() -> jinja2.Environment:
    env = jinja2.Environment(
        keep_trailing_newline=True,
        undefined=jinja2.StrictUndefined,
    )
    env.filters["yaml_val"] = _yaml_val
    return env


def render_converge(module_name: str, cls, fixture: ModuleFixture) -> str:
    env = _make_jinja_env()
    tmpl = env.from_string(CONVERGE_TEMPLATE)

    cf = fixture.canonical_field
    r0 = fixture.resources[0]
    r1 = fixture.resources[1]
    r0_key = r0[cf]
    r1_key = r1[cf]

    # idem resources: strip password (write-only)
    idem_resources = [{k: v for k, v in r.items() if k != "password"} for r in fixture.resources]

    # Diff field for merged update assertions
    diff_field = _diff_field(r0, fixture.update_config, cf)
    diff_v1 = r0.get(diff_field) if diff_field else None
    diff_v2 = fixture.update_config.get(diff_field) if diff_field else None

    # Diff field for replaced assertions
    replaced_diff_field = _diff_field(r0, fixture.replaced_config, cf)
    replaced_v1 = r0.get(replaced_diff_field) if replaced_diff_field else None
    replaced_v2 = fixture.replaced_config.get(replaced_diff_field) if replaced_diff_field else None

    # Override config: use current state (after update + replace)
    override_resources = [{k: v for k, v in r.items() if k != "password"} for r in fixture.resources]

    return tmpl.render(
        module_name=module_name,
        cf=cf,
        prefix=fixture.prefix,
        r0_key=r0_key,
        r1_key=r1_key,
        valid_states=getattr(cls, "VALID_STATES", frozenset()),
        canonical_key=getattr(cls, "CANONICAL_KEY", None),
        supports_delete=fixture.supports_delete,
        resources_yaml=_configs_to_yaml(fixture.resources, base_indent=8),
        idem_resources_yaml=_configs_to_yaml(idem_resources, base_indent=8),
        update_yaml=_config_to_yaml(fixture.update_config, base_indent=8),
        replaced_yaml=_config_to_yaml(fixture.replaced_config, base_indent=8),
        seeds_yaml=_configs_to_yaml(fixture.extra_seeds, base_indent=8),
        override_yaml=_configs_to_yaml(override_resources, base_indent=8),
        extra_seeds=fixture.extra_seeds,
        diff_field=diff_field,
        diff_v1=diff_v1,
        diff_v2=diff_v2,
        replaced_diff_field=replaced_diff_field,
        replaced_v1=replaced_v1,
        replaced_v2=replaced_v2,
    )


def render_verify(module_name: str, fixture: ModuleFixture) -> str:
    env = _make_jinja_env()
    tmpl = env.from_string(VERIFY_TEMPLATE)
    cf = fixture.canonical_field
    return tmpl.render(
        module_name=module_name,
        cf=cf,
        r0_key=fixture.resources[0][cf],
        r1_key=fixture.resources[1][cf],
    )


def render_cleanup(module_name: str, fixture: ModuleFixture) -> str:
    env = _make_jinja_env()
    tmpl = env.from_string(CLEANUP_TEMPLATE)
    cf = fixture.canonical_field
    all_resources = fixture.resources + fixture.extra_seeds
    return tmpl.render(
        module_name=module_name,
        cf=cf,
        all_resources=all_resources,
    )


def gen_molecule_yml(module_name: str) -> str:
    return f"""\
---
# Scenario: full integration test for ansible.platform.{module_name}
# Covers all supported resource-module states.
# Runs against the mock Gateway — no real AAP required.
# Connection-mode coverage is owned by {module_name}_mock.
driver:
  name: default

platforms:
  - name: localhost

ansible:
  executor:
    args:
      ansible_playbook:
        - --inventory=${{MOLECULE_SCENARIO_DIRECTORY}}/inventory.yml

provisioner:
  name: ansible
  options:
    v: true
  playbooks:
    converge: converge.yml
    verify: verify.yml
    cleanup: cleanup.yml
  config_options:
    defaults:
      collections_path: "${{MOLECULE_SCENARIO_DIRECTORY}}/../../../../../../"
      log_verbosity: 4

scenario:
  test_sequence:
    - converge
    - verify
    - cleanup
...
"""


def gen_inventory_yml() -> str:
    return """\
---
all:
  vars:
    ansible_connection: local
    gateway_hostname: "http://127.0.0.1:8000"
    gateway_username: "mock"
    gateway_password: "testpass"
    gateway_validate_certs: false
  children:
    gateway_under_test:
      hosts:
        localhost: {}
"""


# ---------------------------------------------------------------------------
# Per-state scenario generators  (meraki_rm pattern)
# Produces extensions/molecule/{module_name}/{state}/ directories.
# Each state has: molecule.yml, vars.yml, converge.yml, verify.yml,
#                 cleanup.yml, and optionally prepare.yml.
# ---------------------------------------------------------------------------

# States that require a prepare.yml (need pre-seeded resources)
_STATES_NEED_PREPARE = frozenset({"replaced", "overridden", "deleted", "gathered", "check"})

# States that require SUPPORTS_DELETE=True
_STATES_NEED_DELETE = frozenset({"overridden", "deleted"})


def _dict_to_yaml_block(d: dict, indent: int = 2) -> str:
    """Render a Python dict as a YAML mapping block (not prefixed with '- ')."""
    pad = " " * indent
    lines = []
    for k, v in d.items():
        if isinstance(v, bool):
            lines.append(f"{pad}{k}: {str(v).lower()}")
        elif isinstance(v, str):
            lines.append(f'{pad}{k}: "{v}"')
        elif isinstance(v, list):
            lines.append(f"{pad}{k}:")
            for item in v:
                if isinstance(item, str):
                    lines.append(f'{pad}  - "{item}"')
                else:
                    lines.append(f"{pad}  - {item}")
        else:
            lines.append(f"{pad}{k}: {v}")
    return "\n".join(lines)


def _list_to_yaml_block(configs: List[dict], indent: int = 2) -> str:
    """Render a list of dicts as a YAML list block."""
    pad = " " * indent
    inner = " " * (indent + 2)
    lines = []
    for cfg in configs:
        first = True
        for k, v in cfg.items():
            pfx = f"{pad}- " if first else inner
            first = False
            if isinstance(v, bool):
                lines.append(f"{pfx}{k}: {str(v).lower()}")
            elif isinstance(v, str):
                lines.append(f'{pfx}{k}: "{v}"')
            elif isinstance(v, list):
                lines.append(f"{pfx}{k}:")
                for item in v:
                    if isinstance(item, str):
                        lines.append(f'{inner}  - "{item}"')
                    else:
                        lines.append(f"{inner}  - {item}")
            else:
                lines.append(f"{pfx}{k}: {v}")
    return "\n".join(lines)


def _gw_params() -> List[str]:
    """Return the 4 shared gateway parameter task lines."""
    return [
        '      gateway_hostname: "{{ gateway_hostname }}"',
        '      gateway_username: "{{ gateway_username }}"',
        '      gateway_password: "{{ gateway_password }}"',
        '      gateway_validate_certs: "{{ gateway_validate_certs }}"',
    ]


# ── molecule.yml ────────────────────────────────────────────────────────────

def _gen_per_state_molecule_yml(state: str, fixture: "ModuleFixture") -> str:
    """Generate a minimal molecule.yml that inherits everything from ../../config.yml.

    Only overrides:
    - scenario.test_sequence  (state-specific: prepare step, idempotence or not)
    - provisioner.playbooks.prepare  (only for states that need a prepare.yml)

    All shared settings (driver, platforms, ansible env, provisioner options,
    collections_path, verifier, prerun, shared_state) live in config.yml.
    """
    needs_prepare = state in _STATES_NEED_PREPARE or fixture.prepare_all_states
    # check mode: skip idempotence — check_mode tasks always predict a change
    # (nothing was actually applied so each re-run still sees a diff)
    use_idempotence = state != "check"

    seq_items = []
    if needs_prepare:
        seq_items.append("prepare")
    seq_items.append("converge")
    seq_items.append("verify")
    if use_idempotence:
        seq_items.append("idempotence")
        seq_items.append("verify")
    seq_items.append("cleanup")

    seq_block = "\n".join(f"  - {item}" for item in seq_items)

    prepare_block = (
        "\nprovisioner:\n"
        "  playbooks:\n"
        "    prepare: prepare.yml\n"
    ) if needs_prepare else ""

    return (
        "---\n"
        "# Inherits shared config from ../../config.yml\n"
        f"{prepare_block}"
        "\n"
        "scenario:\n"
        "  test_sequence:\n"
        f"{seq_block}\n"
        "...\n"
    )


# ── inventory.yml (shared per module) ───────────────────────────────────────

def _gen_per_module_inventory_yml() -> str:
    return (
        "---\n"
        "all:\n"
        "  vars:\n"
        "    ansible_connection: local\n"
        '    gateway_hostname: "http://127.0.0.1:8000"\n'
        '    gateway_username: "mock"\n'
        '    gateway_password: "testpass"\n'
        "    gateway_validate_certs: false\n"
        "  children:\n"
        "    gateway_under_test:\n"
        "      hosts:\n"
        "        localhost: {}\n"
    )


# ── vars.yml ─────────────────────────────────────────────────────────────────

def _gen_per_state_vars_yml(
    state: str,
    fixture: ModuleFixture,
    cf: str,
) -> str:
    r0 = fixture.resources[0]
    r0_no_pw = {k: v for k, v in r0.items() if k != "password"}

    # Compute expected_config (what the converge play uses as config input)
    if state == "merged":
        expected = r0
    elif state == "replaced":
        expected = fixture.replaced_config
    elif state == "overridden":
        expected = r0_no_pw
    elif state in ("deleted", "gathered"):
        expected = {cf: r0[cf]}        # key-only: minimal config for the operation
    else:  # check
        expected = fixture.update_config

    # Compute prepare_config / prepare_configs
    prepare_single: dict | None = None
    prepare_list: List[dict] | None = None

    if state == "replaced":
        prepare_single = r0
    elif state in ("deleted", "gathered", "check"):
        prepare_single = r0
    elif state == "overridden":
        all_seeds = fixture.resources + fixture.extra_seeds
        prepare_list = [{k: v for k, v in r.items() if k != "password"} for r in all_seeds]

    lines = ["---"]
    if prepare_single is not None:
        lines.append("prepare_config:")
        lines.append(_dict_to_yaml_block(prepare_single, indent=2))
        lines.append("")
    if prepare_list is not None:
        lines.append("prepare_configs:")
        lines.append(_list_to_yaml_block(prepare_list, indent=2))
        lines.append("")
    lines.append("expected_config:")
    lines.append(_dict_to_yaml_block(expected, indent=2))
    lines.append("")
    return "\n".join(lines)


# ── converge.yml ─────────────────────────────────────────────────────────────

def _gen_per_state_converge_yml(module_name: str, state: str) -> str:
    op = "merged" if state == "check" else state
    lines = [
        "---",
        f'- name: "Converge \u2014 {module_name} ({state})"',
        "  hosts: localhost",
        "  gather_facts: false",
        "  vars_files:",
        "  - vars.yml",
        "  tasks:",
        f'  - name: Run ansible.platform.{module_name} with state={op}',
        f'    ansible.platform.{module_name}:',
        "      config:",
        '      - "{{ expected_config }}"',
        f'      state: {op}',
    ]
    lines.extend(_gw_params())
    if state == "check":
        lines.append("    check_mode: true")
        lines.append("    diff: true")
    lines.append("    register: result")
    lines.append("")

    if state == "check":
        lines += [
            "  - name: Assert check mode predicted a change",
            "    ansible.builtin.assert:",
            "      that:",
            "      - result.changed == true",
            "      - result.before is defined",
            "      - result.after is defined",
            '      fail_msg: "check mode should predict a change. got={{ result }}"',
            "",
            "  - name: Assert diff output is present",
            "    ansible.builtin.assert:",
            "      that:",
            "      - result.diff is defined",
            '      fail_msg: "diff output missing from check result"',
            "    when: result.diff is defined",
            "",
        ]

    return "\n".join(lines) + "\n"


# ── verify.yml ────────────────────────────────────────────────────────────────

def _gen_per_state_verify_yml(
    module_name: str,
    state: str,
    cf: str,
    fixture: ModuleFixture,
) -> str:
    r0 = fixture.resources[0]
    r0_key = r0[cf]
    r1_key = fixture.resources[1][cf]

    lines = [
        "---",
        f'- name: "Verify \u2014 {module_name} ({state})"',
        "  hosts: localhost",
        "  gather_facts: false",
        "  vars_files:",
        "  - vars.yml",
        "  tasks:",
    ]

    if state == "deleted":
        # Gather by key — assert empty
        lines += [
            f'  - name: Gather {module_name} (should be absent after deleted)',
            f'    ansible.platform.{module_name}:',
            "      config:",
            f'      - {cf}: "{r0_key}"',
            "      state: gathered",
        ]
        lines.extend(_gw_params())
        lines += [
            "    register: gathered",
            "",
            f'  - name: Assert {r0_key} no longer exists (deleted)',
            "    ansible.builtin.assert:",
            "      that:",
            "      - gathered.gathered is defined",
            "      - gathered.gathered | length == 0",
            f'      fail_msg: "Expected empty after deleted, got: {{{{ gathered.gathered }}}}"',
            "",
        ]

    elif state == "overridden":
        # Check target still exists
        lines += [
            f'  - name: Gather target resource {r0_key} (should exist after overridden)',
            f'    ansible.platform.{module_name}:',
            "      config:",
            f'      - {cf}: "{r0_key}"',
            "      state: gathered",
        ]
        lines.extend(_gw_params())
        lines += [
            "    register: gathered_target",
            "",
            f'  - name: Assert {r0_key} still exists after overridden',
            "    ansible.builtin.assert:",
            "      that:",
            "      - gathered_target.gathered is defined",
            "      - gathered_target.gathered | length == 1",
            f'      fail_msg: "Expected {r0_key} to exist after overridden. got: {{{{ gathered_target.gathered }}}}"',
            "",
            f'  - name: Gather extra resource {r1_key} (should be deleted by overridden)',
            f'    ansible.platform.{module_name}:',
            "      config:",
            f'      - {cf}: "{r1_key}"',
            "      state: gathered",
        ]
        lines.extend(_gw_params())
        lines += [
            "    register: gathered_extra",
            "",
            f'  - name: Assert {r1_key} was deleted by overridden (not in desired config)',
            "    ansible.builtin.assert:",
            "      that:",
            "      - gathered_extra.gathered is defined",
            "      - gathered_extra.gathered | length == 0",
            f'      fail_msg: "overridden should have deleted {r1_key}. got: {{{{ gathered_extra.gathered }}}}"',
            "",
        ]

    elif state == "check":
        # Verify that check mode did NOT alter the resource
        diff_field = _diff_field(r0, fixture.update_config, cf)
        lines += [
            f'  - name: Gather {module_name} (check mode must not have applied changes)',
            f'    ansible.platform.{module_name}:',
            "      config:",
            f'      - {cf}: "{{{{ expected_config.{cf} }}}}"',
            "      state: gathered",
        ]
        lines.extend(_gw_params())
        lines += [
            "    register: gathered",
            "",
            f'  - name: Assert {r0_key} still has prepare_config values (check did not apply)',
            "    ansible.builtin.assert:",
            "      that:",
            "      - gathered.gathered is defined",
            "      - gathered.gathered | length > 0",
        ]
        if diff_field:
            lines.append(
                f'      - (gathered.gathered | first).{diff_field} == prepare_config.{diff_field}'
            )
        lines += [
            f'      fail_msg: "check mode should not alter resource. got: {{{{ gathered.gathered }}}}"',
            "",
        ]

    else:
        # merged / replaced / gathered — gather by key, assert present
        lines += [
            f'  - name: Gather {module_name} (assert present after {state})',
            f'    ansible.platform.{module_name}:',
            "      config:",
            f'      - {cf}: "{{{{ expected_config.{cf} }}}}"',
            "      state: gathered",
        ]
        lines.extend(_gw_params())
        lines += [
            "    register: gathered",
            "",
            f'  - name: Assert configuration exists after {state}',
            "    ansible.builtin.assert:",
            "      that:",
            "      - gathered.gathered is defined",
            "      - gathered.gathered | length > 0",
            f'      fail_msg: "Expected resource after {state}. got: {{{{ gathered.gathered }}}}"',
            "",
        ]

        # For replaced state, also check the diff field changed
        if state == "replaced":
            diff_field = _diff_field(r0, fixture.replaced_config, cf)
            if diff_field:
                new_val = fixture.replaced_config.get(diff_field)
                lines += [
                    f'  - name: Assert {diff_field} was updated by replaced',
                    "    ansible.builtin.assert:",
                    "      that:",
                    f'      - (gathered.gathered | first).{diff_field} == expected_config.{diff_field}',
                    f'      fail_msg: "replaced should have set {diff_field}={new_val!r}. got: {{{{ (gathered.gathered | first).{diff_field} }}}}"',
                    "",
                ]

    return "\n".join(lines) + "\n"


# ── cleanup.yml ───────────────────────────────────────────────────────────────

def _gen_per_state_cleanup_yml(
    module_name: str,
    state: str,
    fixture: ModuleFixture,
    cf: str,
) -> str:
    r0 = fixture.resources[0]
    r0_key = r0[cf]

    lines = [
        "---",
        f'- name: "Cleanup \u2014 {module_name} ({state})"',
        "  hosts: localhost",
        "  gather_facts: false",
        "  vars_files:",
        "  - vars.yml",
        "  tasks:",
    ]

    if state == "deleted":
        lines += [
            f'  - name: No-op \u2014 {r0_key} already deleted by converge',
            "    ansible.builtin.debug:",
            f'      msg: "{r0_key} was deleted in converge \u2014 nothing to clean up"',
            "",
        ]
    else:
        # overridden deletes r1/extras during converge; only r0 remains
        lines += [
            f'  - name: Remove {r0_key} (test teardown)',
            f'    ansible.platform.{module_name}:',
            "      config:",
            f'      - {cf}: "{r0_key}"',
            "      state: deleted",
        ]
        lines.extend(_gw_params())
        lines += [
            "    ignore_errors: true",
            "",
        ]

    # Append prerequisite cleanup tasks (e.g. remove parent resource seeded in prepare)
    if fixture.cleanup_prereq_yaml:
        for line in fixture.cleanup_prereq_yaml.rstrip().splitlines():
            lines.append(line)
        lines.append("")

    return "\n".join(lines) + "\n"


# ── prepare.yml ───────────────────────────────────────────────────────────────

def _gen_per_state_prepare_yml(
    module_name: str,
    state: str,
    cf: str,
    fixture: "ModuleFixture",
) -> str:
    needs_prepare = state in _STATES_NEED_PREPARE or fixture.prepare_all_states
    if not needs_prepare:
        return ""

    lines = [
        "---",
        f'- name: "Prepare \u2014 {module_name} ({state})"',
        "  hosts: localhost",
        "  gather_facts: false",
        "  vars_files:",
        "  - vars.yml",
        "  tasks:",
    ]

    # Inject prerequisite tasks first (e.g. create a parent resource that must exist)
    if fixture.prereq_yaml:
        for line in fixture.prereq_yaml.rstrip().splitlines():
            lines.append(line)
        lines.append("")

    # Seed the module's own resources (only for states that need data pre-seeded)
    if state in _STATES_NEED_PREPARE:
        if state == "overridden":
            # Seed multiple resources (r0, r1, extra seeds)
            lines += [
                f'  - name: Seed prerequisite resources via merged (r0 + r1 + extras for overridden)',
                f'    ansible.platform.{module_name}:',
                "      config: \"{{ prepare_configs }}\"",
                "      state: merged",
            ]
        else:
            # Seed a single resource
            verb = {"replaced": "to be replaced", "deleted": "to be deleted",
                    "gathered": "to be gathered", "check": "as check-mode baseline"}[state]
            lines += [
                f'  - name: Seed {module_name} {verb} (prerequisite for {state})',
                f'    ansible.platform.{module_name}:',
                "      config:",
                '      - "{{ prepare_config }}"',
                "      state: merged",
            ]
        lines.extend(_gw_params())

    lines.append("")
    return "\n".join(lines) + "\n"


# ── Top-level per-state generator ─────────────────────────────────────────────

def generate_per_state_scenarios(
    module_name: str,
    dry_run: bool = False,
    force: bool = False,
) -> None:
    """Generate extensions/molecule/{module_name}/{state}/ for each applicable state."""
    if module_name not in FIXTURES:
        print(f"  [SKIP] {module_name}: no fixture defined")
        return

    fixture = FIXTURES[module_name]

    try:
        cls = load_model_class(module_name)
    except SystemExit as exc:
        print(f"  [SKIP] {module_name}: {exc}")
        return

    canonical_key = getattr(cls, "CANONICAL_KEY", None)
    if canonical_key is None:
        print(f"  [SKIP] {module_name}: CANONICAL_KEY=None (singleton — write manually)")
        return

    cf = fixture.canonical_field
    supports_delete = getattr(cls, "SUPPORTS_DELETE", True) and fixture.supports_delete

    # States to generate
    states = ["merged", "replaced", "gathered", "check"]
    if supports_delete:
        states += ["overridden", "deleted"]

    module_dir = MOLECULE_DIR / module_name

    for state in states:
        state_dir = module_dir / state

        if state_dir.exists() and not force:
            print(f"  [SKIP] {module_name}/{state}: already exists (use --force)")
            continue

        # Build file map
        needs_prepare = state in _STATES_NEED_PREPARE or fixture.prepare_all_states
        files: dict[str, str] = {
            "molecule.yml": _gen_per_state_molecule_yml(state, fixture),
            "vars.yml":     _gen_per_state_vars_yml(state, fixture, cf),
            "converge.yml": _gen_per_state_converge_yml(module_name, state),
            "verify.yml":   _gen_per_state_verify_yml(module_name, state, cf, fixture),
            "cleanup.yml":  _gen_per_state_cleanup_yml(module_name, state, fixture, cf),
        }
        if needs_prepare:
            files["prepare.yml"] = _gen_per_state_prepare_yml(module_name, state, cf, fixture)

        if dry_run:
            print(f"\n{'=' * 70}")
            print(f"DRY RUN: {module_name}/{state}/converge.yml")
            print("=" * 70)
            print(files["converge.yml"])
            continue

        state_dir.mkdir(parents=True, exist_ok=True)
        for fname, content in files.items():
            (state_dir / fname).write_text(content)

        print(f"  [OK]   {module_name}/{state}/ → {state_dir}")

    # Write shared per-module inventory.yml (once per module)
    inv_path = module_dir / "inventory.yml"
    if not inv_path.exists() or force:
        if not dry_run:
            module_dir.mkdir(parents=True, exist_ok=True)
            inv_path.write_text(_gen_per_module_inventory_yml())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate_scenario(module_name: str, dry_run: bool = False, force: bool = False) -> None:
    if module_name not in FIXTURES:
        print(f"  [SKIP] {module_name}: no fixture defined (add to FIXTURES dict)")
        return

    fixture = FIXTURES[module_name]

    try:
        cls = load_model_class(module_name)
    except SystemExit as exc:
        print(f"  [SKIP] {module_name}: {exc}")
        return

    canonical_key = getattr(cls, "CANONICAL_KEY", None)
    if canonical_key is None:
        print(f"  [SKIP] {module_name}: CANONICAL_KEY=None (singleton/category-C — write scenario manually)")
        return

    scenario_dir = MOLECULE_DIR / f"{module_name}_integration"

    if scenario_dir.exists() and not force:
        print(f"  [SKIP] {module_name}: scenario already exists (use --force to overwrite)")
        return

    files = {
        "molecule.yml":  gen_molecule_yml(module_name),
        "inventory.yml": gen_inventory_yml(),
        "converge.yml":  render_converge(module_name, cls, fixture),
        "verify.yml":    render_verify(module_name, fixture),
        "cleanup.yml":   render_cleanup(module_name, fixture),
    }

    if dry_run:
        print(f"\n{'=' * 70}")
        print(f"DRY RUN: {module_name}_integration/converge.yml")
        print("=" * 70)
        print(files["converge.yml"])
        return

    scenario_dir.mkdir(parents=True, exist_ok=True)
    for fname, content in files.items():
        (scenario_dir / fname).write_text(content)

    print(f"  [OK]   {module_name}_integration/ → {scenario_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("modules", nargs="*", help="Module name(s) to generate")
    parser.add_argument("--all",       action="store_true", help="Generate for all known modules")
    parser.add_argument("--dry-run",   action="store_true", help="Print converge.yml to stdout only")
    parser.add_argument("--force",     action="store_true", help="Overwrite existing scenarios")
    parser.add_argument("--list",      action="store_true", help="List modules with fixtures defined")
    parser.add_argument(
        "--per-state",
        action="store_true",
        help=(
            "Generate per-state scenarios ({module}/{state}/) following the meraki_rm pattern. "
            "Each state gets its own molecule.yml, vars.yml, converge.yml, verify.yml, "
            "cleanup.yml (and prepare.yml where needed). "
            "Molecule idempotence step validates re-run produces no changes."
        ),
    )
    args = parser.parse_args()

    if args.list:
        print("Modules with fixture definitions:")
        for name in sorted(FIXTURES):
            print(f"  {name}")
        return

    if args.all:
        modules = get_all_module_names()
    elif args.modules:
        modules = args.modules
    else:
        parser.print_help()
        return

    if args.per_state:
        # Per-state mode: generate {module}/{state}/ directories
        for module_name in modules:
            generate_per_state_scenarios(
                module_name, dry_run=args.dry_run, force=args.force
            )
    else:
        # Legacy mode: generate {module}_integration/ directories
        for module_name in modules:
            if module_name in HAND_CRAFTED and not args.force:
                print(f"  [SKIP] {module_name}: hand-crafted scenario exists (use --force to regenerate)")
                continue
            generate_scenario(module_name, dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    main()
