"""Platform SDK - Gateway Configuration.

Generic configuration extraction for platform gateway connections.
This module is part of the platform SDK and is not Ansible-specific.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Environment variable names for each connection parameter, in priority order
# (first name found wins).  These mirror the ``env_fallback`` lists in
# plugins/module_utils/aap_module.py (legacy module path) and the ``env:`` keys
# in plugins/doc_fragments/auth_lookup.py (lookup plugin path) so that all three
# entry points honour the same variables with the same GATEWAY_* over AAP_*
# precedence.
_ENV_ALIASES: Dict[str, Tuple[str, ...]] = {
    "hostname": ("GATEWAY_HOSTNAME", "AAP_HOSTNAME"),
    "username": ("GATEWAY_USERNAME", "AAP_USERNAME"),
    "password": ("GATEWAY_PASSWORD", "AAP_PASSWORD"),
    "token": ("GATEWAY_API_TOKEN", "AAP_TOKEN"),
    "validate_certs": ("GATEWAY_VERIFY_SSL", "AAP_VALIDATE_CERTS"),
    "request_timeout": ("GATEWAY_REQUEST_TIMEOUT", "AAP_REQUEST_TIMEOUT"),
}

# Strings accepted as boolean values from the environment, matching the
# conversions performed by ansible.module_utils.parsing.convert_bool.boolean.
# Parsed locally so this SDK module stays importable outside Ansible.
_BOOLEAN_TRUE = frozenset(("y", "yes", "on", "1", "true", "t"))
_BOOLEAN_FALSE = frozenset(("n", "no", "off", "0", "false", "f"))


@dataclass
class GatewayConfig:
    """Gateway connection configuration.

    This is a generic configuration object that can be used by any
    entry point (Ansible, CLI, MCP, etc.).
    """

    base_url: str
    username: Optional[str] = None
    password: Optional[str] = None
    oauth_token: Optional[str] = None
    verify_ssl: bool = True
    ca_bundle: Optional[str] = None
    request_timeout: float = 10.0
    connection_mode: str = "standard"  # "standard" or "experimental"
    idle_timeout: float = 3600.0
    max_retries: Optional[int] = None
    retry_backoff_factor: Optional[int] = None

    def __post_init__(self):
        """Normalize the URL and validate optional retry settings."""
        self.max_retries = _parse_retry_setting("aap_max_retries", self.max_retries, minimum=0)
        self.retry_backoff_factor = _parse_retry_setting("aap_retry_backoff_factor", self.retry_backoff_factor, minimum=1)
        original_url = self.base_url
        self.base_url = self._normalize_url(self.base_url)
        if original_url != self.base_url:
            logger.debug(
                "Normalized gateway URL: %s -> %s",
                original_url,
                self.base_url,
            )
        logger.info(
            "GatewayConfig initialized: base_url=%s, verify_ssl=%s, ca_bundle=%s, timeout=%s, idle_timeout=%s",
            self.base_url,
            self.verify_ssl,
            self.ca_bundle,
            self.request_timeout,
            self.idle_timeout,
        )

    @property
    def has_retry_settings(self) -> bool:
        """Whether either transient retry setting was supplied."""
        return self.max_retries is not None or self.retry_backoff_factor is not None

    @property
    def requests_verify(self) -> Union[bool, str]:
        """Value passed to requests ``verify=`` for TLS validation."""
        if not self.verify_ssl:
            return False
        if self.ca_bundle:
            return self.ca_bundle
        return True

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Normalize gateway URL.

        Args:
            url: Gateway URL (may or may not have protocol)

        Returns:
            Normalized URL with protocol
        """
        if not url:
            return url

        if not url.startswith(("https://", "http://")):
            return f"https://{url}"

        return url


def _env_first(env: Mapping[str, str], key: str) -> Optional[str]:
    """Return the first non-empty environment value for ``key``.

    Args:
        env: Environment mapping to read from.
        key: Logical parameter name, a key of :data:`_ENV_ALIASES`.

    Returns:
        The first non-empty value found, or None when no alias is set.
    """
    for name in _ENV_ALIASES[key]:
        value = env.get(name)
        # Skip both unset and empty-string values; an exported-but-empty
        # variable should fall through to the next alias or the default.
        if value:
            return value
    return None


def _env_boolean(value: str) -> bool:
    """Convert an environment string to a boolean.

    Environment variables are always strings, so ``bool()`` cannot be used:
    ``bool("false")`` is True.

    Args:
        value: Raw string read from the environment.

    Returns:
        The parsed boolean.

    Raises:
        ValueError: If the string is not a recognized boolean value.
    """
    normalized = str(value).strip().lower()
    if normalized in _BOOLEAN_TRUE:
        return True
    if normalized in _BOOLEAN_FALSE:
        return False
    raise ValueError(f"Invalid boolean value for gateway validate_certs environment variable: {value!r}")


def _resolve_validate_certs(
    task_args: Dict[str, Any],
    host_vars: Dict[str, Any],
    env: Mapping[str, str],
) -> Any:
    """Return the TLS verification setting from task, inventory or environment scope.

    Uses ``key in dict`` rather than ``a or b`` chaining so that an explicit
    ``False`` is honoured.  The environment is consulted — and parsed — only
    when neither task nor inventory supplies a value, so an unparsable
    ``GATEWAY_VERIFY_SSL`` cannot break a run that overrides it.

    Aliases: aap_validate_certs (primary), gateway_validate_certs, validate_certs (legacy).

    Args:
        task_args: Task/command arguments (highest priority).
        host_vars: Host/inventory variables (middle priority).
        env: Environment mapping (lowest priority).

    Returns:
        The resolved value, defaulting to True (verify TLS certificates).

    Raises:
        ValueError: If the environment value is used and is not a valid boolean.
    """
    keys = ("aap_validate_certs", "gateway_validate_certs", "validate_certs")
    for scope in (task_args, host_vars):
        for key in keys:
            if key in scope:
                return scope[key]
    env_value = _env_first(env, "validate_certs")
    if env_value is not None:
        return _env_boolean(env_value)
    return True  # default: verify SSL


def _extract_persistent_manager_idle_timeout(
    task_args: Dict[str, Any],
    host_vars: Dict[str, Any],
) -> Optional[Any]:
    """Return ``persistent_manager_idle_timeout`` if set in task or host scope (including ``0``).

    Controls how long the *local* manager process on the control node may stay
    idle before exiting; it is not a gateway server-side timeout.

    Uses ``key in dict`` so ``0`` is not dropped (unlike ``a or b`` chains).
    Task arguments override host/inventory variables.
    """
    if "persistent_manager_idle_timeout" in task_args:
        return task_args["persistent_manager_idle_timeout"]
    if "persistent_manager_idle_timeout" in host_vars:
        return host_vars["persistent_manager_idle_timeout"]
    return None


def _resolve_ca_bundle(
    task_args: Dict[str, Any],
    host_vars: Dict[str, Any],
) -> Optional[str]:
    """Return a CA bundle path from task or inventory scope.

    Aliases: aap_ca_bundle (primary), gateway_ca_bundle, ansible_platform_ca_bundle.
    Task arguments override host/inventory variables.
    """
    _ca_bundle_keys = ("aap_ca_bundle", "gateway_ca_bundle", "ansible_platform_ca_bundle")
    for scope in (task_args, host_vars):
        for key in _ca_bundle_keys:
            if key in scope:
                value = scope[key]
                if value is not None and value != "":
                    return str(value)
    return None


def _parse_retry_setting(name: str, value: Any, minimum: int) -> Optional[int]:
    """Parse a configured integer without coercing booleans or fractions."""
    if value is None:
        return None

    message = f"{name} must be an integer greater than or equal to {minimum}"
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(message)
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(message) from error
    if parsed < minimum:
        raise ValueError(message)
    return parsed


def _resolve_retry_setting(name: str, task_args: Mapping[str, Any], host_vars: Mapping[str, Any], environment: Mapping[str, Any]) -> Any:
    """Return the first supplied value in task, inventory, or environment scope."""
    canonical_name = f"aap_{name}"
    for scope in (task_args, host_vars):
        for key in (canonical_name, name):
            value = scope.get(key)
            if value is not None:
                return value
    return environment.get(canonical_name.upper())


def extract_gateway_config(
    task_args: Optional[Dict[str, Any]] = None,
    host_vars: Optional[Dict[str, Any]] = None,
    required: bool = True,
    environment: Optional[Mapping[str, Any]] = None,
) -> GatewayConfig:
    """
    Extract gateway configuration from task arguments, host variables and the environment.

    This is a generic function that extracts gateway configuration from
    any dict-like structure. It's not Ansible-specific and can be used
    by CLI tools, MCP tools, or other entry points.

    Resolution order per parameter is task_args, then host_vars, then
    environment variables, then the built-in default.  Environment variables
    rank below inventory variables to match Ansible's own plugin configuration
    precedence (ansible/config/manager.py resolves vars before env).

    Args:
        task_args: Task/command arguments (highest priority)
        host_vars: Host/inventory variables (middle priority)
        required: Whether gateway_url is required (default: True)
        environment: Environment mapping (lowest priority), used for the
            connection, TLS, timeout and retry settings. Defaults to
            os.environ; pass an explicit mapping (for example ``{}``) to make
            callers such as unit tests independent of the ambient environment.

    Returns:
        GatewayConfig object with normalized values

    Raises:
        ValueError: If required gateway_url is missing, or if an environment
            variable holds an unparsable boolean or timeout value.
    """
    task_args = task_args or {}
    host_vars = host_vars or {}
    environment = os.environ if environment is None else environment

    logger.debug(
        "Extracting gateway config from task_args (keys: %s) and host_vars (keys: %s)",
        list(task_args.keys()),
        list(host_vars.keys()),
    )

    # Get gateway URL from task args first, then host_vars, then the environment.
    # Aliases: aap_hostname (primary), gateway_hostname, gateway_url (legacy).
    gateway_url = (
        task_args.get("aap_hostname")
        or task_args.get("gateway_hostname")
        or task_args.get("gateway_url")
        or host_vars.get("aap_hostname")
        or host_vars.get("gateway_hostname")
        or host_vars.get("gateway_url")
        or _env_first(environment, "hostname")
    )
    logger.debug("Gateway URL extracted: %s", gateway_url)

    # Get auth parameters from task args first, then host_vars, then the environment.
    # Aliases: aap_username/aap_password/aap_token (primary), gateway_* (legacy).
    gateway_username = (
        task_args.get("aap_username")
        or task_args.get("gateway_username")
        or host_vars.get("aap_username")
        or host_vars.get("gateway_username")
        or _env_first(environment, "username")
    )
    gateway_password = (
        task_args.get("aap_password")
        or task_args.get("gateway_password")
        or host_vars.get("aap_password")
        or host_vars.get("gateway_password")
        or _env_first(environment, "password")
    )

    # Only credentials given explicitly in the task or inventory suppress the
    # token fallbacks below.  Environment credentials must NOT, because the
    # environment ranks below inventory: an exported GATEWAY_USERNAME left over
    # in a developer shell would otherwise discard an inventory aap_token and
    # leave a username with no password and no token.
    has_explicit_credentials = bool(
        task_args.get("aap_username")
        or task_args.get("gateway_username")
        or host_vars.get("aap_username")
        or host_vars.get("gateway_username")
        or task_args.get("aap_password")
        or task_args.get("gateway_password")
        or host_vars.get("aap_password")
        or host_vars.get("gateway_password")
    )
    gateway_token_raw = (
        task_args.get("aap_token")
        or task_args.get("gateway_token")
        or host_vars.get("gateway_token")
        or
        # Only fall back to the aap_token ansible_fact when no username/password
        # credentials are available.  The token module stores a read-scoped token
        # in aap_token after creation; picking it up here would cause all
        # subsequent tasks in the same play to authenticate as that limited token
        # instead of the admin user, leading to 403 errors.
        (host_vars.get("aap_token") if not has_explicit_credentials else None)
        # Same guard for the environment: an exported token must not override
        # username/password credentials supplied by the task or inventory.
        or (_env_first(environment, "token") if not has_explicit_credentials else None)
    )
    # The token module sets aap_token as a dict ({"token": "...", "id": ...}).
    # Extract the actual token string if we got a dict.
    if isinstance(gateway_token_raw, dict):
        gateway_token = gateway_token_raw.get("token")
    else:
        gateway_token = gateway_token_raw

    gateway_validate_certs = _resolve_validate_certs(task_args, host_vars, environment)

    # Resolve request_timeout aliases: aap_request_timeout (primary), gateway_request_timeout,
    # request_timeout (legacy).  Environment values are strings, so cast to float.
    _request_timeout_env = _env_first(environment, "request_timeout")
    gateway_request_timeout = (
        task_args.get("aap_request_timeout")
        or task_args.get("gateway_request_timeout")
        or task_args.get("request_timeout")
        or host_vars.get("aap_request_timeout")
        or host_vars.get("gateway_request_timeout")
        or host_vars.get("request_timeout")
        or (float(_request_timeout_env) if _request_timeout_env is not None else None)
        or 10.0
    )
    # Local persistent manager idle shutdown (not a gateway session timeout).
    # Default: 3600 s. Set to 0 to disable. See _extract_persistent_manager_idle_timeout.
    pm_idle_timeout = _extract_persistent_manager_idle_timeout(task_args, host_vars)
    gateway_ca_bundle = _resolve_ca_bundle(task_args, host_vars)
    # Connection mode: "standard" (default) or "experimental" (persistent manager)
    connection_mode = task_args.get("platform_connection_mode") or host_vars.get("platform_connection_mode") or "standard"

    if required and not gateway_url:
        logger.error("Gateway URL is required but not found in task_args or host_vars")
        raise ValueError("gateway_url or gateway_hostname must be provided as task parameter or defined in inventory")

    # Log auth method being used (without exposing secrets)
    if gateway_token:
        auth_method = "token"
    elif gateway_username:
        auth_method = "username/password"
    else:
        auth_method = "none"
    logger.info(
        "Gateway config extracted: url=%s, auth_method=%s, verify_ssl=%s, ca_bundle=%s, timeout=%s",
        gateway_url,
        auth_method,
        gateway_validate_certs,
        gateway_ca_bundle,
        gateway_request_timeout,
    )

    config = GatewayConfig(
        base_url=gateway_url or "",
        username=gateway_username,
        password=gateway_password,
        oauth_token=gateway_token,
        verify_ssl=gateway_validate_certs,
        ca_bundle=gateway_ca_bundle,
        request_timeout=gateway_request_timeout,
        connection_mode=connection_mode,
        idle_timeout=(float(pm_idle_timeout) if pm_idle_timeout is not None else 3600.0),
        max_retries=_resolve_retry_setting("max_retries", task_args, host_vars, environment),
        retry_backoff_factor=_resolve_retry_setting("retry_backoff_factor", task_args, host_vars, environment),
    )

    logger.debug("GatewayConfig created successfully")
    return config
