# Ansible Facts Population Flow - Exact Locations

This document shows the **exact code locations** where Ansible facts are populated from `set_fact` to `hostvars`.

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Action Plugin Calls set_fact                                │
│    Location: base_action.py:360-369                            │
│    Method: _execute_module('ansible.builtin.set_fact', ...)    │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. set_fact Action Plugin Returns Result                        │
│    Location: ansible/plugins/action/set_fact.py:51-54           │
│    Returns: {'ansible_facts': {...}, '_ansible_facts_cacheable': True} │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. TaskExecutor Processes Result                                │
│    Location: executor/task_executor.py:775-789                 │
│    Extracts ansible_facts and adds to variables dict           │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Strategy Plugin Stores Facts                                │
│    Location: plugins/strategy/__init__.py:709-720              │
│    Calls: VariableManager.set_host_facts()                     │
│    AND: VariableManager.set_nonpersistent_facts()             │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. VariableManager Stores in Fact Cache                        │
│    Location: vars/manager.py:564-587                           │
│    Method: set_host_facts(host, facts)                         │
│    Storage: _fact_cache.set(host, host_cache)                  │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. Facts Retrieved for Subsequent Tasks                        │
│    Location: vars/manager.py:289-310                           │
│    Method: get_vars() -> _fact_cache.get(host.name)            │
│    Result: Available in task_vars['hostvars'][hostname]       │
└─────────────────────────────────────────────────────────────────┘
```

## Exact Code Locations

### 1. Where We Call set_fact

**File**: `plugins/action/base_action.py`  
**Lines**: 359-369

```python
# Set facts so subsequent tasks can reuse this manager
try:
    self._execute_module(
        module_name='ansible.builtin.set_fact',
        module_args={
            'platform_manager_socket': socket_path,
            'platform_manager_authkey': authkey_b64,
            'gateway_url': gateway_url,
            'cacheable': True  # Persist across plays
        },
        task_vars=task_vars
    )
except Exception as e:
    logger.warning(f"Failed to set facts: {e}")
```

### 2. set_fact Action Plugin Returns Result

**File**: `ansible/lib/ansible/plugins/action/set_fact.py`  
**Lines**: 51-54

```python
if facts:
    # just as _facts actions, we don't set changed=true as we are not modifying the actual host
    result['ansible_facts'] = facts
    result['_ansible_facts_cacheable'] = cacheable
```

**Returns**:
```python
{
    'ansible_facts': {
        'platform_manager_socket': '/tmp/ansible_platform/manager_localhost.sock',
        'platform_manager_authkey': 'dGhpc2lzYXNlY3JldGtleQ==',
        'gateway_url': 'https://platform.example.com'
    },
    '_ansible_facts_cacheable': True
}
```

### 3. TaskExecutor Processes ansible_facts

**File**: `ansible/lib/ansible/executor/task_executor.py`  
**Lines**: 775-789

```python
if 'ansible_facts' in result and self._task.action not in C._ACTION_DEBUG:
    if self._task.action in C._ACTION_WITH_CLEAN_FACTS:
        variables.update(result['ansible_facts'])
    else:
        # TODO: cleaning of facts should eventually become part of taskresults instead of vars
        af = result['ansible_facts']
        variables['ansible_facts'] = combine_vars(
            variables.get('ansible_facts', {}), 
            namespace_facts(af)
        )
        if _INJECT_FACTS:
            if _INJECT_FACTS_ORIGIN == 'default':
                cleaned_toplevel = {k: _deprecate_top_level_fact(v) for k, v in clean_facts(af).items()}
            else:
                cleaned_toplevel = clean_facts(af)
            variables.update(cleaned_toplevel)
```

### 4. Strategy Plugin Stores Facts (THE KEY LOCATION)

**File**: `ansible/lib/ansible/plugins/strategy/__init__.py`  
**Lines**: 709-720

**This is where facts are actually stored in VariableManager!**

```python
cacheable = result_item.pop('_ansible_facts_cacheable', False)
for target_host in host_list:
    # so set_fact is a misnomer but 'cacheable = true' was meant to create an 'actual fact'
    # to avoid issues with precedence and confusion with set_fact normal operation,
    # we set BOTH fact and nonpersistent_facts (aka hostvar)
    # when fact is retrieved from cache in subsequent operations it will have the lower precedence,
    # but for playbook setting it the 'higher' precedence is kept
    is_set_fact = original_task.action in C._ACTION_SET_FACT
    if not is_set_fact or cacheable:
        self._variable_manager.set_host_facts(target_host, result_item['ansible_facts'].copy())
    if is_set_fact:
        self._variable_manager.set_nonpersistent_facts(target_host, result_item['ansible_facts'].copy())
```

**Key Points**:
- If `cacheable=True` OR action is NOT `set_fact`: calls `set_host_facts()` → stores in fact cache
- If action IS `set_fact`: calls `set_nonpersistent_facts()` → stores in non-persistent cache
- With `cacheable=True` on `set_fact`: **BOTH** are called (fact cache + non-persistent)

### 5. VariableManager.set_host_facts() Stores in Cache

**File**: `ansible/lib/ansible/vars/manager.py`  
**Lines**: 564-587

```python
def set_host_facts(self, host, facts):
    """
    Sets or updates the given facts for a host in the fact cache.
    """
    if not isinstance(facts, Mapping):
        raise AnsibleAssertionError("the type of 'facts' to set for host_facts should be a Mapping but is a %s" % type(facts))

    warn_if_reserved(facts)

    try:
        host_cache = self._fact_cache.get(host)
    except KeyError:
        # We get to set this as new
        host_cache = facts
    else:
        if not isinstance(host_cache, MutableMapping):
            raise TypeError('The object retrieved for {0} must be a MutableMapping but was'
                            ' a {1}'.format(host, type(host_cache)))
        # Update the existing facts
        host_cache |= facts

    # Save the facts back to the backing store
    self._fact_cache.set(host, host_cache)
```

**What happens**:
1. Gets existing facts from cache (or creates new dict)
2. Merges new facts with existing (`host_cache |= facts`)
3. Saves back to fact cache (`_fact_cache.set(host, host_cache)`)

### 6. Facts Retrieved for Subsequent Tasks

**File**: `ansible/lib/ansible/vars/manager.py`  
**Lines**: 289-310

```python
# finally, the facts caches for this host, if they exist
try:
    try:
        facts = self._fact_cache.get(host.name)
    except KeyError:
        facts = {}

    all_vars |= namespace_facts(facts)

    inject, origin = C.config.get_config_value_and_origin('INJECT_FACTS_AS_VARS')
    # push facts to main namespace
    if inject:
        if origin == 'default':
            clean_top = {k: _deprecate_top_level_fact(v) for k, v in clean_facts(facts).items()}
        else:
            clean_top = clean_facts(facts)
        all_vars = _combine_and_track(all_vars, clean_top, "facts")
    else:
        # always 'promote' ansible_local, even if empty
        all_vars = _combine_and_track(all_vars, {'ansible_local': facts.get('ansible_local', {})}, "facts")
except KeyError:
    pass
```

**Result**: Facts are now available in `task_vars['hostvars'][hostname]` for subsequent tasks.

## Summary

**Where facts are populated**:

1. **Action plugin calls set_fact**: `base_action.py:360`
2. **set_fact returns result**: `plugins/action/set_fact.py:53`
3. **TaskExecutor processes**: `executor/task_executor.py:775`
4. **Strategy plugin stores** (KEY STEP): `plugins/strategy/__init__.py:718`
5. **VariableManager saves to cache**: `vars/manager.py:587`
6. **Facts retrieved for next task**: `vars/manager.py:292`

**The critical step is #4** - the strategy plugin calls `VariableManager.set_host_facts()`, which stores facts in the fact cache. These facts are then available in `hostvars` for all subsequent tasks.

