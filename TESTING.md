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
Set CHROMIUM_PATH if Chromium is elsewhere (default `/usr/bin/chromium`), for example `CHROMIUM_PATH=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`. Set `ALMA_QA_DIR` to a folder to keep navigation screenshots. The runner starts a temporary HTTPS WSGI/SQLite app and exercises setup, login, package persistence, account retry, File Manager, backups, mail, DNS drafts, preferences, themes and logout.

Since alpha.11 it also checks compact navigation:

- Sidebar links: five for administrators and resellers, four for hosting users.
- Dashboard groups for each role. Server Administration is hidden from resellers and users, and Hosting Management from users.
- Opening secondary tools from dashboard groups.
- Search by name, description and category, result counts, the empty state, Clear search and Escape.
- Breadcrumbs, page titles, active and `aria-current` indicators.
- Dashboard layout at 800, 1024, 1280, 1440 and 1920 pixels: small groups share rows, large groups span them, rows have no gaps and pages have no horizontal overflow.
- Desktop collapse to an icon rail, persisted across a reload.
- The mobile drawer at 390 pixels: focus moves into it, Tab stays inside, Escape returns focus to the menu button, and the backdrop, close button and link navigation close it.

No root adapters are simulated. The suite passed on 2026-11-23 with Playwright Chromium 1243. Earlier workspaces could not start Chromium because local socket creation was forbidden. `--no-sandbox` is used only for this isolated test process; no such browser dependency is installed on hosting servers.

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

## Alpha.5 mail acceptance

On a clean disposable Amazon Linux 2023 VM:

```bash
sudo env ALMA_DISPOSABLE_VM=YES ALMA_TEST_MAIL=YES bash tests/installation/amazon_vm.sh
```

The runner configures loopback Postfix and Dovecot with a short-lived test
certificate and checks SMTP authentication and relay denial, forwarding through
LMTP, IMAP quota enforcement, and archived mailbox access. Locally, generated
configurations and Postfix maps passed parser checks. The Chromium test covers
form submission using a fixture. Real mail delivery, public DNS and renewal
need service acceptance on the VM.

## Alpha.6 backup acceptance

```bash
python3 tests/integration/offsite_backup.py -v
sudo env ALMA_DISPOSABLE_VM=YES ALMA_TEST_OFFSITE=YES bash tests/installation/amazon_vm.sh
```

The integration test uses real restic and a temporary local encrypted
repository. It covers snapshot creation, selective retrieval, imported ZIP
validation, site recovery, scoped retention and an invalid password. If
restic is installed outside PATH, set `ALMA_TEST_RESTIC` to its executable.
Run the second command on a clean Amazon Linux VM with restic available
from your configured repository or installed at `/usr/local/bin/restic`.
It adds a round trip with the broker's Linux account identities and the
installed admin CLI. Test your remote destination and timer separately.

## Alpha.7 database backup acceptance

```bash
sudo env ALMA_DISPOSABLE_VM=YES ALMA_TEST_SQL=YES ALMA_TEST_OFFSITE=YES bash tests/installation/amazon_vm.sh
```

The VM runner enrolls both database engines through the installed CLI,
checks the encrypted snapshot, and verifies restored data in a separate
managed database. It checks the original data and rejects a repeated import
into the populated destination. The live Amazon Linux run is pending.

The local round trip used MariaDB 11.8, PostgreSQL 17 and real restic 0.18
on private test ports. It checked wrong-password rejection, table rows
and binary data, PostgreSQL view recovery, refusal of unsupported MariaDB
objects, and full repository data verification. The disposable VM is
required to exercise systemd and the target OS identity and socket paths.

## Alpha.8 managed DNS recovery acceptance

```bash
sudo env ALMA_DISPOSABLE_VM=YES ALMA_TEST_DNS=YES ALMA_TEST_OFFSITE=YES bash tests/installation/amazon_vm.sh
```

The VM runner changes a test zone, restores its prior export through the
administrator API and queries the active BIND service. The VM run is pending.
Locally, the restic test checks the recovered record set and can pass it to
`named-checkzone` when `ALMA_TEST_NAMED_CHECKZONE` is set. The browser test
checks draft import and rejects a backup for a different domain.

## Alpha.10 File Manager acceptance

`make check` exercises tenant boundaries, upload replay and collision
handling, partial uploads, revision checks, file permissions, paged metadata
and ZIP/Trash operations with actual files. The Chromium suite uses the live
WSGI application and an isolated filesystem fixture for the agent operation
boundary. It exercises the folder tree, keyboard-accessible controls, file
transfers, source editing, permissions, ZIP, image conversion, audio preview,
Trash restore and a mobile viewport.

An unprivileged Linux CLI run uploaded 256 MiB in 512 chunks and verified
the published file's SHA-256 checksum. The installed Amazon Linux and Ubuntu
VM tests still need to verify the service UID, ACLs and exposure through Nginx.
`tests/e2e/live_vm.py` contains those File Manager checks for a disposable VM.
