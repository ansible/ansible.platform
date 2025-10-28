from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

# In CI, generate this from the AAP OpenAPI spec (gateway/controller).
@dataclass
class User:
    id: Optional[int] = None
    username: Optional[str] = None
    email: Optional[str] = None
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    is_superuser: Optional[bool] = False
