"""Ansible EventStream dataclass - user-facing stable interface."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AnsibleEventStream:
    """Ansible representation of an EDA event stream."""

    # Required / identity
    name: str

    # Optional fields
    new_name: Optional[str] = None
    credential_name: Optional[str] = None
    organization_name: Optional[str] = None
    event_stream_type: Optional[str] = None  # Deprecated, ignored
    headers: Optional[str] = None
    forward_events: Optional[bool] = None
    uuid: Optional[str] = None
    state: str = "present"

    # Read-only fields (populated from API responses)
    id: Optional[int] = None

    def __post_init__(self):
        """Validate UUID format if provided."""
        if self.uuid is not None:
            import uuid as uuid_module

            try:
                uuid_module.UUID(self.uuid)
            except ValueError:
                raise ValueError("Invalid UUID format: %s" % self.uuid)
