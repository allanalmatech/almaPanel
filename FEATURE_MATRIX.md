# Feature matrix
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

**No complete cPanel-equivalent or production release claim.** “Implemented locally” means source plus local tests where specified, not full acceptance. “Adapter implemented” means actual Linux operation code exists but VM acceptance is not run. Target OS is Ubuntu 24.04; no OS is production-certified.

| Feature | Module | Implementation | Linux integration | Test status | Target OS | Limitations |
|---|---|---|---|---|---|---|
| Repository structure | Foundation | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Full requested directory layout; no remote push |
| Branding and ownership | Foundation | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Original branding and owner notices; licensing pending |
| Architecture and documentation | Foundation | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Status, limitations and API documented |
| Database schema | Foundation | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | SQLite schema v1; no customer SQL servers |
| Authentication | Foundation | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Scrypt, setup, secure sessions, rate limiting; MFA absent |
| Authorization | Foundation | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Server-side ownership and role tests |
| API | Foundation | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Documented core endpoints; OpenAPI generated |
| Privileged agent | Foundation | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | UID-checked Unix socket and closed operation list |
| Frontend shell | Foundation | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Original role-aware shell; browser run blocked |
| Installation framework | Foundation | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Source installer with conflict detection; no VM execution |
| File Manager | Files | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Core read/write/list/upload/download/mkdir/rename/delete only |
| Images | Files | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Directory Privacy | Files | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Disk Usage | Files | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Actual du size, no enforcement |
| Web Disk | Files | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| FTP Accounts | Files | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| FTP Connections | Files | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Backup | Files | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Backup Wizard | Files | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Git Version Control | Files | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Archive creation | Files | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| ZIP extraction | Files | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Trash and restore | Files | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Permissions editor | Files | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Syntax highlighting | Files | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Hidden files toggle | Files | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Drag and drop upload | Files | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| phpMyAdmin | Databases | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| MySQL Databases | Databases | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| MySQL Database Wizard | Databases | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Remote MySQL | Databases | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| PostgreSQL Databases | Databases | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| PostgreSQL Database Wizard | Databases | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| PostgreSQL administration UI | Databases | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Database backup and restore | Databases | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Database import/export | Databases | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Domains | Domains | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Nginx HTTP virtual host; external DNS |
| Addon Domains | Domains | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Additional domains share account docroot |
| Subdomains | Domains | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | FQDN accepted as normal HTTP vhost |
| Aliases | Domains | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Additional vhosts share public_html; no separate alias model |
| Redirects | Domains | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Zone Editor | Domains | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Dynamic DNS | Domains | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| DNS templates | Domains | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Nameserver configuration | Domains | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| DNSSEC | Domains | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| DNS import/export | Domains | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Domain verification | Domains | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Document roots | Domains | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Fixed public_html per account; no selectable per-domain roots |
| Email Accounts | Email | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Forwarders | Email | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Email Routing | Email | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Autoresponders | Email | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Default Address | Email | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Mailing Lists | Email | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Track Delivery | Email | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Global Email Filters | Email | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Email Filters | Email | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Email Deliverability | Email | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Address Importer | Email | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Spam Filters | Email | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Encryption | Email | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Calendars and Contacts | Email | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Webmail | Email | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Mailbox migration | Email | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Postfix Dovecot Rspamd integration | Email | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Visitors | Metrics | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Errors | Metrics | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Bandwidth | Metrics | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Raw Access Logs | Metrics | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Web analytics | Metrics | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Resource Usage | Metrics | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| CPU Usage | Metrics | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Admin load averages only; no CPU percentage |
| Memory Usage | Metrics | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Admin MemTotal/MemAvailable only |
| Processes | Metrics | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Inode Usage | Metrics | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| I/O Usage | Metrics | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| SSH Access | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| SSL/TLS | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| SSL/TLS Status | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Hotlink Protection | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| IP Blocker | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| ModSecurity | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Two-Factor Authentication | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Leech Protection | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Firewall | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Malware Scanner | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Security Advisor | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Fail2ban integration | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| File integrity monitoring | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Security notifications | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| PHP Selector | Software | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| MultiPHP Manager | Software | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| PHP INI Editor | Software | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| PHP Extensions | Software | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Node.js App Manager | Software | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Python App Manager | Software | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Ruby App Manager | Software | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Application Installer | Software | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| WordPress Manager | Software | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Composer | Software | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Git Deployment | Software | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Terminal | Software | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Create/clone/import repositories | Git | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| GitHub/GitLab/Bitbucket private auth | Git | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| SSH key management | Git | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Branch and history view | Git | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Fetch/pull/push | Git | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Release deployment and rollback | Git | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Webhook deployments | Git | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Pipeline stages | Git | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Environment secrets | Git | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Cron Jobs | Advanced | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| DNS Track | Advanced | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Indexes | Advanced | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Error Pages | Advanced | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Apache Handlers | Advanced | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| MIME Types | Advanced | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| API Tokens | Advanced | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Process Manager | Advanced | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Password & Security | Preferences | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Password change and session invalidation |
| Change Language | Preferences | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Contact Information | Preferences | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| User Manager | Preferences | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Theme Settings | Preferences | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Light/dark implementation; browser run blocked |
| Account Settings | Preferences | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Create hosting accounts | Administration | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Linux identity + PHP pool; pending VM acceptance |
| Suspend/unsuspend accounts | Administration | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | HTTP + panel state; does not kill existing processes |
| Terminate accounts | Administration | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Hosting packages | Administration | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Domain count only |
| Reseller accounts | Administration | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Owned accounts and account count only |
| Reseller branding | Administration | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Service management | Administration | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Nginx/PHP restart allowlist only |
| Server networking | Administration | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Server-wide settings | Administration | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Account quotas | Administration | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Audit logs | Administration | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Local SQLite recent events; no immutable external sink |
| Job history | Administration | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | State machine; root adapter tests pending |
| Updates | Administration | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Server health | Administration | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Actual /proc and systemd data |
| Notifications | Administration | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Control-plane backup | Backup and recovery | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Snapshot code; not customer recovery |
| Control-plane restore | Backup and recovery | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Same-server exact registry guard; not live tested |
| Full-account backup | Backup and recovery | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Website/database/mail/DNS backup | Backup and recovery | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Scheduled backups | Backup and recovery | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Incremental backups | Backup and recovery | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| SFTP/S3 remote storage | Backup and recovery | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Encrypted backup | Backup and recovery | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Retention and integrity policies | Backup and recovery | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Individual-file restore | Backup and recovery | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Complete-account restore | Backup and recovery | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Migration between servers | Backup and recovery | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Ubuntu clean installer | Installer and release | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | 24.04 amd64/arm64 targets, not certified |
| Public one-command endpoint | Installer and release | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Preflight checks | Installer and release | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Ubuntu-only; source checks tested, live not run |
| Safe uninstall/disable | Installer and release | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Preserves customer resources |
| Repair command | Installer and release | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Validation and restart only |
| Reproducible source artifact | Installer and release | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Deterministic source packaging; OS dependencies not frozen |
| Versioned upgrade and rollback | Installer and release | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Signed releases | Installer and release | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| GitHub Actions | Installer and release | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Workflow code present; remote execution not run |
| Dependency/secret scanning | Installer and release | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Dependabot action configuration + basic local scanner; full dependency audit pending |
| Production acceptance | Installer and release | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
