"""
Credential Management for Platform Persistent Connection Manager.

This module provides secure credential handling, including:
- In-memory credential storage with process/namespace isolation
- Token refresh and expiration detection
- Secure credential lifecycle management
"""

import hashlib
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CredentialNamespace:
    """
    Represents a credential namespace for isolation.

    A namespace is identified by a combination of:
    - Gateway URL
    - Credential hash (username/password or token)
    - Process identifier

    This ensures that different credentials for the same gateway
    get separate manager processes and isolated storage.
    """

    gateway_url: str
    credential_hash: str
    process_id: Optional[str] = None

    def __post_init__(self):
        """Generate namespace identifier."""
        self.namespace_id = self._generate_namespace_id()

    def _generate_namespace_id(self) -> str:
        """Generate unique namespace identifier."""
        components = [self.gateway_url, self.credential_hash]
        if self.process_id:
            components.append(self.process_id)
        namespace_str = ":".join(components)
        return hashlib.sha256(namespace_str.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def from_credentials(
        cls,
        gateway_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        oauth_token: Optional[str] = None,
        process_id: Optional[str] = None,
    ) -> "CredentialNamespace":
        """
        Create namespace from credentials.

        Args:
            gateway_url: Gateway base URL
            username: Username (for basic auth)
            password: Password (for basic auth)
            oauth_token: OAuth token (for bearer auth)
            process_id: Optional process identifier

        Returns:
            CredentialNamespace instance
        """
        # Create credential hash (without storing actual credentials)
        if oauth_token:
            cred_string = f"token:{oauth_token}"
        elif username and password:
            cred_string = f"basic:{username}:{password}"
        else:
            cred_string = "none"

        credential_hash = hashlib.sha256(cred_string.encode("utf-8")).hexdigest()[:16]

        return cls(gateway_url=gateway_url, credential_hash=credential_hash, process_id=process_id)


@dataclass
class TokenInfo:
    """Information about an OAuth token."""

    token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    issued_at: Optional[datetime] = None

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        """
        Check if token is expired (with buffer).

        Args:
            buffer_seconds: Seconds before expiration to consider expired

        Returns:
            True if expired or will expire within buffer
        """
        if not self.expires_at:
            return False  # No expiration info, assume valid

        return datetime.now() >= (self.expires_at - timedelta(seconds=buffer_seconds))

    def time_until_expiry(self) -> Optional[float]:
        """
        Get seconds until token expires.

        Returns:
            Seconds until expiry, or None if no expiration info
        """
        if not self.expires_at:
            return None

        delta = self.expires_at - datetime.now()
        return delta.total_seconds()


@dataclass
class CredentialStore:
    """
    Secure in-memory credential storage for a namespace.

    Credentials are stored only in memory and are never written to disk.
    Each namespace has its own isolated credential store.
    """

    namespace: CredentialNamespace
    username: Optional[str] = None
    password: Optional[str] = None
    token_info: Optional[TokenInfo] = None
    last_used: datetime = field(default_factory=datetime.now)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def get_auth_credentials(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Get current authentication credentials.

        Returns:
            Tuple of (username, password, oauth_token)
        """
        with self.lock:
            self.last_used = datetime.now()
            token = self.token_info.token if self.token_info else None
            return (self.username, self.password, token)

    def update_token(self, token: str, refresh_token: Optional[str] = None, expires_in: Optional[int] = None) -> None:
        """
        Update OAuth token.

        Args:
            token: New OAuth token
            refresh_token: Optional refresh token
            expires_in: Optional expiration time in seconds from now
        """
        with self.lock:
            expires_at = None
            if expires_in:
                expires_at = datetime.now() + timedelta(seconds=expires_in)

            self.token_info = TokenInfo(token=token, refresh_token=refresh_token, expires_at=expires_at, issued_at=datetime.now())
            self.last_used = datetime.now()
            logger.info("Token updated for namespace %s, expires_at=%s", self.namespace.namespace_id, expires_at)

    def clear_credentials(self) -> None:
        """Clear all stored credentials."""
        with self.lock:
            self.username = None
            self.password = None
            self.token_info = None
            logger.info("Credentials cleared for namespace %s", self.namespace.namespace_id)


class CredentialManager:
    """
    Central credential manager with namespace isolation.

    This manager provides:
    - Per-namespace credential isolation
    - Thread-safe credential access
    - Token expiration detection
    - Secure credential lifecycle management
    """

    def __init__(self):
        """Initialize credential manager."""
        self._stores: Dict[str, CredentialStore] = {}
        self._lock = threading.Lock()
        logger.info("CredentialManager initialized")

    def get_or_create_store(
        self,
        gateway_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        oauth_token: Optional[str] = None,
        process_id: Optional[str] = None,
    ) -> CredentialStore:
        """
        Get or create credential store for namespace.

        Args:
            gateway_url: Gateway base URL
            username: Username (for basic auth)
            password: Password (for basic auth)
            oauth_token: OAuth token (for bearer auth)
            process_id: Optional process identifier

        Returns:
            CredentialStore for the namespace
        """
        namespace = CredentialNamespace.from_credentials(
            gateway_url=gateway_url, username=username, password=password, oauth_token=oauth_token, process_id=process_id
        )

        with self._lock:
            if namespace.namespace_id not in self._stores:
                store = CredentialStore(
                    namespace=namespace, username=username, password=password, token_info=TokenInfo(token=oauth_token) if oauth_token else None
                )
                self._stores[namespace.namespace_id] = store
                logger.info("Created credential store for namespace %s", namespace.namespace_id)
            else:
                store = self._stores[namespace.namespace_id]
                logger.debug("Reusing credential store for namespace %s", namespace.namespace_id)

            return store

    def get_store_by_namespace_id(self, namespace_id: str) -> Optional[CredentialStore]:
        """
        Get credential store by namespace ID.

        Args:
            namespace_id: Namespace identifier

        Returns:
            CredentialStore or None if not found
        """
        with self._lock:
            return self._stores.get(namespace_id)

    def check_token_expiration(self, namespace_id: str) -> Tuple[bool, Optional[float]]:
        """
        Check if token is expired for a namespace.

        Args:
            namespace_id: Namespace identifier

        Returns:
            Tuple of (is_expired, seconds_until_expiry)
        """
        store = self.get_store_by_namespace_id(namespace_id)
        if not store or not store.token_info:
            return (False, None)

        with store.lock:
            is_expired = store.token_info.is_expired()
            time_until = store.token_info.time_until_expiry()
            return (is_expired, time_until)

    def clear_namespace(self, namespace_id: str) -> None:
        """
        Clear credentials for a namespace.

        Args:
            namespace_id: Namespace identifier
        """
        with self._lock:
            if namespace_id in self._stores:
                self._stores[namespace_id].clear_credentials()
                del self._stores[namespace_id]
                logger.info("Cleared credential store for namespace %s", namespace_id)

    def clear_all(self) -> None:
        """Clear all credential stores."""
        with self._lock:
            for store in self._stores.values():
                store.clear_credentials()
            self._stores.clear()
            logger.info("Cleared all credential stores")


# Global credential manager instance (per-process)

_global_credential_manager: Optional[CredentialManager] = None
_global_credential_manager_lock = threading.Lock()


def get_credential_manager() -> CredentialManager:
    """
    Get global credential manager instance (singleton per process).

    Returns:
        CredentialManager instance
    """
    global _global_credential_manager
    with _global_credential_manager_lock:
        if _global_credential_manager is None:
            _global_credential_manager = CredentialManager()
        return _global_credential_manager
