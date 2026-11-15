# Changelog
## 0.1.0-alpha.1 — 2026-11-14
Private evaluation source delivery; not an approved production release.

- Original role-aware grouped-tool interface, light/dark themes and responsive navigation.
- Authentication, one-time setup, sessions, CSRF/origin checks, throttling and audit.
- Package/reseller allocation and account ownership enforcement.
- Worker queue plus restricted Linux broker and tenant file helper.
- Ubuntu installer, Nginx/PHP configurations, control-plane backup/recovery utilities.
- Automated core/security tests, VM/browser test runners, CI, deterministic packaging.
- Complete status documentation; production gate remains closed.

Unimplemented requested modules are tracked in FEATURE_MATRIX.md; no claim of production installation, GitHub publication or public installer availability.

## 0.1.0-alpha.2

- Add GitHub Release update status and immediate checks for administrators.
- Add signed application updates with a systemd timer and code rollback.
- Add regular-file copying in File Manager.

## 0.1.0-alpha.3

- Add account-scoped MariaDB and PostgreSQL with reset, import and export.
- Add domain roots, aliases, redirects, TXT proof, forward DNS and site TLS.
- Add safe ZIP operations, uploads, copying, Trash and scheduled website backups.
- Add WordPress installation, public Git staging, PHP settings and scheduled
  PHP scripts.
- Add TOTP and recovery codes, read-only API tokens, profile details, directory
  passwords and site IP denial rules.
- Add website request and PHP log views, process metrics and the Amazon Linux
  disposable-VM acceptance script.
- Normalize installed source permissions during code updates.

## 0.1.0-alpha.4

- Add an optional, separate chrooted SFTP listener and dashboard key controls.
- Remove SFTP authorization when a hosting account is suspended.
- Add DNS Track and an account-scoped operation notification inbox.

## 0.1.0-alpha.4 upgrade recovery

- Use the checkout's health check when resuming an interrupted upgrade.
- Retry the API socket, Nginx HTTPS and agent probes independently. Report
  the failing endpoint and preserve the rollback snapshot.

## 0.1.0-alpha.5

- Add optional SMTP and IMAP on Postfix and Dovecot. Mail listens locally
  by default, with explicit opt-in for public IPv4 listeners.
- Add account-scoped aliases, mail routing, mailbox provisioning, password
  resets, quotas, archiving and restoration.
- Add tests for tenant scope, relay denial, TLS authentication, LMTP delivery,
  quota checks and archived mailbox login denial.

## 0.1.0-alpha.6

- Browse and search private website ZIPs, verify their integrity and restore
  individual files to unused paths.
- Configure encrypted off-site website snapshots with restic, run backups
  on demand or daily, track progress and failure in the administrator
  dashboard, preview retention, and recover and import one site ZIP.

## 0.1.0-alpha.7

- Enroll managed MariaDB and PostgreSQL databases for encrypted off-site
  backups using their account-owned database logins.
- Record dump checksums and sizes, list and recover individual database
  dumps, and optionally import into a different empty database.

## 0.1.0-alpha.8

- Include almaPanel-managed DNS zones in encrypted off-site snapshots.
- List and recover zone records by account and domain, and load the
  verified export into Zone Editor for review and publishing.
