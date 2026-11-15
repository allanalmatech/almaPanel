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

## 2026-11-14 · 0.1.0-alpha.3

Implemented account-scoped MariaDB and PostgreSQL, per-domain Nginx roots,
aliases and redirects, tenant DNS proof, BIND forward zones, site certificate
upload, Certbot issuance and renewal, and WordPress initialization. Added
bounded ZIP create/extract, recursive copy and search, private Trash, uploads,
previews, website snapshot and restore, daily/weekly backup schedules and
tenant SQL transfers. Added public Git source staging, account PHP settings
and scripts on a schedule, TOTP/recovery codes, read-only tokens, profile
details, directory passwords, IP denial rules and recent website/process
metrics. Existing alpha.2 installations can upgrade from the Git checkout.

Verification completed in this workspace:

- 53 Python tests, Python compile, JavaScript and shell syntax checks.
- Real Chromium over local HTTPS for setup, sign-in, packages, search, profile,
  API token creation, mobile navigation, theme and logout. The standard
  Chromium launcher was blocked, so this run used Chromium headless shell.
- Real MariaDB 11.8 and PostgreSQL 17 over loopback. Create, read/write,
  ownership denial, size and delete worked for two database owners.
- Real BIND zone validation and Nginx generated-config validation.
- Real Nginx HTTPS requests verified directory passwords on static and PHP
  routes. The test used a temporary self-signed certificate and high ports.
- Real PHP 8.4 and the pinned WordPress bundle initialized MariaDB tables and
  the WordPress admin account. The test used loopback SQL transport.
- Real Git archive staging of a local test commit. Public provider fetch
  still needs acceptance from the deployment host.

These service checks use local Debian packages and temporary data, so the
Amazon Linux/Ubuntu installers, systemd, public ACME, DNS delegation, PHP-FPM
ACL behavior, reboot and signed update failure recovery still need a live VM.
Run the disposable Amazon Linux acceptance script in tests/installation with
SQL tests enabled to check the production adapters.

Open modules include mail, FTP/WebDAV, SSH/SFTP, terminal, Node/Python/Ruby
runtimes, OS quotas, private Git deployment, additional app management, DNSSEC
and secondary DNS, full-account snapshots, remote backup and migration.
The detailed status is in FEATURE_MATRIX.md and TODO.md.

## 2026-11-14 · 0.1.0-alpha.4

Added optional tenant SFTP on a separate OpenSSH listener with per-account
chroots and Ed25519 public key registration. Suspension removes authorization
for new SFTP sessions. Also added DNS Track and an in-panel operation inbox.
Local unit tests and sshd configuration validation passed. The disposable VM
runner now includes SFTP upload, chroot and revocation acceptance. The live
Amazon Linux SFTP run is still pending.

### EC2 upgrade recovery

The EC2 checkout reached alpha.4. Recovery on the installed instance stopped
after Nginx and PHP configuration validation with curl exit code 7. Updated
the upgrade to use the health check from the checkout, wait for the API socket,
HTTPS and agent separately, and identify failing endpoints. The operator
confirmed the retry worked on their EC2 instance. `make check` passed 57
tests. A local harness verified delayed startup and persistent connection
failure handling. The basic secret scan passed.

## 2026-11-14 · 0.1.0-alpha.5

Added Email Accounts and local routing for assigned domains. The optional
installer configures Postfix SMTP, authenticated TLS submission and Dovecot
IMAP/LMTP for virtual mailboxes with per-mailbox quotas. Mail starts in
loopback mode. Mailbox password changes, archive and restore, forwarding and
new-session denial on account suspension are implemented.

- `make check` passed 62 tests and Python, JavaScript and shell syntax.
- Chromium passed the panel browser checks, including creating a mailbox
  through a test API fixture. That check verified the form and request.
- Dovecot 2.3 and Postfix 3.7 parsed local generated configuration. Postfix
  read generated recipient and sender maps using a loopback adapter for
  interface enumeration in the workspace.
- The basic secret scan, OpenAPI validation and Bandit at the CI threshold passed.

The disposable Amazon Linux runner now includes SMTP relay denial, authenticated
submission, local forwarding, IMAP quota enforcement and archive access checks.
It still needs a live VM run. Public mail DNS, TLS certificate renewal, EC2
outbound delivery, DKIM/SPF/DMARC, spam filtering, webmail, logs and mail recovery
remain open. The production release gate remains closed.

## 2026-11-14 · 0.1.0-alpha.6

Website Backups can browse and search existing ZIPs, verify each file, and
recover an individual file to an unused path. The same account Linux identity
and file descriptor checks are used for backup creation and restore.

Added root-configured restic repositories for encrypted local, S3 and SFTP
website snapshots, an optional daily timer, a dashboard run/status screen,
host-scoped retention, and recovery into a private account backup list.
S3 uses scoped credentials in a mode-0600 file. SFTP checks a pinned host key.

- `make check` passed 66 local tests plus Python, JavaScript and shell syntax.
- Chromium exercised backup creation, browsing, verification and single-file
  recovery against the actual filesystem helper through a local HTTP fixture.
  It also exercised the off-site dispatch and progress display with a fixture.
- Restic 0.18 passed a local encrypted recovery drill, full repository check,
  wrong-password rejection and scoped retention. Upload and retrieval also
  passed against local HTTPS S3 and SSH/SFTP protocol fixtures.
- OpenAPI validation, Bandit at the CI threshold, the basic secret scan and
  systemd unit verification passed.

The optional disposable Amazon Linux runner exercises the installed CLI and
tenant-owned backup import. Live startup, scheduled jobs and remote-provider
recovery on EC2 remain pending. Off-site snapshots cover website files. SQL,
mail, DNS and full-account disaster recovery remain open.

## 2026-11-15 · 0.1.0-alpha.7

Off-site snapshots include selected managed MariaDB and PostgreSQL databases.
The administrator enrolls each database using its verified owner login.
Database clients run under the hosting UID. Recovery validates the checksum
and can import into a separate empty database in the same account. Database
enrollment, staging and restore commands are in [docs/BACKUPS.md](docs/BACKUPS.md).

- `make check` passed 70 tests plus Python, JavaScript and installer syntax checks.
- Chromium passed the panel workflows, including off-site backup status.
- The local test ran real MariaDB 11.8 and PostgreSQL 17 on loopback and used
  restic 0.18 to archive and recover both databases. Both engines recovered
  rows and binary values. PostgreSQL also recovered a view. Incorrect
  credentials and occupied destinations were rejected, and the repository
  passed a full data check.
- The restic integration tests passed website recovery, retention, a legacy
  alpha.6 website snapshot and invalid-archive handling.
- OpenAPI validation, the basic secret scan, Bandit at the CI threshold,
  and systemd unit verification passed.

MariaDB capture covers InnoDB tables. Each database capture has its own
consistency point. The daily timer and remote recovery on EC2 require live
acceptance. Mailbox, DNS, panel state and full-account recovery remain open.

## 2026-11-15 · 0.1.0-alpha.8

Managed DNS zones now join the encrypted off-site snapshot. Each record
export is bound to its source domain, checked against the snapshot hash,
and loaded as a draft by Zone Editor. An administrator reviews and
publishes the draft through the existing BIND configuration workflow.

- `make check` passed 71 tests plus Python, JavaScript and shell syntax checks.
- Restic recovered and verified an exported DNS zone. BIND 9 accepted the
  file rendered from its recovered records. Website recovery and previous
  snapshot formats also passed.
- Chromium loaded the restored DNS draft for the matching domain and rejected
  a different domain. The MariaDB and PostgreSQL round trips passed again.
- OpenAPI validation, Bandit at the CI threshold, the basic secret scan and
  systemd unit verification passed.

The disposable Amazon Linux test can publish the recovered zone and query
the running BIND service. Live EC2 and remote storage acceptance remain
open. Mailbox, panel state and full-account recovery remain open.

## 2026-11-15 · 0.1.0-alpha.9

The EC2 agent journal recorded a failed `useradd` and a follow-on exception
that hid the error. A live mount check confirmed that the agent saw `/etc` as
read-only and that the attempt left no Linux user, group or home. The agent saw
the mount as writable after the provisioning drop-in was applied.

Updated the agent, systemd unit and checkout upgrade path for local account
creation. The hosting-account list now exposes a scoped retry action for the
existing row, and the agent refuses to adopt partial Linux resources. Also set
the owner/group access on new account homes independently of the service umask.

`make check` passed 75 tests. Chromium exercised the retry UI against the real
WSGI API and showed the queued job for the same account. Live confirmation of
the user's retried account and Linux PHP-FPM pool is pending.
