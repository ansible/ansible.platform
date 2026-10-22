from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AnsibleNotificationTemplate:
    name: str
    organization: str
    new_name: Optional[str] = None
    description: Optional[str] = None
    notification_type: Optional[str] = None
    notification_configuration: Optional[Dict[str, Any]] = None
    messages: Optional[Dict[str, Any]] = None
    state: str = "present"
    id: Optional[int] = None
