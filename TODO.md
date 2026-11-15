# TODO
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

Legend: [ ] not started; [~] in progress; [x] completed **local subtask**. No full Linux feature is complete before live acceptance. See FEATURE_MATRIX for scope.

## Milestone 1 — Foundation
- [x] Create versioned source layout and ownership notices.
- [x] Implement/test authentication, SQLite schema, API and authorization locally.
- [x] Implement/test file-descriptor boundaries with real temporary files.
- [~] Root broker, worker, shell and installer: code present; VM/UI acceptance incomplete.
- [ ] Verify first boot and reboot on Ubuntu amd64 and arm64.

## Milestone 2 — Hosting core
- [~] Linux accounts, PHP pools, HTTP vhosts, basic file manager.
- [ ] Customer databases, DNS and domain verification.
- [ ] Extend file manager safely with requested advanced operations.

## Milestone 3 — Hosting services
- [~] Mail, ACME renewal, SFTP/SSH, cron, Git, application hosting.

## Milestone 4 — Advanced hosting
- [~] Reseller account allocation and domain-count packages.
- [ ] Real disk/cgroup/inode/bandwidth quotas and full customer backups.
- [ ] WordPress/application installer and runtime managers.

## Milestone 5 — Administration
- [~] Service restarts, audit, jobs and real host statistics.
- [ ] System networking, updates, migration, notifications and security modules.

## Milestone 6 — Hardening
- [x] Local core/security tests and Python/JavaScript/shell syntax checks.
- [x] Static security review at medium/high threshold, documented socket exception.
- [ ] Complete browser acceptance (Chromium blocked by workspace).
- [ ] Live tenant isolation, quotas, install/reboot, upgrade/rollback, full restore, failure recovery.
- [ ] Independent security review and dependency/supply-chain hardening.

## Milestone 7 — Release
- [~] Deterministic evaluation source archive and GitHub workflows.
- [ ] Owner license approval and signed-release trust.
- [ ] Publish approved GitHub repository and public installer infrastructure.
- [ ] Satisfy all mandatory acceptance gates; only then publish production artifacts.

## Detailed scope backlog

### Foundation
- [~] Repository structure
- [~] Branding and ownership
- [~] Architecture and documentation
- [~] Database schema
- [~] Authentication
- [~] Authorization
- [~] API
- [~] Privileged agent
- [~] Frontend shell
- [~] Installation framework

### Files
- [~] File Manager
- [ ] Images
- [ ] Directory Privacy
- [~] Disk Usage
- [ ] Web Disk
- [ ] FTP Accounts
- [ ] FTP Connections
- [ ] Backup
- [ ] Backup Wizard
- [ ] Git Version Control
- [ ] Archive creation
- [ ] ZIP extraction
- [ ] Trash and restore
- [ ] Permissions editor
- [ ] Syntax highlighting
- [ ] Hidden files toggle
- [ ] Drag and drop upload

### Databases
- [ ] phpMyAdmin
- [ ] MySQL Databases
- [ ] MySQL Database Wizard
- [ ] Remote MySQL
- [ ] PostgreSQL Databases
- [ ] PostgreSQL Database Wizard
- [ ] PostgreSQL administration UI
- [ ] Database backup and restore
- [ ] Database import/export

### Domains
- [~] Domains
- [~] Addon Domains
- [~] Subdomains
- [~] Aliases
- [ ] Redirects
- [ ] Zone Editor
- [ ] Dynamic DNS
- [ ] DNS templates
- [ ] Nameserver configuration
- [ ] DNSSEC
- [ ] DNS import/export
- [ ] Domain verification
- [~] Document roots

### Email
- [~] Email Accounts with mailbox quotas, archives and password resets. Live acceptance pending.
- [~] Forwarders with alias loop validation. Live acceptance pending.
- [~] Local mail routing for assigned domains. Remote routing remains open.
- [ ] Autoresponders
- [ ] Default Address
- [ ] Mailing Lists
- [ ] Track Delivery
- [ ] Global Email Filters
- [ ] Email Filters
- [ ] Email Deliverability
- [ ] Address Importer
- [ ] Spam Filters
- [ ] Encryption
- [ ] Calendars and Contacts
- [ ] Webmail
- [ ] Mailbox migration
- [~] Postfix and Dovecot setup. Validate local SMTP/IMAP and public delivery on the target host.
- [ ] Rspamd spam filtering and mail signing.

### Metrics
- [ ] Visitors
- [ ] Errors
- [ ] Bandwidth
- [ ] Raw Access Logs
- [ ] Web analytics
- [ ] Resource Usage
- [~] CPU Usage
- [~] Memory Usage
- [ ] Processes
- [ ] Inode Usage
- [ ] I/O Usage

### Security
- [ ] SSH Access
- [ ] SSL/TLS
- [ ] SSL/TLS Status
- [ ] Hotlink Protection
- [ ] IP Blocker
- [ ] ModSecurity
- [ ] Two-Factor Authentication
- [ ] Leech Protection
- [ ] Firewall
- [ ] Malware Scanner
- [ ] Security Advisor
- [ ] Fail2ban integration
- [ ] File integrity monitoring
- [ ] Security notifications

### Software
- [ ] PHP Selector
- [ ] MultiPHP Manager
- [ ] PHP INI Editor
- [ ] PHP Extensions
- [ ] Node.js App Manager
- [ ] Python App Manager
- [ ] Ruby App Manager
- [ ] Application Installer
- [ ] WordPress Manager
- [ ] Composer
- [ ] Git Deployment
- [ ] Terminal

### Git
- [ ] Create/clone/import repositories
- [ ] GitHub/GitLab/Bitbucket private auth
- [ ] SSH key management
- [ ] Branch and history view
- [ ] Fetch/pull/push
- [ ] Release deployment and rollback
- [ ] Webhook deployments
- [ ] Pipeline stages
- [ ] Environment secrets

### Advanced
- [ ] Cron Jobs
- [ ] DNS Track
- [ ] Indexes
- [ ] Error Pages
- [ ] Apache Handlers
- [ ] MIME Types
- [ ] API Tokens
- [ ] Process Manager

### Preferences
- [~] Password & Security
- [ ] Change Language
- [ ] Contact Information
- [ ] User Manager
- [~] Theme Settings
- [ ] Account Settings

### Administration
- [~] Create hosting accounts
- [~] Suspend/unsuspend accounts
- [ ] Terminate accounts
- [~] Hosting packages
- [~] Reseller accounts
- [ ] Reseller branding
- [~] Service management
- [ ] Server networking
- [ ] Server-wide settings
- [ ] Account quotas
- [~] Audit logs
- [~] Job history
- [ ] Updates
- [~] Server health
- [ ] Notifications

### Backup and recovery
- [~] Control-plane backup
- [~] Control-plane restore
- [ ] Full-account backup
- [ ] Website/database/mail/DNS backup
- [ ] Scheduled backups
- [~] Restic deduplication across website snapshots. Expand to all account resources.
- [~] SFTP/S3 remote website repository support. Verify each remote backend.
- [~] Encrypted website backup and recovery. Add DB, mail and DNS coverage.
- [ ] Retention and integrity policies
- [~] Browse and restore an individual ZIP member. Live EC2 verification pending.
- [ ] Complete-account restore
- [ ] Migration between servers

### Installer and release
- [~] Ubuntu clean installer
- [ ] Public one-command endpoint
- [~] Preflight checks
- [~] Safe uninstall/disable
- [~] Repair command
- [~] Reproducible source artifact
- [ ] Versioned upgrade and rollback
- [ ] Signed releases
- [~] GitHub Actions
- [~] Dependency/secret scanning
- [ ] Production acceptance

## Consolidated requested backlog — 2026-11-14

This section reconciles the user’s alpha.2 checklist. Items remain open until implementation and required acceptance pass.

### Dashboard and navigation

- [ ] Full grouped catalog and sidebar
- [ ] notifications
- [ ] language selector
- [ ] profile controls
- [ ] contextual help
- [ ] keyboard/mobile acceptance
- [ ] primary domain and shared IP
- [ ] quota bars
- [ ] bandwidth and resource counts
- [ ] entry processes, I/O, inodes, tenant CPU/RAM

### File Manager

- [ ] Folder tree
- [ ] drag-and-drop uploads
- [ ] recursive search
- [ ] previews
- [ ] syntax highlighting
- [~] hidden-files toggle — implemented, browser acceptance pending
- [~] permission editor — implemented, live ACL acceptance pending
- [ ] archives and safe ZIP extraction
- [ ] trash/restore
- [ ] recursive copy
- [ ] full move workflow

### Other Files tools

- [ ] Images
- [ ] Directory Privacy
- [ ] WebDAV
- [ ] FTP accounts and connections
- [ ] tenant SSH/SFTP
- [ ] Backup Wizard
- [ ] Git Version Control
- [ ] storage and inode enforcement

### Databases

- [ ] MySQL/MariaDB and PostgreSQL
- [ ] database/user CRUD
- [ ] privileges
- [ ] password resets
- [ ] remote controls
- [ ] connection details
- [ ] usage
- [ ] SQL import/export
- [ ] backup/restore
- [ ] wizards
- [ ] phpMyAdmin
- [ ] PostgreSQL admin UI

### Domains and DNS

- [ ] Primary/addon/subdomain/parked domains and aliases
- [ ] per-domain roots
- [ ] redirects
- [ ] verification
- [ ] authoritative DNS
- [ ] Zone Editor
- [ ] dynamic DNS
- [ ] templates
- [ ] custom nameservers
- [ ] DNSSEC
- [ ] import/export
- [ ] validation/reloads
- [ ] A/AAAA/CNAME/MX/TXT/SRV/CAA/PTR records

### Email

- [~] Mailbox provisioning, quotas, password resets, archive and restore. Live quota acceptance pending.
- [~] TLS-protected SMTP submission and IMAP. Live service acceptance pending.
- [ ] webmail
- [~] Forwarding and aliases. Autoresponders and catch-all remain open.
- [~] Local mail routing. Remote routing, mailing lists and imports remain open.
- [ ] global and mailbox filters
- [ ] spam
- [ ] encryption
- [ ] calendars/contacts
- [ ] tracking/logs/queues
- [ ] DKIM/SPF/DMARC
- [~] Mail TLS certificates and manual refresh. Automated renewal verification remains open.
- [ ] backups/migration
- [~] Postfix and Dovecot configuration. Rspamd and Roundcube remain open.

### Site SSL/TLS

- [ ] ACME issuance/renewal
- [ ] wildcard DNS challenges
- [ ] custom certificates
- [ ] validation/status/expiry alerts
- [ ] HTTPS redirects
- [ ] per-site TLS

### Metrics

- [ ] Visitors/errors/bandwidth/access logs
- [ ] analytics
- [ ] resource graphs
- [ ] processes
- [ ] CPU/RAM/I/O/entry processes/inodes

### Security

- [ ] MFA
- [ ] API tokens
- [ ] tenant SSH keys
- [ ] firewall/Fail2ban/IP blocking/ModSecurity
- [ ] hotlink/leech protection
- [ ] malware/integrity scans
- [ ] advisor/notifications
- [ ] secret management
- [ ] externally retained audit
- [ ] hostile tenant tests

### PHP and app hosting

- [ ] PHP versions and per-domain selection
- [ ] INI/extensions/resource settings/error logs
- [ ] Composer
- [ ] Node/Python/Ruby
- [ ] dependencies/isolation/supervision/proxies/environment/logs/restarts/health

### Application installer and WordPress

- [ ] WordPress/Joomla/Drupal/phpBB/PrestaShop installs
- [ ] database/TLS setup
- [ ] versions/core/plugins/themes
- [ ] backup/restore
- [ ] staging/promotion
- [ ] maintenance/security

### Customer Git deployment

- [ ] Create/clone/import
- [ ] provider connections/private auth
- [ ] SSH keys
- [ ] branches/history/status/fetch/pull/push
- [ ] webhooks/manual/automatic deployment
- [ ] secrets/logs/notifications
- [ ] build/test/release/rollback

### Advanced tools and preferences

- [ ] Cron/DNS Track/Indexes/Error Pages/Handlers/MIME/Process Manager
- [ ] language/contact/user/account settings
- [ ] browser terminal identity/WebSocket/resize/timeouts/audit/admin authorization

### Hosting packages and resellers

- [ ] Disk/bandwidth/mail/database/FTP/CPU/RAM/process/I/O/inode limits
- [ ] retention
- [ ] SSH/Git/app permissions
- [ ] reseller branding/allocation/reports

### Server administration

- [ ] Termination
- [ ] stop suspended workloads
- [ ] hostname/network/IP
- [ ] server settings
- [ ] DNS/mail/database/PHP management
- [ ] service controls/logs/packages/maintenance/reboot/scheduling
- [ ] administrators/notifications

### Backups and migration

- [ ] Website/database/mail/DNS/full-account
- [ ] scheduling/incremental
- [ ] SFTP/S3
- [ ] encryption/retention/integrity
- [ ] download/progress/alerts
- [ ] file/database/account restore
- [ ] migration/disaster recovery

### Installer, updates and releases

- [ ] Public installer endpoint
- [ ] signing/publication automation
- [ ] dependency scanning/provenance
- [ ] dependency/schema/platform upgrades
- [ ] live updater/rollback tests
- [ ] key enrollment
- [ ] signed release assets

### Production acceptance and documentation

- [ ] Browser/accessibility
- [ ] service integration
- [ ] isolation/quotas/reboot/recovery
- [ ] full restore/upgrades/mail/DNS/TLS/performance/security review
- [ ] reconcile feature matrix/OpenAPI/guides/release checklist

## Alpha.3 implementation and acceptance

This block overrides older status labels for the same work. The consolidated
18-area checklist above remains the scope. Every partial item still needs its
remaining behavior and live acceptance before completion.

- [x] Implement ZIP creation and safe extraction, large-file download, folder
  navigation and search, recursive copy, move, Trash, image preview, source
  highlighting, and drag-and-drop upload.
- [x] Implement dedicated per-domain roots, aliases, redirects, primary domain,
  removal, and DNS TXT verification for tenant claims.
- [x] Implement local MariaDB/PostgreSQL database provisioning, connection
  information, password reset, size, deletion and tenant import/export.
- [x] Implement optional authoritative forward DNS with typed records and JSON
  import/export, plus Nginx website certificate issuance, upload and renewal.
- [x] Implement private website backups, schedule, retention and restore to a
  new folder. Database exports remain separately downloadable.
- [x] Add WordPress install, public Git staging, per-UID process and recent
  Nginx/PHP metrics, PHP pool settings, and scheduled PHP scripts.
- [x] Implement TOTP, recovery codes, read-only API tokens, contact details,
  directory passwords and website IP denial rules.
- [ ] Validate the complete alpha.3 upgrade, reboot, tenant ACL protections,
  optional-service installation, ACME renewal and real DNS on Amazon Linux.
- [ ] Validate browser layout and keyboard workflows on software that permits
  Chromium to run. Exercise both administrator and tenant actions.
- [ ] Finish email, FTP/WebDAV, tenant SSH/SFTP, terminal, application runtimes,
  resource enforcement, fuller database and WordPress administration,
  private Git deployment, and full-account backups and migration.
- [ ] Finish signed GitHub release publication, public installer endpoint,
  rollback for schema/OS changes, external audit retention and release review.

## Alpha.4 implementation and acceptance
- [x] Add account SFTP key registration and revocation on an independent
  chrooted listener. Suspension prevents new logins.
- [x] Add DNS Track for common record queries and a dashboard job inbox.
- [ ] Run the chroot, upload, authentication and revocation acceptance on EC2.
- [ ] Add secure interactive shell and browser terminal after isolation review.

## Alpha.6 backup implementation and acceptance

- [x] Browse and search website ZIPs, verify file integrity and selectively
  restore to unused paths. Local and Chromium checks passed.
- [x] Implement encrypted website backups through restic, daily scheduling,
  scoped retention, recovery and import into an active account's private
  backup list. A local encrypted repository passed a recovery drill.
- [x] Add administrator controls to request an off-site backup and see
  the latest run's progress or failure.
- [ ] Run the installed EC2 backup, daily timer and restore with real tenants
  and the selected S3 or SFTP provider.
- [ ] Add Maildir and account configuration to full backups.
- [ ] Add complete account restore, scheduled failure alerts and migration.

## Alpha.7 off-site database implementation and acceptance

- [x] Enroll managed MariaDB and PostgreSQL databases in encrypted off-site
  snapshots. Verify restored data, checksum failures and occupied destinations.
- [x] Keep existing website-only backup manifests and recoveries compatible.
- [ ] Verify database enrollment, scheduled backup and SQL restoration on
  a disposable Amazon Linux VM with the real storage provider.
- [ ] Add backup coverage for MariaDB objects beyond InnoDB tables, and
  coordinate consistency across databases and website files.

## Alpha.8 managed DNS implementation and acceptance

- [x] Archive managed DNS records, recover a verified export and validate it
  in BIND. Zone Editor verifies the export's domain before loading a draft.
- [ ] Run the live Amazon Linux backup and republish checks.
- [ ] Cover external DNS integrations and full-account recovery.
