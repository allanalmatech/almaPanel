# Development progress
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

## 2026-11-14 · 0.1.0-alpha.1
Phase: **Milestone 1 implemented in part; selected Milestone 2/4/5 core paths coded; production gates blocked.** No milestone requiring actual Linux acceptance is marked complete.

### Implemented functionality and changed files
- `backend/`: SQLite/session/auth/RBAC primitives and WSGI API; schema under `database/migrations/`.
- `agent/`: restricted root broker, generated Nginx/PHP configs, tenant-UID file helper; local tests cover safe file access and configuration rollback logic.
- `worker/`: queued operation processing, result/audit persistence, suspended-login synchronization and interrupted-job handling.
- `frontend/`: original grouped tools, administrator/reseller/user navigation, account/package forms, file manager, jobs, preferences and real-state statistics.
- `installer/`, `services/`: Ubuntu install/preflight, TLS bootstrap, systemd units, health/diagnostics, control-plane snapshots/restore and non-destructive disablement. Updates explicitly unavailable.
- `tests/`, `.github/`, `scripts/`: local tests, separate VM/browser acceptance runners, CI, release gate and deterministic packaging.
- Root and `docs/`: architecture, scope matrix, backlog, API/OpenAPI, EC2 instructions and readiness evidence.

### Commands and results
- `python3 -m unittest discover -s tests -v`: 34 passed.
- `make check`: unit tests, Python compile, JavaScript syntax and installer shell syntax passed.
- `python3 -m coverage run --source=backend,agent,worker -m unittest discover -s tests`: passed; approximately 69% statement coverage at initial measurement. Agent coverage is low because actual root service execution was not performed.
- `python3 -m bandit -r backend agent worker -ll -ii`: no medium/high findings after documenting the intentionally group-accessible broker socket. Low subprocess findings remain for reviewed fixed command arrays.
- `python3 tests/e2e/browser.py`: **blocked/failed at Chromium launch**, socket creation not permitted in this workspace; no UI success claimed.
- Live installer and `tests/installation/ubuntu_vm.sh`: **not run**; workspace is not a clean Ubuntu root/systemd VM.
- Packaging and repository verification: see `docs/VALIDATION.md` for final commands/results.

### Known limitations and blockers
The implementation is a real but incomplete evaluation core. No mail/hosted-database/DNS/ACME/Git/app/WordPress/SSH/cron modules, full backups, cgroup/disk quotas, MFA or tested upgrades. Browser validation and live VM acceptance are outstanding. No access to an EC2 instance, test domain, public installer host or GitHub remote is configured. Owner license/signing approvals remain unresolved. Unsupported modules are not simulated and do not appear as functional tools.

### Next actions
1. Run local browser acceptance on a host that permits Chromium sockets.
2. Execute the disposable-VM runner on Ubuntu 24.04 amd64; fix actual install issues and retain complete logs; repeat arm64.
3. Verify two hostile tenants, socket isolation, service config failures and reboot behavior.
4. Complete database/DNS/ACME/Git and customer-backup modules with real-service tests, then the remaining milestones.
5. Complete all release acceptance criteria and independent security review before signing/publishing.

## 2026-11-14 — Backlog reconciliation and File Manager work
The complete 18-area checklist is recorded in TODO.md. Amazon Linux installation
and initial setup passed according to the supplied EC2 logs and user testing.
Alpha.2 source is published with file copying and signed application-update code.
Signing-key enrollment, release assets and live rollback acceptance remain pending.

Current implementation focus: hidden-file visibility and tenant-scoped permission
editing. Broader modules remain open. Next work is safe archive handling, followed
by customer database provisioning and per-domain site configuration.

Implemented in this increment: hidden-files toggle and account-owned permission
editing using no-follow descriptors. Only 600/640/644/700/750/755 modes are allowed.
Symlinks, hardlinked regular files and non-owned entries are rejected.
Validation: 37 local tests passed plus Python, JavaScript and shell syntax checks.
Browser and live EC2 permission/ACL behavior still require acceptance.
