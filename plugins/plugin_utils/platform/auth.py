"""Platform SDK - Authentication Manager.

Simplified authentication handling for AAP Gateway.
Handles token refresh using username/password Basic Auth or Refresh Tokens.
"""

import logging
import requests
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AuthCredentials:
    """Authentication credentials container."""
    base_url: str
    oauth_token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    refresh_token: Optional[str] = None
    
    # 👇 NEW: Client Credentials fields
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    
    verify_ssl: bool = True
    request_timeout: float = 10.0


class TokenManager:
    """
    Manages authentication for AAP Gateway.
    
    Strategies:
    0. Refresh Token (with Client Creds if available)
    1. Token Rotation (Access Token -> New Access Token)
    2. Basic Auth (Username/Password)
    """
    
    def __init__(self, credentials: AuthCredentials):
        """
        Initialize token manager.
        """
        self.base_url = credentials.base_url.rstrip('/')
        self.oauth_token = credentials.oauth_token
        self.username = credentials.username
        self.password = credentials.password
        self.refresh_token = credentials.refresh_token
        
        # 👇 NEW: Store Client Credentials
        self.client_id = credentials.client_id
        self.client_secret = credentials.client_secret
        
        self.verify_ssl = credentials.verify_ssl
        self.request_timeout = credentials.request_timeout
        
        logger.info("TokenManager initialized")
        logger.debug(f"Has oauth_token: {bool(self.oauth_token)}")
        logger.debug(f"Has refresh_token: {bool(self.refresh_token)}")
        logger.debug(f"Has client_id: {bool(self.client_id)}")
    
    def get_current_token(self) -> Optional[str]:
        return self.oauth_token
    
    def refresh_or_login(self) -> bool:
        """Refresh token or re-authenticate."""
        logger.info("🔄 Attempting to refresh or re-authenticate...")
        
        # Strategy 0: Use Refresh Token (Highest Priority)
        if self.refresh_token:
            logger.info("Strategy 0: Refreshing using refresh_token...")
            if self._create_token_with_refresh_token():
                return True
                
        # Strategy 1: Try creating new token with current token
        if self.oauth_token:
            logger.info("Strategy 1: Creating new token with current token...")
            if self._create_token_with_token():
                logger.info("✅ Token refresh successful!")
                return True
            logger.warning("❌ Token creation failed (token likely expired)")
        
        # Strategy 2: Use username/password Basic Auth
        if self.username and self.password:
            logger.info("Strategy 2: Creating token with username/password...")
            if self._create_token_with_password():
                logger.info("✅ Basic Auth login successful!")
                return True
            logger.error("❌ Basic Auth failed")
        
        logger.error("🚨 All authentication methods failed!")
        return False
    
    def _create_token_with_refresh_token(self) -> bool:
        """
        Create new token using the refresh token + User Basic Auth.
        
        NOTE: AAP Gateway requires User Basic Auth (Username:Password) 
        to validate the identity during a refresh flow. 
        Client Credentials are NOT accepted.
        """
        try:
            token_url = f"{self.base_url}/api/gateway/v1/tokens/"
            
            # Payload
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token
            }
            
            # CRITICAL FIX: Use User Credentials for Auth Header
            # This satisfies the requirement: "refresh endpoint protected by user auth"
            auth_header = None
            if self.username and self.password:
                auth_header = (self.username, self.password)
                logger.debug(f"POST {token_url} using User Basic Auth")
            else:
                # If we don't have password, we can't refresh on this specific Gateway
                logger.warning("Cannot refresh: User credentials missing (Required by Gateway)")
                return False
            
            response = requests.post(
                token_url,
                json=data,
                auth=auth_header,
                verify=self.verify_ssl,
                timeout=self.request_timeout
            )
            
            if response.status_code in (200, 201):
                result = response.json()
                self.oauth_token = result.get('access_token') or result.get('token')
                
                if result.get('refresh_token'):
                    self.refresh_token = result.get('refresh_token')
                    
                logger.info("✅ Token refreshed successfully via Refresh Flow!")
                return True
            else:
                logger.warning(f"Refresh failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Refresh strategy exception: {e}")
            return False
    
    def _create_token_with_password(self) -> bool:
        """Create a new token using username/password Basic Auth."""
        try:
            token_url = f"{self.base_url}/api/gateway/v1/tokens/"
            
            token_data = {
                'description': 'Auto-refreshed token',
                'scope': 'write'
            }
            
            logger.debug(f"POST {token_url} with Basic Auth (username={self.username})")
            
            response = requests.post(
                token_url,
                auth=(self.username, self.password),
                json=token_data,
                verify=self.verify_ssl,
                timeout=self.request_timeout
            )
            
            if response.status_code not in (200, 201):
                logger.error(f"Token creation failed: {response.status_code}")
                return False
            
            result = response.json()
            new_token = result.get('token')
            
            if not new_token:
                return False
            
            self.oauth_token = new_token
            logger.info(f"New token created, expires: {result.get('expires', 'unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"Token creation exception: {e}", exc_info=True)
            return False
    
    def update_session_headers(self, session) -> None:
        """Update session headers with current token."""
        if not self.oauth_token:
            return
        
        session.headers['Authorization'] = f"Bearer {self.oauth_token}"
        logger.debug("Session Authorization header updated")