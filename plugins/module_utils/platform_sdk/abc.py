from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Iterable, Optional, Protocol

T = TypeVar("T")

class TokenProvider(Protocol):
    def __call__(self) -> tuple[str, float]: ...

class Repository(ABC, Generic[T]):
    """Stable interface for endpoint repositories."""
    @abstractmethod
    def list(self) -> Iterable[T]: ...
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[T]: ...
    @abstractmethod
    def create(self, obj: T) -> T: ...
    @abstractmethod
    def update(self, obj: T) -> T: ...
    @abstractmethod
    def delete(self, obj: T) -> None: ...
