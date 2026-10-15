# Contributing to ansible.platform

This collection is distributed through Red Hat Automation Hub and maintained by Red Hat engineering. Contributions come from PDT members and internal stakeholders.

---

## Before opening a PR

- Reference a Jira issue in the PR title: `[AAP-XXXXX] Short description`
- Fill the PR template completely
- Apply the `safe to test` label to trigger integration CI
- Minimum **2 approvals** required before merge

For new modules, architecture changes, or anything with cross-PDT impact — open a discussion with the Component Lead first. Full workflow details are in [`docs/07-adding-resources.md`](docs/07-adding-resources.md).

---

## CasC notification

If your change adds a module, alters auth or return values, or deprecates anything — tag the CasC collections team in the PR. The CI check will post a reminder automatically when trigger areas are touched.

---

See [`docs/`](docs/) for architecture, coding standards, testing strategy, and the full module workflow.

### AI agents and automated contributors

Before changing `plugins/action/` or adding controller/awx migrations, read
[`docs/09-agent-collaboration.md`](docs/09-agent-collaboration.md) §10 (SDK execution
invariants) and [`docs/07-adding-resources.md`](docs/07-adding-resources.md) §4c (launch/job
wait). Run `make check_action_plugin_invariants` before opening a PR. Resource logic belongs
in transform mixins and `PlatformService.execute()` so playbooks, MCP, and other SDK
consumers share one path.

**Checklist for controller migrations and launch modules:**

- [ ] No `manager.session` or `requests` in action plugins (`make check_action_plugin_invariants`)
- [ ] No wait/poll loops (`time.sleep`, `_wait_for_*`) in action plugins — use PlatformService
- [ ] Every option in module `DOCUMENTATION` (including `wait`, `interval`, `timeout`) works via
      `PlatformService.execute()`, not only through the action plugin
