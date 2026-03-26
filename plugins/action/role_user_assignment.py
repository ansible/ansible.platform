#!/usr/bin/env python
# -*- coding: utf-8 -*-
# (c) 2025, Ansible Platform Collection Contributors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible.errors import AnsibleError

from ansible_collections.ansible.platform.plugins.action.base_action import BaseResourceActionPlugin
from ansible_collections.ansible.platform.plugins.plugin_utils.ansible_models.role_user_assignment import AnsibleRoleUserAssignment


class ActionModule(BaseResourceActionPlugin):
    MODULE_NAME = 'role_user_assignment'
    MODEL_CLASS = AnsibleRoleUserAssignment
    LOOKUP_FIELD = 'id'

    def run(self, tmp=None, task_vars=None):
        """
        Custom run() for role_user_assignment.

        Supports three object-selection modes:
        - object_id (scalar): standard single-object path via _run_standard().
        - object_ids (list): iterate, resolving each entry → object_id, then
          idempotent create/delete per object.
        - Neither: system-wide assignment, single-object path.
        """
        if task_vars is None:
            task_vars = {}
        self._task_vars = task_vars
        result = super(BaseResourceActionPlugin, self).run(tmp, task_vars)
        del tmp

        try:
            # ---- validate input ------------------------------------------------
            doc = self._get_documentation()
            argspec = self._build_argspec_from_docs(doc) if doc else None
            if not argspec:
                raise AnsibleError(
                    "Could not load DOCUMENTATION for %s module" % self.MODULE_NAME
                )
            validated_input = self._validate_data(
                self._task.args.copy(), argspec, 'input'
            )
            validated_params = validated_input.validated_parameters

            # ---- manager connection --------------------------------------------
            manager, facts_to_set = self._get_or_spawn_manager(task_vars)
            if facts_to_set:
                result['ansible_facts'] = facts_to_set
                result['_ansible_facts_cacheable'] = True

            state = validated_params.get('state', 'present')
            object_ids_raw = validated_params.get('object_ids') or []

            if not object_ids_raw:
                # ---- single-object path ---------------------------------------
                return self._run_standard(
                    result, manager, argspec, validated_params, state
                )

            # ---- multi-object path: iterate over object_ids ------------------
            # Base data (role + user, shared across all assignments)
            _skip = self._AUTH_PARAMS | {'object_ids', 'state', 'object_id'}
            base_data = {
                k: v for k, v in validated_params.items()
                if v is not None and k not in _skip
            }

            all_changed = False
            assignments = []

            for raw_oid in object_ids_raw:
                # Build per-object data: set object_id to each list entry.
                # from_ansible_data's existing FK resolver handles str→int
                # resolution (via role_definition-type-aware endpoint probing).
                per_obj = dict(base_data)
                per_obj['object_id'] = raw_oid

                if state == 'present':
                    # Idempotency: find existing assignment
                    try:
                        find_result = manager.execute(
                            operation='find',
                            module_name=self.MODULE_NAME,
                            ansible_data=per_obj,
                        )
                        if find_result and find_result.get('id'):
                            assignments.append(find_result)
                            continue   # already exists — no change
                    except Exception:
                        pass

                    # Create
                    mgr_result = manager.execute(
                        operation='create',
                        module_name=self.MODULE_NAME,
                        ansible_data=per_obj,
                    )
                    all_changed = True
                    assignments.append(mgr_result)

                elif state == 'absent':
                    try:
                        find_result = manager.execute(
                            operation='find',
                            module_name=self.MODULE_NAME,
                            ansible_data=per_obj,
                        )
                        if find_result and find_result.get('id'):
                            manager.execute(
                                operation='delete',
                                module_name=self.MODULE_NAME,
                                ansible_data={'id': find_result['id']},
                            )
                            all_changed = True
                    except Exception:
                        pass

                elif state == 'exists':
                    # Check existence without modifying; collect found assignments
                    try:
                        find_result = manager.execute(
                            operation='find',
                            module_name=self.MODULE_NAME,
                            ansible_data=per_obj,
                        )
                        if find_result and find_result.get('id'):
                            assignments.append(find_result)
                    except Exception:
                        pass

            # ---- build clean result -------------------------------------------
            _strip = (
                self._ANSIBLE_DIRECTIVES
                | (self._READ_ONLY_FIELDS - {'id'})
                | {'_timing', 'changed', 'object_ids', 'assignments'}
            )

            # For state=exists: fail (without setting MODULE_NAME key) if nothing
            # was found — mirrors the single-object path's "not found" behaviour
            # so that `failed_when: false` + `result.role_user_assignment is not defined`
            # idiom works identically for both scalar and list object selectors.
            if state == 'exists' and not assignments:
                raise ValueError(
                    "No %s found matching the given criteria" % self.MODULE_NAME
                )

            primary = assignments[0] if assignments else {}
            clean = {k: v for k, v in primary.items() if k not in _strip}

            result.update({
                'changed': all_changed,
                'failed': False,
                self.MODULE_NAME: clean,
            })
            if len(assignments) > 1:
                result['assignments'] = [
                    {k: v for k, v in a.items() if k not in _strip}
                    for a in assignments
                ]

        except Exception as exc:
            import traceback as _tb
            self._display.vvv(
                "Error in %s action plugin: %s" % (self.MODULE_NAME, exc)
            )
            result['failed'] = True
            result['msg'] = str(exc)
            if self._display.verbosity >= 3:
                result['exception'] = _tb.format_exc()

        return result

    # ------------------------------------------------------------------
    def _run_standard(self, result, manager, argspec, validated_params, state):
        """Single-object / system-wide path: standard present/absent logic."""
        from dataclasses import asdict

        resource_data = {
            k: v for k, v in validated_params.items()
            if v is not None and k not in self._AUTH_PARAMS
            and k != 'object_ids'
        }
        try:
            resource = self.MODEL_CLASS(**resource_data)
        except TypeError as exc:
            result['failed'] = True
            result['msg'] = str(exc)
            return result

        operation = self._detect_operation(validated_params)

        _strip = (
            self._ANSIBLE_DIRECTIVES
            | (self._READ_ONLY_FIELDS - {'id'})
            | {'_timing', 'changed', 'object_ids', 'assignments'}
        )

        if state == 'present' and operation == 'create':
            try:
                find_result = manager.execute(
                    operation='find',
                    module_name=self.MODULE_NAME,
                    ansible_data=resource_data,
                )
                if find_result and find_result.get('id'):
                    if not self._should_update(resource_data, find_result):
                        clean = {k: v for k, v in find_result.items() if k not in _strip}
                        result.update({
                            'changed': False, 'failed': False,
                            self.MODULE_NAME: clean,
                        })
                        return result
                    operation = 'update'
                    resource.id = find_result['id']
            except Exception:
                pass

        if operation == 'delete' and not getattr(resource, 'id', None):
            try:
                find_result = manager.execute(
                    operation='find',
                    module_name=self.MODULE_NAME,
                    ansible_data=resource_data,
                )
                if find_result and find_result.get('id'):
                    resource.id = find_result['id']
                else:
                    result.update({
                        'changed': False, 'failed': False,
                        self.MODULE_NAME: {'state': 'absent'},
                    })
                    return result
            except Exception:
                result.update({
                    'changed': False, 'failed': False,
                    self.MODULE_NAME: {'state': 'absent'},
                })
                return result

        ansible_data = asdict(resource)
        manager_result = manager.execute(
            operation=operation,
            module_name=self.MODULE_NAME,
            ansible_data=ansible_data,
        )

        clean = {k: v for k, v in manager_result.items() if k not in _strip}
        result.update({
            'changed': manager_result.get('changed', False),
            'failed': False,
            self.MODULE_NAME: clean,
        })
        if operation == 'delete':
            result[self.MODULE_NAME]['state'] = 'absent'

        return result
