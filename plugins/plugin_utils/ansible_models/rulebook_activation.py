"""Ansible Rulebook Activation dataclass - user-facing stable interface."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class AnsibleRulebookActivation:
    """Ansible representation of an EDA rulebook activation."""

    # Required / identity
    name: str

    # Optional fields
    new_name: Optional[str] = None
    description: Optional[str] = None
    project_name: Optional[str] = None
    rulebook_name: Optional[str] = None
    extra_vars: Optional[str] = None
    restart: Optional[bool] = None
    restart_policy: Optional[str] = None
    decision_environment_name: Optional[str] = None
    awx_token_name: Optional[str] = None
    organization_name: Optional[str] = None
    eda_credentials: Optional[List[str]] = None
    k8s_service_name: Optional[str] = None
    event_streams: Optional[List[Dict[str, Any]]] = None
    log_level: Optional[str] = None
    enable_persistence: Optional[bool] = None
    rule_engine_credential_id: Optional[int] = None
    restart_on_project_update: Optional[bool] = None
    state: Optional[str] = None

    # API response fields used by the action and update idempotency checks.
    id: Optional[int] = None
    is_enabled: Optional[bool] = None
    extra_var: Optional[str] = None
    rulebook_id: Optional[int] = None
    awx_token_id: Optional[int] = None
    source_mappings: Optional[str] = None
