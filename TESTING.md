# Test strategy and evidence
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

## Local automated checks
```bash
make check
python3 -m pip install bandit==1.8.6 coverage==7.10.7
python3 -m bandit -r backend agent worker -ll -ii
python3 -m coverage run --source=backend,agent,worker -m unittest discover -s tests
python3 -m coverage report
python3 scripts/secret_scan.py
```
34 unittest cases exercise actual WSGI handlers, SQLite and temporary filesystem operations. Tested paths include setup token replay, cookie flags, login throttling, sessions/CSRF/Origin, password invalidation, user/reseller scope, allocation exhaustion, domain input injection, job state transitions, file lifecycle, traversal, symlinks, hardlinks, FIFO rejection, size limits, non-overwriting rename and config rollback. Mocked RPC/config command calls verify control flow **only**; they do not establish Linux provisioning success.

Initial measured statement coverage was approximately 69% overall (agent ~33%, file helper ~89%, API ~81%). No inflated service acceptance coverage claim. Coverage artifacts are generated locally, not shipped as source.

Static review: one explicit Bandit B103 suppression for socket 0660 with a dedicated group and SO_PEERCRED UID check. Low subprocess-related findings are reviewed fixed-array operations without a shell. Medium/high scan passes; this is not penetration testing.

## Browser acceptance
Install Playwright and Chromium in a local development environment and run:
```bash
python3 tests/e2e/browser.py
```
Set CHROMIUM_PATH if Chromium is elsewhere. The runner starts a temporary HTTPS WSGI/SQLite app and exercises setup, login, package persistence, search, themes, mobile navigation and logout. No root adapters are simulated. In this workspace Chromium fails at startup because local socket creation is forbidden, so the browser suite is **not passed**. `--no-sandbox` is used only for this isolated test process; no such browser dependency is installed on hosting servers.

## Actual Linux installation acceptance
On a **disposable clean Ubuntu 24.04 VM only**, after reviewing scripts:
```bash
sudo env ALMA_DISPOSABLE_VM=YES bash tests/installation/ubuntu_vm.sh
```
This installs real services and executes HTTPS setup/login, package/account provisioning, domain, file upload, real PHP HTTP execution, a private-state read-denial check, suspension and unsuspension. It leaves random-password test accounts for inspection and is not a production cleanup script. A failed/missing service fails the test rather than skips. This runner has **not been executed** in this delivery.

Additional required manual/live suites: second-tenant cross-access, concurrent races, useradd/reload crash recovery, socket peer denial, memory/disk quotas once implemented, disk exhaustion, certificate renewals, DNS/mail delivery, database restore, full account restoration, kernel/service reboot persistence, schema upgrades and rollback. Public-DNS/mail tests need suitable infrastructure. See RELEASE_CHECKLIST.md.

## Packaging and CI
Run package twice and compare SHA256SUMS. CI checks syntax, tests, basic secret scanning and Bandit. GitHub workflow execution and dependency scanning are not claimed run. Release workflow is intentionally gated; no publishing step exists. Validate CloudFormation through AWS before any deployment. See docs/VALIDATION.md for final local evidence.


## Alpha.3 acceptance

Run the Amazon Linux installer and hosting checks on a disposable systemd EC2 VM:

```bash
sudo env ALMA_DISPOSABLE_VM=YES ALMA_TEST_SQL=YES bash tests/installation/amazon_vm.sh
```

Omit ALMA_TEST_SQL to run the core and website snapshot checks alone. The script
creates accounts and starts supported services. Use a clean VM. The local
test evidence and provider-specific checks that still require a VM are recorded
in PROGRESS.md.
