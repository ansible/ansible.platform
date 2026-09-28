# Manual validation playbooks — `role_team_assignment` (PR #205)

## Confidence (honest)

| Layer | Confidence | Why |
|---|---|---|
| Unit tests (mocked `search_api`) | **High (~90%)** | Org resolve, Controller query param, EDA filter, ambiguous fail-closed, Hub reject org |
| Gateway CI / integration | **Medium-high** | Existing `role_team_assignments_test` exercises gateway; soft-skips Controller/EDA/Hub when absent |
| Live Controller org-disambiguation | **Medium until you run this** | New code path; not in gateway-only CI |
| Live EDA / Hub | **Medium until you run this** | Same — logic is there; environment-dependent |
| Role definition / permission strings | **Lower** | Exact `content_type` / permission names vary by AAP version; playbook may need tweaks |

**Bottom line:** safe to review/merge from a code-correctness view for the *lookup algorithm*, but **do not call it production-proven for Controller/EDA/Hub** until someone runs this suite (or equivalent) on a full AAP.

## What this suite proves

1. **Gateway** — name assign + idempotency  
2. **`object_ids` removed** — task with `object_ids:` must fail  
3. **Controller customer gap** — same inventory name in Prod + Preprod; `organization: Preprod` hits the right id; without org → fail closed  
4. **EDA** — `eda_projects` + `organization`  
5. **Hub** — name assign; `organization=` must fail  

## Run

```bash
cd tests/manual/role_team_assignment_validation
cp vars.example.yml vars.yml   # edit hostname/password
# Install collection under test (checkout with the PR changes)
ansible-playbook playbook.yml -e @vars.yml -vv
```

Tagged runs:

```bash
# Gateway only (works on CI-like gateway)
ansible-playbook playbook.yml -e @vars.yml --tags gateway

# Customer scenario
ansible-playbook playbook.yml -e @vars.yml --tags gateway,controller

# Everything reachable
ansible-playbook playbook.yml -e @vars.yml --tags gateway,controller,eda,hub
```

Keep resources for inspection:

```bash
ansible-playbook playbook.yml -e @vars.yml -e cleanup=false
```

## Share with team

Point reviewers at this directory + the confidence table above. Ask Controller/EDA/Hub owners to run the matching tags on a shared AAP and paste the assert failures (if any) back on the PR.
