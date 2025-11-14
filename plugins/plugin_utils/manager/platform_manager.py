"""Platform Manager - Persistent service for API communication.

This module provides the server-side manager that maintains persistent
connections to the platform API and handles all data transformations.
"""

import base64
import logging
import threading
from multiprocessing.managers import BaseManager
from socketserver import ThreadingMixIn
from typing import Any, Dict, Optional
from dataclasses import asdict, is_dataclass
from urllib.parse import urlparse, urlencode
import requests

from ..platform.registry import APIVersionRegistry
from ..platform.loader import DynamicClassLoader
from ..platform.types import EndpointOperation

logger = logging.getLogger(__name__)


class PlatformService:
    """
    Generic platform service - resource agnostic.
    
    This service maintains a persistent connection and handles all resource operations
    generically. It performs all transformations and API calls.
    
    Attributes:
        base_url: Platform base URL
        session: Persistent HTTP session
        api_version: Detected/cached API version
        registry: Version registry
        loader: Class loader
        cache: Lookup cache (org names ↔ IDs, etc.)
        username: Authentication username
        password: Authentication password
        oauth_token: OAuth token for authentication
        verify_ssl: SSL verification flag
    """
    
    def __init__(
        self,
        base_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        oauth_token: Optional[str] = None,
        verify_ssl: bool = True,
        request_timeout: float = 10.0
    ):
        """
        Initialize platform service.
        
        Args:
            base_url: Platform base URL (e.g., https://platform.example.com)
            username: Username for basic auth
            password: Password for basic auth
            oauth_token: OAuth token for bearer auth
            verify_ssl: Whether to verify SSL certificates
            request_timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.oauth_token = oauth_token
        self.verify_ssl = verify_ssl
        self.request_timeout = request_timeout
        
        # Initialize persistent session (thread-safe)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Ansible Platform Collection',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        # Authenticate
        self._authenticate()
        
        # Detect API version (cached for lifetime)
        self.api_version = self._detect_version()
        logger.info(f"PlatformService initialized with API v{self.api_version}")
        
        # Initialize registry and loader
        self.registry = APIVersionRegistry()
        self.loader = DynamicClassLoader(self.registry)
        
        # Cache for lookups
        self.cache: Dict[str, Any] = {}
    
    def _authenticate(self) -> None:
        """Authenticate with the platform API."""
        url = self._build_url("")
        
        if self.oauth_token:
            # OAuth token authentication
            header = {"Authorization": f"Bearer {self.oauth_token}"}
            self.session.headers.update(header)
            try:
                response = self.session.get(url, timeout=self.request_timeout, verify=self.verify_ssl)
                response.raise_for_status()
                logger.info("Authenticated using OAuth token")
            except requests.RequestException as e:
                raise ValueError(f"Authentication error with token: {e}") from e
        elif self.username and self.password:
            # Basic authentication
            basic_str = base64.b64encode(
                f"{self.username}:{self.password}".encode("ascii")
            )
            header = {"Authorization": f"Basic {basic_str.decode('ascii')}"}
            self.session.headers.update(header)
            try:
                response = self.session.get(url, timeout=self.request_timeout, verify=self.verify_ssl)
                response.raise_for_status()
                logger.info("Authenticated using basic auth")
            except requests.RequestException as e:
                raise ValueError(f"Authentication error: {e}") from e
        else:
            raise ValueError("Either oauth_token or username/password must be provided")
    
    def _detect_version(self) -> str:
        """
        Detect platform API version.
        
        Returns:
            Version string (e.g., '1', '2.1')
        """
        try:
            # Try to get version from API
            # Most AAP APIs have a version endpoint or include version in response
            response = self.session.get(
                f'{self.base_url}/api/gateway/v1/ping/',
                timeout=self.request_timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            
            # Try to extract version from response or default to v1
            version_str = '1'  # Default to v1 for AAP Gateway
            
            # If API provides version info, extract it
            if response.headers.get('X-API-Version'):
                version_str = response.headers.get('X-API-Version', '1')
            elif response.json().get('version'):
                version_str = str(response.json().get('version', '1'))
            
            # Normalize version string
            if version_str.startswith('v'):
                version_str = version_str[1:]
            
            logger.info(f"Detected platform API version: {version_str}")
            return version_str
            
        except Exception as e:
            logger.warning(f"Failed to detect API version: {e}, using default '1'")
            return '1'
    
    def _build_url(self, endpoint: str, query_params: Optional[Dict] = None) -> str:
        """
        Build full URL for an endpoint.
        
        Args:
            endpoint: API endpoint path
            query_params: Optional query parameters
        
        Returns:
            Full URL string
        """
        # Ensure endpoint starts with /api/gateway/v1
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        if not endpoint.startswith("/api/"):
            endpoint = f"/api/gateway/v{self.api_version}{endpoint}"
        if not endpoint.endswith("/") and "?" not in endpoint:
            endpoint = f"{endpoint}/"
        
        url = f"{self.base_url}{endpoint}"
        
        if query_params:
            url = f"{url}?{urlencode(query_params)}"
        
        return url
    
    def execute(
        self,
        operation: str,
        module_name: str,
        ansible_data_dict: dict
    ) -> dict:
        """
        Execute a generic operation on any resource.
        
        This is the main entry point called by action plugins via RPC.
        
        Args:
            operation: Operation type ('create', 'update', 'delete', 'find')
            module_name: Module name (e.g., 'user', 'organization')
            ansible_data_dict: Ansible dataclass as dict
        
        Returns:
            Result as dict (Ansible format)
        
        Raises:
            ValueError: If operation is unknown or execution fails
        """
        thread_id = threading.get_ident()
        logger.info(
            f"Executing {operation} on {module_name} [Thread: {thread_id}]"
        )
        
        # Load version-appropriate classes
        AnsibleClass, APIClass, MixinClass = self.loader.load_classes_for_module(
            module_name,
            self.api_version
        )
        
        # Reconstruct Ansible dataclass
        ansible_instance = AnsibleClass(**ansible_data_dict)
        
        # Build transformation context
        context = {
            'manager': self,
            'session': self.session,
            'cache': self.cache,
            'api_version': self.api_version
        }
        
        # Execute operation
        try:
            if operation == 'create':
                result = self._create_resource(
                    ansible_instance, MixinClass, context
                )
            elif operation == 'update':
                result = self._update_resource(
                    ansible_instance, MixinClass, context
                )
            elif operation == 'delete':
                result = self._delete_resource(
                    ansible_instance, MixinClass, context
                )
            elif operation == 'find':
                result = self._find_resource(
                    ansible_instance, MixinClass, context
                )
            else:
                raise ValueError(f"Unknown operation: {operation}")
            
            logger.info(
                f"Operation {operation} on {module_name} completed "
                f"[Thread: {thread_id}]"
            )
            
            return result
            
        except Exception as e:
            logger.error(
                f"Operation {operation} on {module_name} failed: {e}",
                exc_info=True
            )
            raise
    
    def _create_resource(
        self,
        ansible_data: Any,
        mixin_class: type,
        context: dict
    ) -> dict:
        """
        Create resource with transformation.
        
        Args:
            ansible_data: Ansible dataclass instance
            mixin_class: Transform mixin class
            context: Transformation context
        
        Returns:
            Created resource as dict (Ansible format)
        """
        # FORWARD TRANSFORM: Ansible → API
        api_data = ansible_data.to_api(context)
        
        # Get endpoint operations from mixin
        operations = mixin_class.get_endpoint_operations()
        
        # Execute operations (potentially multi-endpoint)
        api_result = self._execute_operations(
            operations, api_data, context, required_for='create'
        )
        
        # REVERSE TRANSFORM: API → Ansible
        if api_result:
            api_result_instance = type(api_data)(**api_result)
            ansible_result = api_result_instance.to_ansible(context)
            return asdict(ansible_result)
        
        return {}
    
    def _update_resource(
        self,
        ansible_data: Any,
        mixin_class: type,
        context: dict
    ) -> dict:
        """
        Update resource with transformation.
        
        Args:
            ansible_data: Ansible dataclass instance
            mixin_class: Transform mixin class
            context: Transformation context
        
        Returns:
            Updated resource as dict (Ansible format)
        """
        # FORWARD TRANSFORM: Ansible → API
        api_data = ansible_data.to_api(context)
        
        # Get endpoint operations from mixin
        operations = mixin_class.get_endpoint_operations()
        
        # Execute update operation
        api_result = self._execute_operations(
            operations, api_data, context, required_for='update'
        )
        
        # REVERSE TRANSFORM: API → Ansible
        if api_result:
            api_result_instance = type(api_data)(**api_result)
            ansible_result = api_result_instance.to_ansible(context)
            return asdict(ansible_result)
        
        return {}
    
    def _delete_resource(
        self,
        ansible_data: Any,
        mixin_class: type,
        context: dict
    ) -> dict:
        """
        Delete resource.
        
        Args:
            ansible_data: Ansible dataclass instance
            mixin_class: Transform mixin class
            context: Transformation context
        
        Returns:
            Empty dict (resource deleted)
        """
        # Get endpoint operations from mixin
        operations = mixin_class.get_endpoint_operations()
        
        # Find delete operation
        delete_op = None
        for op_name, op in operations.items():
            if op_name == 'delete' or (op.required_for == 'delete'):
                delete_op = op
                break
        
        if not delete_op:
            raise ValueError("No delete operation defined for this resource")
        
        # Need ID for delete
        resource_id = ansible_data.id
        if not resource_id:
            raise ValueError("Resource ID required for delete operation")
        
        # Build URL with path parameters
        path = delete_op.path
        if delete_op.path_params:
            for param in delete_op.path_params:
                if param == 'id':
                    path = path.replace(f'{{{param}}}', str(resource_id))
        
        url = self._build_url(path)
        
        # Make DELETE request
        logger.debug(f"Calling DELETE {url}")
        response = self.session.delete(
            url,
            timeout=self.request_timeout,
            verify=self.verify_ssl
        )
        response.raise_for_status()
        
        return {}
    
    def _find_resource(
        self,
        ansible_data: Any,
        mixin_class: type,
        context: dict
    ) -> dict:
        """
        Find resource by identifier.
        
        Args:
            ansible_data: Ansible dataclass instance
            mixin_class: Transform mixin class
            context: Transformation context
        
        Returns:
            Found resource as dict (Ansible format)
        """
        # Get endpoint operations from mixin
        operations = mixin_class.get_endpoint_operations()
        
        # Find get/list operation
        get_op = None
        for op_name, op in operations.items():
            if op.method == 'GET':
                get_op = op
                break
        
        if not get_op:
            raise ValueError("No GET operation defined for this resource")
        
        # Build URL - use unique field from ansible_data
        # For now, assume we can query by name or ID
        unique_field = getattr(ansible_data, 'username', None) or getattr(ansible_data, 'name', None) or getattr(ansible_data, 'id', None)
        
        if unique_field:
            url = self._build_url(f"{get_op.path.rstrip('/')}/{unique_field}/")
        else:
            url = self._build_url(get_op.path)
        
        # Make GET request
        logger.debug(f"Calling GET {url}")
        response = self.session.get(
            url,
            timeout=self.request_timeout,
            verify=self.verify_ssl
        )
        response.raise_for_status()
        
        api_result = response.json()
        
        # REVERSE TRANSFORM: API → Ansible
        api_result_instance = type(ansible_data).__class__(**api_result)
        ansible_result = api_result_instance.to_ansible(context)
        return asdict(ansible_result)
    
    def _execute_operations(
        self,
        operations: Dict,
        api_data: Any,
        context: dict,
        required_for: str = None
    ) -> dict:
        """
        Execute potentially multiple API endpoint operations.
        
        Args:
            operations: Dict of EndpointOperations
            api_data: API dataclass instance
            context: Context
            required_for: Filter operations by required_for field
        
        Returns:
            Combined API response dict
        """
        # Filter operations
        relevant_ops = {
            name: op for name, op in operations.items()
            if op.required_for is None or op.required_for == required_for
        }
        
        # Sort by dependencies and order
        sorted_ops = self._sort_operations(relevant_ops)
        
        # Execute in order
        results = {}
        api_data_dict = asdict(api_data)
        
        for op_name in sorted_ops:
            endpoint_op = relevant_ops[op_name]
            
            # Extract fields for this endpoint
            request_data = {}
            for field in endpoint_op.fields:
                if field in api_data_dict and api_data_dict[field] is not None:
                    request_data[field] = api_data_dict[field]
            
            if not request_data:
                logger.debug(f"Skipping {op_name} - no data")
                continue
            
            # Build URL with path parameters
            path = endpoint_op.path
            if endpoint_op.path_params:
                for param in endpoint_op.path_params:
                    if param in results:
                        path = path.replace(f'{{{param}}}', str(results[param]))
                    elif param == 'id' and 'id' in api_data_dict:
                        path = path.replace(f'{{{param}}}', str(api_data_dict['id']))
            
            url = self._build_url(path)
            
            # Make API call
            logger.debug(f"Calling {endpoint_op.method} {url}")
            response = self.session.request(
                endpoint_op.method,
                url,
                json=request_data,
                timeout=self.request_timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            
            # Store result
            result_data = response.json() if response.content else {}
            results[op_name] = result_data
            
            # Store ID for dependent operations
            if 'id' in result_data and 'id' not in results:
                results['id'] = result_data['id']
        
        # Return main result
        return results.get('create') or results.get('update') or results.get('main') or {}
    
    def _sort_operations(self, operations: Dict) -> list:
        """
        Sort operations by dependencies and order.
        
        Args:
            operations: Dict of EndpointOperations
        
        Returns:
            List of operation names in execution order
        """
        sorted_ops = []
        remaining = dict(operations)
        
        # Topological sort based on depends_on
        while remaining:
            # Find operations with no unmet dependencies
            ready = [
                name for name, op in remaining.items()
                if op.depends_on is None or op.depends_on in sorted_ops
            ]
            
            if not ready:
                raise ValueError(
                    f"Circular dependency in operations: "
                    f"{list(remaining.keys())}"
                )
            
            # Sort ready operations by order field
            ready.sort(key=lambda name: remaining[name].order)
            
            # Add first ready operation
            sorted_ops.append(ready[0])
            remaining.pop(ready[0])
        
        return sorted_ops
    
    # Helper methods for transformations (called via context)
    
    def lookup_org_ids(self, org_names: list) -> list:
        """
        Convert organization names to IDs.
        
        Args:
            org_names: List of organization names
        
        Returns:
            List of organization IDs
        """
        ids = []
        for name in org_names:
            # Check cache
            cache_key = f'org_name:{name}'
            if cache_key in self.cache:
                ids.append(self.cache[cache_key])
                continue
            
            # API lookup
            url = self._build_url('organizations', query_params={'name': name})
            response = self.session.get(
                url,
                timeout=self.request_timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            results = response.json().get('results', [])
            
            if results:
                org_id = results[0]['id']
                self.cache[cache_key] = org_id
                ids.append(org_id)
            else:
                raise ValueError(f"Organization '{name}' not found")
        
        return ids
    
    def lookup_org_names(self, org_ids: list) -> list:
        """
        Convert organization IDs to names.
        
        Args:
            org_ids: List of organization IDs
        
        Returns:
            List of organization names
        """
        names = []
        for org_id in org_ids:
            # Check reverse cache
            cache_key = f'org_id:{org_id}'
            if cache_key in self.cache:
                names.append(self.cache[cache_key])
                continue
            
            # API lookup
            url = self._build_url(f'organizations/{org_id}/')
            response = self.session.get(
                url,
                timeout=self.request_timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            org = response.json()
            
            name = org['name']
            self.cache[cache_key] = name
            self.cache[f'org_name:{name}'] = org_id  # Store both directions
            names.append(name)
        
        return names


class PlatformManager(ThreadingMixIn, BaseManager):
    """
    Custom Manager for sharing PlatformService across processes.
    
    Uses ThreadingMixIn to handle concurrent client connections.
    """
    daemon_threads = True


