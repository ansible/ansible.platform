#!/usr/bin/env python
# -*- coding: utf-8 -*-

# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Base action plugin for platform resource modules.

Provides a data-driven run() that eliminates per-module boilerplate.
Each resource action plugin declares USER_MODEL (dotted import path to
the Ansible Model dataclass) and the base class handles the rest.

All resource metadata lives on the Ansible Model class itself (via
BaseTransformMixin): MODULE_NAME, SCOPE_PARAM, CANONICAL_KEY,
SYSTEM_KEY, SUPPORTS_DELETE, VALID_STATES.  The base run() loads the
model class, syncs its metadata onto ``self``, then dispatches.

Follows the standard Ansible network resource module pattern:
  1. Gather current state → ``before``
  2. Apply desired mutations based on ``state``
  3. Gather resulting state → ``after``
  4. ``changed = (before != after)``

Supported states (set theory):
  gathered:    Read-only — return current config
  merged:      C' = C ∪ D   (additive: add new, merge fields into existing)
  replaced:    C' = (C \\ K(D)) ∪ D  (item-level: replace matching items only)
  overridden:  C' = D  (set equality: result is exactly desired set)
  deleted:     C' = C \\ D  (set difference: remove matching items)

Subclass contract (minimal):
    class ActionModule(BaseResourceActionPlugin):
        USER_MODEL = 'plugins.plugin_utils.ansible_models.user.AnsibleUser'

Identity categories (see docs/05-design-principles.md):
    Category A: CANONICAL_KEY set, SYSTEM_KEY=None  — user key IS the API key
    Category B: CANONICAL_KEY set, SYSTEM_KEY set   — match by canonical, resolve system
    Category C: CANONICAL_KEY=None, SYSTEM_KEY set  — gather-first, match by content
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import base64
import importlib
import json
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, Union

import yaml
from ansible.errors import AnsibleError
from ansible.module_utils.common.arg_spec import ArgumentSpecValidator
from ansible.plugins.action import ActionBase
from ansible.utils.display import Display

if TYPE_CHECKING:
    from ansible_collections.ansible.platform.plugins.plugin_utils.manager.rpc_client import ManagerRPCClient
    from ansible_collections.ansible.platform.plugins.plugin_utils.platform.direct_client import DirectHTTPClient

# ---------------------------------------------------------------------------
# Logging strategy for action plugins
# ---------------------------------------------------------------------------
# Action plugins always use self._display (Ansible-native) instead of Python's
# logging module.  self._display writes to BOTH the terminal (at the right
# verbosity level) AND ANSIBLE_LOG_PATH unconditionally.
#
# Verbosity mapping used throughout this file:
#   self._display.vvvv(msg)    DEBUG
#   self._display.vvv(msg)     INFO
#   self._display.vv(msg)      INFO
#   self._display.warning(msg) WARNING
#   self._display.error(msg)   ERROR
# ---------------------------------------------------------------------------
display = Display()


def _manager_process_entry(
    socket_path,
    socket_dir,
    inventory_hostname,
    gateway_url,
    gateway_username,
    gateway_password,
    gateway_token,
    gateway_validate_certs,
    gateway_request_timeout,
    authkey_b64,
    sys_path,
):
    """
    Entry point for the manager process.

    This is a module-level function so it can be pickled for multiprocessing.spawn.
    Uses the same pattern as python-multiproc repository.
    """
    import base64
    import sys
    import traceback
    from pathlib import Path

    # Redirect stderr to a file for debugging
    error_log_path = Path(socket_dir) / f"manager_error_{inventory_hostname}.log"
    stderr_log = Path(socket_dir) / f"manager_stderr_{inventory_hostname}.log"

    try:
        sys.stderr = open(stderr_log, "w", buffering=1)
        sys.stdout = open(stderr_log, "a", buffering=1)
    except Exception:
        pass  # Continue without redirecting

    try:
        # Restore parent's sys.path in child process (spawn starts fresh)
        sys.path = sys_path

        # Decode authkey from base64 string
        authkey = base64.b64decode(authkey_b64.encode("utf-8"))

        # Write to log immediately to capture any early failures
        with open(error_log_path, "w") as f:
            f.write(f"Process started, socket_path={socket_path}\n")
            f.write(f"sys.path has {len(sys_path)} entries\n")
            f.write(f"Manager starting at {socket_path}\n")
            f.write(f"About to create service with base_url={gateway_url}\n")
            f.flush()
    except Exception as e:
        # Can't even write to log, print to stderr
        print(f"ERROR in early startup: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    try:
        from ansible_collections.ansible.platform.plugins.plugin_utils.manager.platform_manager import PlatformManager, PlatformService
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import GatewayConfig

        with open(error_log_path, "a") as f:
            f.write("Imports successful\n")
            f.flush()

        # Create GatewayConfig
        try:
            config = GatewayConfig(
                base_url=gateway_url,
                username=gateway_username,
                password=gateway_password,
                oauth_token=gateway_token,
                verify_ssl=gateway_validate_certs,
                request_timeout=gateway_request_timeout,
                connection_mode="experimental",
            )
            with open(error_log_path, "a") as f:
                f.write("GatewayConfig created successfully\n")
                f.flush()
        except Exception as config_err:
            with open(error_log_path, "a") as f:
                f.write(f"GatewayConfig creation failed: {config_err}\n")
                f.write(traceback.format_exc())
                f.flush()
            raise

        # Create service
        try:
            service = PlatformService(config)
            with open(error_log_path, "a") as f:
                f.write("Service created successfully\n")
                f.flush()
        except Exception as service_err:
            with open(error_log_path, "a") as f:
                f.write(f"Service creation failed: {service_err}\n")
                f.write(traceback.format_exc())
                f.flush()
            raise

        with open(error_log_path, "a") as f:
            f.write("Service created\n")
            f.flush()

        # Register with manager
        _service_ref = [service]

        def _get_service():
            return _service_ref[0]

        PlatformManager.register("get_platform_service", callable=_get_service)

        with open(error_log_path, "a") as f:
            f.write("Service registered\n")
            f.flush()

        # Create manager instance
        manager = PlatformManager(address=socket_path, authkey=authkey)

        with open(error_log_path, "a") as f:
            f.write("Manager instance created\n")
            f.flush()

        # Start manager server
        server = manager.get_server()

        with open(error_log_path, "a") as f:
            f.write("Server obtained, starting serve_forever()\n")
            f.flush()

        server.serve_forever()

    except Exception as e:
        with open(error_log_path, "a") as f:
            f.write(f"\n\nManager startup failed: {e}\n")
            f.write(traceback.format_exc())
        sys.exit(1)


class BaseResourceActionPlugin(ActionBase):
    """Data-driven base action plugin for all platform resource modules.

    Subclasses declare the Ansible Model import path:

        class ActionModule(BaseResourceActionPlugin):
            USER_MODEL = 'plugins.plugin_utils.ansible_models.user.AnsibleUser'

    All resource metadata (MODULE_NAME, SCOPE_PARAM, CANONICAL_KEY, etc.)
    is read from the Ansible Model class at runtime.
    """

    # The only attribute subclasses must set
    USER_MODEL: str = None

    # Defaults — overridden by _sync_model_metadata() from Ansible Model
    MODULE_NAME: str = None
    SCOPE_PARAM: str = None
    CANONICAL_KEY: str = None
    SYSTEM_KEY: str = "id"
    SUPPORTS_DELETE: bool = True
    VALID_STATES: frozenset = frozenset(
        {
            "merged",
            "replaced",
            "overridden",
            "deleted",
            "gathered",
        }
    )
    # Fields that are user-input-only (transformed to other fields before API call,
    # never returned by the API, and must be excluded from before/after comparisons).
    INPUT_ONLY_FIELDS: frozenset = frozenset()

    _user_model_cls = None

    # Class-level tracking of spawned manager processes
    _spawned_processes = {}  # type: dict

    _AUTH_PARAMS = frozenset(
        {
            "gateway_hostname",
            "gateway_username",
            "gateway_password",
            "gateway_token",
            "gateway_validate_certs",
            "gateway_request_timeout",
            "aap_hostname",
            "aap_username",
            "aap_password",
            "aap_token",
            "aap_validate_certs",
            "aap_request_timeout",
        }
    )

    @property
    def _match_key(self) -> str:
        """The field used to index and match resources.

        Returns CANONICAL_KEY when set (Categories A and B), otherwise
        falls back to SYSTEM_KEY (Category C — gather-first resources).
        """
        return self.CANONICAL_KEY or self.SYSTEM_KEY

    # ------------------------------------------------------------------ #
    #  Model resolution and metadata sync                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _resolve_plugin_path(dotted_path: str) -> str:
        """Rewrite a 'plugins.plugin_utils...' path to the real namespace.

        When Ansible loads the collection, the package prefix is
        'ansible_collections.ansible.platform.plugins.plugin_utils', not
        bare 'plugins.plugin_utils'. Detect the correct prefix from
        this module's own __name__.
        """
        _DEV_PREFIX = "plugins.plugin_utils"
        if dotted_path.startswith(_DEV_PREFIX):
            my_name = __name__
            parts = my_name.split(".")
            if "plugins" in parts:
                idx = parts.index("plugins")
                real_prefix = ".".join(parts[:idx]) + "." + _DEV_PREFIX
                return real_prefix + dotted_path[len(_DEV_PREFIX) :]
        return dotted_path

    def _get_user_model_class(self):
        """Lazily resolve USER_MODEL dotted path to a class object.

        On first load, syncs resource metadata (MODULE_NAME, SCOPE_PARAM,
        CANONICAL_KEY, SYSTEM_KEY, SUPPORTS_DELETE, VALID_STATES) from the
        Ansible Model class onto this action plugin instance.
        """
        if self._user_model_cls is not None:
            return self._user_model_cls

        if not self.USER_MODEL:
            raise AnsibleError(f"{type(self).__name__}.USER_MODEL is not set")

        resolved = self._resolve_plugin_path(self.USER_MODEL)
        module_path, class_name = resolved.rsplit(".", 1)
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        type(self)._user_model_cls = cls

        _UNSET = object()
        for attr in ("MODULE_NAME", "SCOPE_PARAM", "CANONICAL_KEY", "SYSTEM_KEY", "SUPPORTS_DELETE", "VALID_STATES", "INPUT_ONLY_FIELDS"):
            model_val = getattr(cls, attr, _UNSET)
            if model_val is not _UNSET:
                # Sync even when the model explicitly sets the attribute to None
                # (e.g. SYSTEM_KEY = None for singleton resources).
                # Set on both instance and subclass so future instances see it.
                setattr(self, attr, model_val)
                setattr(type(self), attr, model_val)

        return cls

    # ------------------------------------------------------------------ #
    #  Index & match helpers                                               #
    # ------------------------------------------------------------------ #

    def _index_by_key(self, items: list, key: str) -> dict:
        """Index a list of resource dicts by *key*, detecting duplicates."""
        index = {}
        for item in items:
            k = str(item.get(key, ""))
            if not k:
                continue
            if k in index and key == self.CANONICAL_KEY and self.SYSTEM_KEY:
                raise AnsibleError(f"Duplicate {key}='{k}' found in existing resources. Provide '{self.SYSTEM_KEY}' in your config to disambiguate.")
            index[k] = item
        return index

    def _match_by_content(self, item, candidates):
        """Content-based fallback for Category C resources."""
        comparison_item = self._strip_input_only(item)
        for candidate in candidates:
            if self._config_matches(comparison_item, candidate):
                return candidate
        return None

    def _prepare_user_data(self, item, current, user_cls):
        """Build user_data, injecting the system key from a matched resource."""
        effective_item = dict(item)
        if self.SYSTEM_KEY and current is not None:
            if not effective_item.get(self.SYSTEM_KEY):
                effective_item[self.SYSTEM_KEY] = current.get(self.SYSTEM_KEY)
        return effective_item

    # ------------------------------------------------------------------ #
    #  Data-driven run()                                                   #
    # ------------------------------------------------------------------ #

    def run(self, tmp=None, task_vars=None):
        """Data-driven resource module execution.

        Follows the standard Ansible network resource module pattern:
          1. Gather current state → ``before``
          2. Apply desired mutations based on ``state``
          3. Gather resulting state → ``after``
          4. ``changed = (before != after)``

        Supports ``--check`` (dry-run) and ``--diff`` modes.

        Return structure matches cisco.ios / cisco.nxos conventions::

            {
                "before": [ ... ],   # config before this run
                "after":  [ ... ],   # config after this run
                "changed": bool,
                "gathered": [ ... ], # only for state=gathered
                "diff": { ... },     # only when --diff is active
            }
        """
        super().run(tmp, task_vars)
        if task_vars is None:
            task_vars = {}

        self._task_vars = task_vars
        args = self._task.args.copy()

        try:
            self._get_user_model_class()

            doc = self._get_documentation()
            if doc:
                argspec = self._build_argspec_from_docs(doc)
                validated_args = self._validate_data(args, argspec, "input")
            else:
                raise AnsibleError("Could not load DOCUMENTATION for %s module" % self.MODULE_NAME)

            state = validated_args.get("state", "merged")
            config = validated_args.get("config", [])

            if state not in self.VALID_STATES:
                raise AnsibleError(f"Unknown state: {state}. Valid states: {sorted(self.VALID_STATES)}")

            # ---- manager connection ----------------------------------------
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            self._client = manager

            # -- gathered: read-only, no before/after -----------------------
            if state == "gathered":
                gathered = self._do_gathered(manager, config)
                if argspec and gathered:
                    gathered = self._validate_output(gathered, argspec)
                return self._build_result(
                    failed=False,
                    changed=False,
                    gathered=gathered,
                    config=config,
                    facts_to_set=facts_to_set,
                )

            # -- mutating states: before → apply → after --------------------
            # before/after always capture the full platform state so the caller
            # can see the complete picture.  config reflects only the items the
            # user asked to manage (their input), never the full gathered set.
            before = self._do_gathered(manager, None)
            if argspec and before:
                before = self._validate_output(before, argspec)

            # -- check mode: predict after without applying -----------------
            if self._task.check_mode:
                after = self._predict_after(state, before, config)
                changed = self._lists_differ(before, after)
                return self._build_result(
                    failed=False,
                    changed=changed,
                    before=before,
                    after=after,
                    config=config,
                    facts_to_set=facts_to_set,
                )

            if state in ("deleted", "overridden") and not self.SUPPORTS_DELETE:
                raise AnsibleError(f"State '{state}' requires delete capability, but {self.__class__.__name__} has SUPPORTS_DELETE=False.")

            if state == "deleted":
                self._apply_deleted(manager, config, before)
            elif state == "overridden":
                self._apply_overridden(manager, config, before)
            else:  # merged, replaced
                self._apply_merged_or_replaced(manager, config, state, before)

            after = self._do_gathered(manager, None)
            if argspec and after:
                after = self._validate_output(after, argspec)

            changed = self._lists_differ(before, after)

            return self._build_result(
                failed=False,
                changed=changed,
                before=before,
                after=after,
                config=config,
                facts_to_set=facts_to_set,
            )
        except Exception as e:
            import traceback as _tb

            self._display.vvv("Error in %s action plugin: %s" % (self.MODULE_NAME, e))
            result = {"failed": True, "msg": str(e) or f"{type(e).__name__} (no message)"}
            if self._display.verbosity >= 3:
                result["exception"] = _tb.format_exc()
            return result

    def _build_result(self, facts_to_set=None, **kwargs):
        """Build result dict, injecting ansible_facts and optional diff."""
        result = dict(kwargs)
        if facts_to_set:
            result["ansible_facts"] = facts_to_set
            result["_ansible_facts_cacheable"] = True
        if (
            getattr(self._task, "diff", False)
            and "before" in result
            and "after" in result
            and result.get("before") is not None
            and result.get("after") is not None
        ):
            result["diff"] = {
                "before": yaml.dump(
                    result["before"],
                    default_flow_style=False,
                    sort_keys=True,
                ),
                "after": yaml.dump(
                    result["after"],
                    default_flow_style=False,
                    sort_keys=True,
                ),
            }
        return result

    # ------------------------------------------------------------------ #
    #  State dispatch helpers                                              #
    # ------------------------------------------------------------------ #

    def _do_gathered(self, manager, config):
        """Gather current resource state (read-only).

        When config is None, gathers ALL resources of this type.
        When config is a list, gathers only the specified items.
        """
        results = []
        for item in config or [{}]:
            try:
                result = manager.execute("find", self.MODULE_NAME, item)
                if isinstance(result, dict) and "config" in result:
                    results.extend(result["config"])
                elif isinstance(result, list):
                    results.extend(result)
                elif isinstance(result, dict):
                    results.append(result)
            except Exception:
                # If a specific item isn't found, skip it
                pass
        return results

    def _apply_deleted(self, manager, config, before):
        """Delete specified resources.

        Matches by canonical key (or system key for Category C).
        Skips items not present in ``before`` (already absent).
        """
        match_key = self._match_key
        if not match_key:
            return

        before_by_key = self._index_by_key(before, match_key)
        before_by_sys = self._index_by_key(before, self.SYSTEM_KEY) if self.SYSTEM_KEY else {}

        for item in config:
            current = None
            if self.SYSTEM_KEY and item.get(self.SYSTEM_KEY):
                current = before_by_sys.get(str(item[self.SYSTEM_KEY]))
            elif match_key and item.get(match_key):
                current = before_by_key.get(str(item[match_key]))
            elif not self.CANONICAL_KEY and self.SYSTEM_KEY:
                current = self._match_by_content(item, before)

            if current is None:
                continue

            user_data = self._prepare_user_data(item, current, None)
            manager.execute("delete", self.MODULE_NAME, user_data)

    def _apply_merged_or_replaced(self, manager, config, state, before):
        """Create or update resources, skipping items already at desired state.

        Uses ``before`` to decide create vs update and to skip no-ops.
        """
        match_key = self._match_key
        cat_c = not self.CANONICAL_KEY and self.SYSTEM_KEY

        before_by_key = self._index_by_key(before, match_key) if match_key else {}
        before_by_sys = self._index_by_key(before, self.SYSTEM_KEY) if self.SYSTEM_KEY else {}

        cat_c_used = set()

        for i, item in enumerate(config):
            current = None

            if self.SYSTEM_KEY and item.get(self.SYSTEM_KEY):
                current = before_by_sys.get(str(item[self.SYSTEM_KEY]))
            elif match_key and item.get(match_key):
                current = before_by_key.get(str(item[match_key]))
            elif cat_c:
                current = self._match_by_content(item, before)
                if current is None and state != "merged":
                    for b in before:
                        b_key = str(b.get(match_key, ""))
                        if b_key and b_key not in cat_c_used:
                            current = b
                            cat_c_used.add(b_key)
                            break
                elif current is not None and current.get(match_key):
                    cat_c_used.add(str(current[match_key]))

            comparison_item = self._strip_input_only(item)
            if match_key:
                if current is not None:
                    if self._config_matches(comparison_item, current):
                        continue
                    op = "update" if state == "merged" else "replace"
                elif item.get(match_key) or item.get(self.SYSTEM_KEY):
                    op = "create"
                else:
                    op = "create"
            else:
                if before and self._config_matches(comparison_item, before[0]):
                    continue
                op = "update" if state == "merged" else "replace"

            user_data = self._prepare_user_data(item, current, None)
            manager.execute(op, self.MODULE_NAME, user_data)

    def _apply_overridden(self, manager, config, before):
        """Override: delete extras, then replace each desired item.

        Uses ``before`` (already gathered by run()) to determine extras.
        """
        match_key = self._match_key
        if not match_key:
            return

        before_by_key = self._index_by_key(before, match_key)
        desired_keys = set()
        use_content_match = not self.CANONICAL_KEY and self.SYSTEM_KEY

        for item in config:
            key_val = item.get(match_key)
            if key_val is not None:
                desired_keys.add(str(key_val))

        # Delete extras (current items not in desired set)
        matched_before = set()
        if use_content_match:
            for item in config:
                m = self._match_by_content(item, before)
                if m and m.get(match_key):
                    matched_before.add(str(m[match_key]))

        for current in before:
            current_key = str(current.get(match_key, ""))
            if not current_key:
                continue
            if current_key in desired_keys or current_key in matched_before:
                continue
            delete_item = {match_key: current.get(match_key)}
            if self.SYSTEM_KEY and current.get(self.SYSTEM_KEY):
                delete_item[self.SYSTEM_KEY] = current[self.SYSTEM_KEY]
            delete_data = self._prepare_user_data(
                delete_item,
                current,
                None,
            )
            manager.execute("delete", self.MODULE_NAME, delete_data)

        # Replace each desired item (skip no-ops)
        for item in config:
            current = None
            if match_key and item.get(match_key):
                current = before_by_key.get(str(item[match_key]))
            elif use_content_match:
                current = self._match_by_content(item, before)

            if current and self._config_matches(self._strip_input_only(item), current):
                continue

            user_data = self._prepare_user_data(item, current, None)
            op = "replace" if current is not None else "create"
            manager.execute(op, self.MODULE_NAME, user_data)

    def _strip_input_only(self, item: dict) -> dict:
        """Return a copy of *item* with INPUT_ONLY_FIELDS removed.

        INPUT_ONLY_FIELDS are user-convenience fields that get transformed to
        other API fields before the request (e.g. assignment_objects → object_id)
        and are never returned by the API.  They must be excluded from
        before/after comparisons so they don't cause spurious mismatches.
        """
        if not self.INPUT_ONLY_FIELDS:
            return item
        return {k: v for k, v in item.items() if k not in self.INPUT_ONLY_FIELDS}

    @staticmethod
    def _config_matches(desired: dict, current: dict) -> bool:
        """Check if every user-supplied field in desired matches current.

        Only compares fields explicitly provided by the user (non-None).
        Extra fields in current (from API defaults) are ignored.
        """
        for key, desired_val in desired.items():
            if desired_val is None:
                continue
            current_val = current.get(key)
            if str(desired_val) != str(current_val):
                return False
        return True

    @staticmethod
    def _lists_differ(before: list, after: list) -> bool:
        """Compare two config lists to determine if anything changed."""
        if len(before) != len(after):
            return True
        for b, a in zip(
            sorted(before, key=lambda x: str(x)),
            sorted(after, key=lambda x: str(x)),
        ):
            if b != a:
                return True
        return False

    # ------------------------------------------------------------------ #
    #  Check mode: predict after state from set theory                     #
    # ------------------------------------------------------------------ #

    def _predict_after(self, state, before, config):
        """Predict the resulting state without making API calls.

        Implements the set-theoretic state operations:
          merged:     C' = C ∪ D   (additive merge)
          replaced:   C' = (C \\ K(D)) ∪ D   (item-level replacement)
          overridden: C' = D   (set equality)
          deleted:    C' = C \\ D   (set difference)
        """
        match_key = self._match_key
        before_by_key = {}
        if match_key:
            for item in before:
                k = str(item.get(match_key, ""))
                if k:
                    before_by_key[k] = item

        if state == "deleted":
            return self._predict_deleted(before, config, before_by_key)
        elif state == "overridden":
            return self._predict_overridden(before, config, before_by_key)
        elif state == "replaced":
            return self._predict_replaced(before, config, before_by_key)
        else:  # merged
            return self._predict_merged(before, config, before_by_key)

    def _predict_merged(self, before, config, before_by_key):
        """Predict merged: union — add new items, merge fields into existing."""
        match_key = self._match_key
        result = [dict(item) for item in before]
        result_by_key = {}
        if match_key:
            for item in result:
                k = str(item.get(match_key, ""))
                if k:
                    result_by_key[k] = item

        for item in config:
            if match_key and item.get(match_key):
                key = str(item[match_key])
                existing = result_by_key.get(key)
                if existing is not None:
                    for field, val in item.items():
                        if val is not None:
                            existing[field] = val
                else:
                    new_item = dict(item)
                    result.append(new_item)
                    result_by_key[key] = new_item
            elif not self.CANONICAL_KEY and self.SYSTEM_KEY:
                existing = self._match_by_content(item, result)
                if existing is not None:
                    for field, val in item.items():
                        if val is not None:
                            existing[field] = val
                else:
                    result.append(dict(item))
            elif not match_key and before:
                for field, val in item.items():
                    if val is not None:
                        result[0][field] = val
            else:
                result.append(dict(item))
        return result

    def _predict_replaced(self, before, config, before_by_key):
        """Predict replaced: item-level replacement, untouched items preserved."""
        match_key = self._match_key
        result = [dict(item) for item in before]
        result_by_key = {}
        if match_key:
            for i, item in enumerate(result):
                k = str(item.get(match_key, ""))
                if k:
                    result_by_key[k] = i

        cat_c = not self.CANONICAL_KEY and self.SYSTEM_KEY
        cat_c_used = set()

        for i, item in enumerate(config):
            if match_key and item.get(match_key):
                key = str(item[match_key])
                idx = result_by_key.get(key)
                if idx is not None:
                    result[idx] = dict(item)
                else:
                    result.append(dict(item))
                    result_by_key[key] = len(result) - 1
            elif cat_c:
                matched = self._match_by_content(item, result)
                if matched is not None:
                    idx = result.index(matched)
                    result[idx] = dict(item)
                    if matched.get(match_key):
                        cat_c_used.add(str(matched[match_key]))
                else:
                    for j, r in enumerate(result):
                        r_key = str(r.get(match_key, ""))
                        if r_key and r_key not in cat_c_used:
                            result[j] = dict(item)
                            cat_c_used.add(r_key)
                            break
                    else:
                        result.append(dict(item))
            elif not match_key and before:
                result[0] = dict(item)
            else:
                result.append(dict(item))
        return result

    @staticmethod
    def _predict_overridden(before, config, before_by_key):
        """Predict overridden: set equality — result is exactly the desired set."""
        return [dict(item) for item in config]

    def _predict_deleted(self, before, config, before_by_key):
        """Predict deleted: set difference — remove items whose keys match."""
        match_key = self._match_key
        if not config:
            return []
        if not match_key:
            return []

        delete_keys = set()
        for item in config:
            k = item.get(match_key)
            if k is not None:
                delete_keys.add(str(k))

        if not delete_keys and not self.CANONICAL_KEY and self.SYSTEM_KEY:
            remaining = list(before)
            for item in config:
                matched = self._match_by_content(item, remaining)
                if matched:
                    remaining = [r for r in remaining if r is not matched]
            return [dict(r) for r in remaining]

        return [dict(item) for item in before if str(item.get(match_key, "")) not in delete_keys]

    # ------------------------------------------------------------------ #
    #  Manager lifecycle                                                   #
    # ------------------------------------------------------------------ #

    def _get_or_spawn_manager(self, task_vars: dict) -> Tuple[Union["DirectHTTPClient", "ManagerRPCClient"], Optional[Dict[str, Any]]]:
        """
        Dispatcher: Get connection client from the connection plugin.

        This method delegates to the connection plugin (e.g., 'ansible.platform.http')
        which handles routing between persistent and direct (ephemeral) modes.

        Returns:
            Tuple[Union[DirectHTTPClient, ManagerRPCClient], Optional[Dict[str, Any]]]:
            (client, facts_dict) where client is ManagerRPCClient (persistent or
            ephemeral) and facts_dict contains facts to set for persistent mode
            (None for direct mode).
        """
        from ansible_collections.ansible.platform.plugins.plugin_utils.platform.config import extract_gateway_config

        # Extract gateway configuration
        gateway_config = extract_gateway_config(task_args=self._task.args, host_vars=task_vars, required=True)

        try:
            if hasattr(self._connection, "get_client"):
                self._display.vvvv(f"Dispatching to connection plugin get_client() (type={type(self._connection).__name__})")
                client, facts_to_set = self._connection.get_client(task_vars, gateway_config)
                self._display.vvvv(f"Got client from connection plugin: {type(client).__name__}")
                return client, facts_to_set
            else:
                self._display.vv(
                    f"Connection '{self._connection.transport}' has no get_client(); using ephemeral manager. "
                    "Set 'connection: ansible.platform.http' for persistent mode."
                )
                from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import spawn_ephemeral_client

                client, facts_to_set = spawn_ephemeral_client(task_vars, gateway_config)
                return client, facts_to_set
        except Exception as e:
            import traceback

            tb = traceback.format_exc()
            self._display.error(f"Failed in _get_or_spawn_manager dispatcher: {type(e).__name__}: {e}")
            self._display.error(f"Traceback: {tb}")

            try:
                with open("/tmp/ansible_platform_error.log", "w") as f:
                    f.write(f"Error: {type(e).__name__}: {e}\n\n")
                    f.write(f"Full Traceback:\n{tb}\n")
            except OSError:
                pass

            raise

    # ------------------------------------------------------------------ #
    #  Documentation and validation helpers                                #
    # ------------------------------------------------------------------ #

    def _get_documentation(self) -> str:
        """Auto-discover DOCUMENTATION from the sibling modules/ package.

        Uses file-based loading relative to this action plugin's location
        so the correct module file is always found, regardless of how
        Python's import system resolves the collection namespace.
        """
        if not self.MODULE_NAME:
            return ""

        # Primary: file-based discovery relative to this action plugin
        module_file = Path(__file__).parent.parent / "modules" / f"{self.MODULE_NAME}.py"
        if module_file.exists():
            try:
                import importlib.util

                spec = importlib.util.spec_from_file_location(f"module_{self.MODULE_NAME}", module_file)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    doc = getattr(mod, "DOCUMENTATION", None)
                    if doc:
                        return doc
            except Exception:
                pass

        # Fallback: standard import
        parent_pkg = type(self).__module__.rsplit(".", 2)[0]  # ...plugins
        for candidate in (
            f"{parent_pkg}.modules.{self.MODULE_NAME}",
            f"ansible_collections.ansible.platform.plugins.modules.{self.MODULE_NAME}",
        ):
            try:
                mod = importlib.import_module(candidate)
                doc = getattr(mod, "DOCUMENTATION", None)
                if doc:
                    return doc
            except (ImportError, ModuleNotFoundError):
                continue
        return ""

    def _build_argspec_from_docs(self, documentation: str) -> dict:
        """Build argument spec from DOCUMENTATION string.

        Parses the YAML documentation and merges documentation fragments
        (e.g., ansible.platform.auth) before converting to ArgumentSpec format.
        """
        try:
            doc_data = yaml.safe_load(documentation)
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse DOCUMENTATION: {e}") from e

        # Merge fragments first, then module options so module's own options take precedence
        options = {}
        extends_fragments = doc_data.get("extends_documentation_fragment", [])
        if not isinstance(extends_fragments, list):
            extends_fragments = [extends_fragments]
        for fragment_name in extends_fragments:
            fragment_options = self._load_documentation_fragment(fragment_name)
            if fragment_options:
                options.update(fragment_options)
        options.update(doc_data.get("options", {}))

        return {
            "argument_spec": options,
            "mutually_exclusive": doc_data.get("mutually_exclusive", []),
            "required_together": doc_data.get("required_together", []),
            "required_one_of": doc_data.get("required_one_of", []),
            "required_if": doc_data.get("required_if", []),
        }

    def _load_documentation_fragment(self, fragment_name: str) -> dict:
        """Load documentation fragment options."""
        try:
            if "." in fragment_name:
                parts = fragment_name.split(".")
                if len(parts) >= 3:
                    fragment = parts[-1]
                else:
                    fragment = fragment_name
            else:
                fragment = fragment_name

            fragment_path = Path(__file__).parent.parent / "doc_fragments" / f"{fragment}.py"

            if fragment_path.exists():
                import importlib.util

                spec = importlib.util.spec_from_file_location(f"doc_fragment_{fragment}", fragment_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    if hasattr(module, "ModuleDocFragment"):
                        fragment_class = module.ModuleDocFragment
                        fragment_doc = getattr(fragment_class, "DOCUMENTATION", "")

                        if fragment_doc:
                            fragment_data = yaml.safe_load(fragment_doc)
                            return fragment_data.get("options", {})

            self._display.vvvv(f"Documentation fragment '{fragment_name}' not found, skipping")
            return {}

        except Exception as e:
            self._display.warning(f"Failed to load documentation fragment '{fragment_name}': {e}")
            return {}

    def _validate_data(self, data: dict, argspec: dict, direction: str) -> dict:
        """Validate data against argument spec."""
        validator = ArgumentSpecValidator(
            argument_spec=argspec.get("argument_spec", {}),
            mutually_exclusive=argspec.get("mutually_exclusive"),
            required_together=argspec.get("required_together"),
            required_one_of=argspec.get("required_one_of"),
            required_if=argspec.get("required_if"),
            required_by=argspec.get("required_by"),
        )

        result = validator.validate(data)

        if result.error_messages:
            error_msg = f"{direction.title()} validation failed: " + ", ".join(result.error_messages)
            raise AnsibleError(error_msg)

        return result.validated_parameters

    def _validate_output(self, results: list, argspec: dict) -> list:
        """Validate return data against the config suboptions schema.

        Ensures the contract with the user: what we return in ``config``
        matches the documented suboptions (field names, types). Items with
        extra keys not in the schema are filtered out.
        """
        config_spec = argspec.get("argument_spec", {}).get("config", {})
        suboptions = config_spec.get("suboptions", {})

        if not suboptions:
            return results

        valid_keys = set(suboptions.keys())
        validated = []

        for item in results:
            if not isinstance(item, dict):
                validated.append(item)
                continue

            cleaned = {}
            for key, value in item.items():
                if key not in valid_keys:
                    continue
                elif value is None:
                    continue
                else:
                    cleaned[key] = value

            validated.append(cleaned)

        return validated

    def _detect_operation(self, args: dict) -> str:
        """Map resource module state to API operation."""
        state = args.get("state", "merged")

        if state not in self.VALID_STATES:
            raise AnsibleError(f"Unknown state: {state}. Valid states: {sorted(self.VALID_STATES)}")

        state_to_operation = {
            "merged": "update",
            "replaced": "replace",
            "overridden": "override",
            "deleted": "delete",
            "gathered": "find",
        }

        return state_to_operation[state]

    # ------------------------------------------------------------------ #
    #  Cleanup                                                             #
    # ------------------------------------------------------------------ #

    def cleanup(self, force: bool = False) -> None:
        """Called by Ansible after each task completes.

        Persistent managers are shut down by the platform_manager_cleanup
        callback plugin. This method only handles ephemeral managers.
        """
        super().cleanup(force)

        if hasattr(self, "_client") and getattr(self._client, "_ephemeral", False):
            self._display.vv("Shutting down ephemeral manager (direct mode)")
            try:
                from ansible_collections.ansible.platform.plugins.plugin_utils.manager.process_manager import ProcessManager

                socket_path = getattr(self._client, "socket_path", None)
                if socket_path:
                    self._shutdown_manager_process(socket_path, ProcessManager)
            except Exception as e:
                self._display.warning(f"Failed to shutdown ephemeral manager: {e}")

    def _shutdown_manager_process(self, socket_path: str, ProcessManager: Any) -> None:
        """Shutdown a specific manager process."""
        process_info = BaseResourceActionPlugin._spawned_processes.get(socket_path)

        if not process_info:
            meta_path = str(socket_path) + ".meta"
            try:
                with open(meta_path, "r") as _mf:
                    meta = json.load(_mf)
                self._display.vvvv(f"Loaded manager meta from {meta_path}: pid={meta.get('pid')}")
                import os as _os

                pid = meta.get("pid")
                if pid:

                    class _PidProxy:
                        """Thin proxy so process.poll/terminate/kill/wait work on a bare PID."""

                        def __init__(self, p):
                            self._pid = p

                        def poll(self):
                            try:
                                _os.kill(self._pid, 0)
                                return None
                            except ProcessLookupError:
                                return 0
                            except PermissionError:
                                return None

                        def terminate(self):
                            try:
                                _os.kill(self._pid, 15)
                            except ProcessLookupError:
                                pass

                        def kill(self):
                            try:
                                _os.kill(self._pid, 9)
                            except ProcessLookupError:
                                pass

                        def wait(self, timeout=None):
                            import time as _t

                            deadline = _t.monotonic() + (timeout or 30)
                            while _t.monotonic() < deadline:
                                if self.poll() is not None:
                                    return 0
                                _t.sleep(0.1)
                            raise subprocess.TimeoutExpired([], timeout)

                    process_info = {"process": _PidProxy(pid), "authkey_b64": meta.get("authkey_b64")}
                else:
                    self._display.vvvv(f"Meta file {meta_path} has no pid, cannot shut down manager")
                    return
            except FileNotFoundError:
                self._display.vvvv(f"Manager {socket_path} not in spawned processes and no meta file found — already gone")
                return
            except Exception as _e:
                self._display.vvvv(f"Could not read manager meta file {meta_path}: {_e}")
                return

        process = process_info["process"]
        authkey_b64 = process_info.get("authkey_b64")

        if process.poll() is None:
            self._display.vvvv(f"Manager process still running at {socket_path}, shutting down...")

            try:
                if authkey_b64 and Path(socket_path).exists():
                    try:
                        authkey = base64.b64decode(authkey_b64)
                        from .plugin_utils.manager.rpc_client import ManagerRPCClient

                        socket_path_str = str(socket_path)
                        client = ManagerRPCClient(process_info.get("gateway_url", ""), socket_path_str, authkey)
                        try:
                            shutdown_result = client.shutdown_manager()
                            self._display.vvvv(f"Sent shutdown signal to manager at {socket_path}: {shutdown_result}")
                        except Exception as e:
                            self._display.vvvv(f"Shutdown RPC failed (manager may have already shut down): {e}")
                        finally:
                            client.close()
                    except Exception as e:
                        self._display.vvvv(f"Could not connect for graceful shutdown: {e}")

                try:
                    process.wait(timeout=5)
                    self._display.vvvv(f"Manager process at {socket_path} shut down gracefully")
                except subprocess.TimeoutExpired:
                    self._display.warning(f"Manager process at {socket_path} did not shut down gracefully, forcing termination")
                    process.terminate()
                    time.sleep(1)
                    if process.poll() is None:
                        process.kill()
                        process.wait()
            except Exception as e:
                self._display.warning(f"Error shutting down manager at {socket_path}: {e}")
                try:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
                except Exception:
                    pass

        try:
            ProcessManager.cleanup_old_socket(socket_path)
            self._display.vvvv(f"Cleaned up socket file: {socket_path}")
        except Exception as e:
            self._display.vvvv(f"Could not clean up socket file {socket_path}: {e}")
        try:
            meta_path = str(socket_path) + ".meta"
            if Path(meta_path).exists():
                Path(meta_path).unlink()
                self._display.vvvv(f"Cleaned up manager meta file: {meta_path}")
        except Exception as e:
            self._display.vvvv(f"Could not clean up meta file: {e}")

        BaseResourceActionPlugin._spawned_processes.pop(socket_path, None)
