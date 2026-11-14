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
- [ ] Mail, ACME renewal, SFTP/SSH, cron, Git, application hosting.

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
- [ ] Email Accounts
- [ ] Forwarders
- [ ] Email Routing
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
- [ ] Postfix Dovecot Rspamd integration

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
- [ ] Incremental backups
- [ ] SFTP/S3 remote storage
- [ ] Encrypted backup
- [ ] Retention and integrity policies
- [ ] Individual-file restore
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
