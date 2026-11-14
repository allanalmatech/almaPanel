# Feature matrix
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

**Alpha.3 evaluation.** Core installation and first-admin setup were verified by
the operator on Amazon Linux 2023 during alpha.1. The table distinguishes local
tests from acceptance on an installed Ubuntu or Amazon Linux VM.

| Feature | Module | Implementation | Linux integration | Test status | Target OS | Limitations |
|---|---|---|---|---|---|---|
| Repository structure | Foundation | Published | GitHub | Source on main | Ubuntu 24.04 / AL2023 | Release signing assets pending |
| Branding and ownership | Foundation | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Original branding and owner notices; licensing pending |
| Architecture and documentation | Foundation | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Status, limitations and API documented |
| Database schema | Foundation | Implemented locally | SQLite with additive settings tables | Local WSGI tests | Ubuntu 24.04 / AL2023 | SQLite is panel storage only |
| Authentication | Foundation | Implemented locally | Password, secure cookie, TOTP and recovery codes | Local replay and revocation tests | Ubuntu 24.04 / AL2023 | EC2 and browser acceptance pending |
| Authorization | Foundation | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Server-side ownership and role tests |
| API | Foundation | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Documented core endpoints; OpenAPI generated |
| Privileged agent | Foundation | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | UID-checked Unix socket and closed operation list |
| Frontend shell | Foundation | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Original role-aware shell; browser run blocked |
| Installation framework | Foundation | Partial | Ubuntu and Amazon Linux adapters | Amazon Linux alpha.1 installed by operator | Ubuntu 24.04 / AL2023 | Fresh alpha.3 runs and reboot pending |
| File Manager | Files | Expanded | Tenant UID, descriptor paths, archive limits and private Trash | Local round trips and rejection tests | Ubuntu 24.04 / AL2023 | Browser tests and heavy workload acceptance pending |
| Images | Files | Partial | PNG, JPEG, GIF and WebP preview | JS syntax | Ubuntu 24.04 / AL2023 | No resizing or conversion |
| Directory Privacy | Files | Implemented locally | Nginx HTTPS Basic authentication | Local real static and PHP route checks | Ubuntu 24.04 / AL2023 | Dedicated document root; one login per rule |
| Disk Usage | Files | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Actual du size, no enforcement |
| Web Disk | Files | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| FTP Accounts | Files | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| FTP Connections | Files | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Backup | Files | Partial | Private website ZIP and SQL dump | Local ZIP restore | Ubuntu 24.04 / AL2023 | Website archive and SQL are separate; no mail data |
| Backup Wizard | Files | Partial | Website backups and SQL import/export UI | Local ZIP tests | Ubuntu 24.04 / AL2023 | Full-account guided recovery remains open |
| Git Version Control | Files | Partial | Public Git branch staging under tenant UID | URL and branch validation | Ubuntu 24.04 / AL2023 | No private repos, webhooks, build scripts or push |
| Archive creation | Files | Implemented locally | ZIP under tenant UID | Round trip and size budget tests | Ubuntu 24.04 / AL2023 | 64 MiB and 5,000-entry default limits |
| ZIP extraction | Files | Implemented locally | Staging, size limits and no-overwrite publish | Rejects links, absolute paths and traversal | Ubuntu 24.04 / AL2023 | Live workload acceptance pending |
| Trash and restore | Files | Implemented locally | Private account storage | Local restore and conflict checks | Ubuntu 24.04 / AL2023 | User-managed retention |
| Permissions editor | Files | Implemented locally | Allowed chmod modes for owned files/folders | Local link denial tests | Ubuntu 24.04 / AL2023 | VM ACL acceptance pending |
| Syntax highlighting | Files | Partial | Highlighted source preview | JS syntax | Ubuntu 24.04 / AL2023 | Lightweight preview, no language grammar editor |
| Hidden files toggle | Files | Implemented locally | Frontend filter | JS syntax | Ubuntu 24.04 / AL2023 | Browser acceptance pending |
| Drag and drop upload | Files | Implemented locally | File drop and no-overwrite upload | Local no-overwrite test | Ubuntu 24.04 / AL2023 | 1 MiB per file |
| phpMyAdmin | Databases | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| MySQL Databases | Databases | Partial | Local MariaDB database + dedicated login | Real MariaDB local create/read/drop and isolation | Ubuntu 24.04 / AL2023 | One login per DB; MySQL server adapter and remote access remain open |
| MySQL Database Wizard | Databases | Partial | One form creates a database + login | Local adapter tests | Ubuntu 24.04 / AL2023 | Extra users and granular grants remain open |
| Remote MySQL | Databases | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| PostgreSQL Databases | Databases | Partial | Local database + dedicated login | Real PostgreSQL local create/read/drop and isolation | Ubuntu 24.04 / AL2023 | One login per DB; VM service setup pending |
| PostgreSQL Database Wizard | Databases | Partial | One form creates database + login | Local adapter tests | Ubuntu 24.04 / AL2023 | Extra users and granular grants remain open |
| PostgreSQL administration UI | Databases | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Database backup and restore | Databases | Partial | Tenant SQL/custom dumps and current database login | Local SQL checks | Ubuntu 24.04 / AL2023 | Imports limited to 1 MiB; scheduling and remote targets remain open |
| Database import/export | Databases | Partial | MariaDB SQL and PostgreSQL custom archives | Local adapter validation | Ubuntu 24.04 / AL2023 | Live VM acceptance pending |
| Domains | Domains | Implemented locally | Nginx sites, aliases and redirects | Real Nginx config validation | Ubuntu 24.04 / AL2023 | VM public DNS and TLS acceptance pending |
| Addon Domains | Domains | Implemented locally | Individual document roots under public_html | Real Nginx config validation | Ubuntu 24.04 / AL2023 | Public VM tests pending |
| Subdomains | Domains | Implemented locally | FQDN with own document root | Real Nginx config validation | Ubuntu 24.04 / AL2023 | Registrar and public DNS setup required |
| Aliases | Domains | Implemented locally | Alias to same-account website | Real Nginx config validation | Ubuntu 24.04 / AL2023 | Protected targets cannot have aliases |
| Redirects | Domains | Implemented locally | HTTP and HTTPS URL redirect | Real Nginx config validation | Ubuntu 24.04 / AL2023 | VM tests pending |
| Zone Editor | Domains | Partial | Admin-managed BIND forward zones | Real BIND zone validation | Ubuntu 24.04 / AL2023 | No DNSSEC, PTR delegation or secondary automation |
| Dynamic DNS | Domains | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| DNS templates | Domains | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Nameserver configuration | Domains | Partial | Configure forward-zone NS records at setup | Real BIND zone validation | Ubuntu 24.04 / AL2023 | External nameserver and registrar setup required |
| DNSSEC | Domains | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| DNS import/export | Domains | Partial | JSON record list | Typed DNS case tests | Ubuntu 24.04 / AL2023 | BIND master-file imports remain open |
| Domain verification | Domains | Implemented locally | DNS TXT proof before tenant claim | Local WSGI authorization tests | Ubuntu 24.04 / AL2023 | Requires dig and public DNS |
| Document roots | Domains | Implemented locally | Validated paths inside tenant public_html | Real Nginx config validation | Ubuntu 24.04 / AL2023 | Public VM tests pending |
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
| Visitors | Metrics | Partial | Recent Nginx request sample | Local Nginx validation | Ubuntu 24.04 / AL2023 | No visitor analytics or long-term aggregates |
| Errors | Metrics | Partial | Nginx response statuses and PHP-FPM log tail | Local renderer tests | Ubuntu 24.04 / AL2023 | No centralized log aggregation |
| Bandwidth | Metrics | Partial | Recent byte counts from managed Nginx log | Local renderer tests | Ubuntu 24.04 / AL2023 | No monthly quota or billing meter |
| Raw Access Logs | Metrics | Partial | Dashboard sample with no query strings | Real Nginx config validation | Ubuntu 24.04 / AL2023 | No historical log export |
| Web analytics | Metrics | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Resource Usage | Metrics | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| CPU Usage | Metrics | Partial | Account process lifetime CPU | Local Linux process parsing | Ubuntu 24.04 / AL2023 | No interval usage graph or resource limits |
| Memory Usage | Metrics | Partial | Host memory and account process RSS | Local Linux process parsing | Ubuntu 24.04 / AL2023 | RSS can double-count shared pages |
| Processes | Metrics | Partial | Read-only per-UID process list | Local Linux process parsing | Ubuntu 24.04 / AL2023 | No process signaling UI |
| Inode Usage | Metrics | Partial | Real account inode count | GNU du adapter | Ubuntu 24.04 / AL2023 | No enforced inode quota |
| I/O Usage | Metrics | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| SSH Access | Security | Partial | Independent chrooted, public-key SFTP with key revocation and suspension | OpenSSH config and local key tests passed | Ubuntu 24.04 / AL2023 | Live login/upload acceptance pending; shell access remains open |
| SSL/TLS | Security | Partial | Certbot HTTP-01, custom PEM, redirects and renewal timer | Local Nginx/OpenSSL checks | Ubuntu 24.04 / AL2023 | Public ACME, wildcard and reboot validation pending |
| SSL/TLS Status | Security | Partial | Live expiry check and dashboard warning status | Local OpenSSL checks | Ubuntu 24.04 / AL2023 | No email alert delivery |
| Hotlink Protection | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| IP Blocker | Security | Implemented locally | Per-site Nginx denial rules | Local rules tests | Ubuntu 24.04 / AL2023 | EC2 firewall unchanged; proxy awareness remains open |
| ModSecurity | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Two-Factor Authentication | Security | Implemented locally | TOTP and single-use recovery codes | Local replay and revocation tests | Ubuntu 24.04 / AL2023 | Browser enrollment acceptance pending |
| Leech Protection | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Firewall | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Malware Scanner | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Security Advisor | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Fail2ban integration | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| File integrity monitoring | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Security notifications | Security | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| PHP Selector | Software | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| MultiPHP Manager | Software | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| PHP INI Editor | Software | Partial | Allowlisted per-account PHP-FPM values | Local validation | Ubuntu 24.04 / AL2023 | No arbitrary INI directives or multiple versions |
| PHP Extensions | Software | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Node.js App Manager | Software | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Python App Manager | Software | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Ruby App Manager | Software | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Application Installer | Software | Partial | Checksum-verified WordPress | Real PHP and MariaDB initialization | Ubuntu 24.04 / AL2023 | Other installers remain open |
| WordPress Manager | Software | Partial | New site installation | Real PHP and MariaDB initialization | Ubuntu 24.04 / AL2023 | Updates, plugin/theme management and staging remain open |
| Composer | Software | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Git Deployment | Software | Partial | Public branch staging under tenant UID | URL and ref validation | Ubuntu 24.04 / AL2023 | Domain promotion is manual; no automatic workflows |
| Terminal | Software | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Create/clone/import repositories | Git | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| GitHub/GitLab/Bitbucket private auth | Git | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| SSH key management | Git | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Branch and history view | Git | Partial | Choose a branch and view its commit in jobs | URL/ref validation | Ubuntu 24.04 / AL2023 | No commit history UI |
| Fetch/pull/push | Git | Partial | Fetch public branch for staging | URL/ref validation | Ubuntu 24.04 / AL2023 | No push or existing checkout fetch |
| Release deployment and rollback | Git | Partial | Stage new folder, switch document root manually | Local renderer tests | Ubuntu 24.04 / AL2023 | No automatic rollback workflow |
| Webhook deployments | Git | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Pipeline stages | Git | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Environment secrets | Git | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Cron Jobs | Advanced | Partial | Schedule existing PHP scripts with time/resource limits | Scheduler tests | Ubuntu 24.04 / AL2023 | No arbitrary shell commands or cron expressions |
| DNS Track | Advanced | Implemented | Fixed DNS lookups via dig | Local input and API verification | Ubuntu 24.04 / AL2023 | Resolver visibility only |
| Indexes | Advanced | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Error Pages | Advanced | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Apache Handlers | Advanced | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| MIME Types | Advanced | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| API Tokens | Advanced | Implemented locally | Read-only 90-day bearer tokens with revocation | Local auth/scope tests | Ubuntu 24.04 / AL2023 | No configurable scopes or write tokens |
| Process Manager | Advanced | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Password & Security | Preferences | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Password change and session invalidation |
| Change Language | Preferences | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Contact Information | Preferences | Implemented locally | Stored display name and email | Local WSGI schema | Ubuntu 24.04 / AL2023 | Notification integration pending |
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
| Updates | Administration | Partial | Signed code updater with rollback | Local version and archive checks | Ubuntu 24.04 / AL2023 | No signed release assets or live EC2 rollback verification |
| Server health | Administration | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Actual /proc and systemd data |
| Notifications | Administration | Partial | Account-scoped job outcome inbox with per-user dismissal | Local API tests | Ubuntu 24.04 / AL2023 | Delivery and maintenance notifications remain open |
| Control-plane backup | Backup and recovery | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Snapshot code; not customer recovery |
| Control-plane restore | Backup and recovery | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Same-server exact registry guard; not live tested |
| Full-account backup | Backup and recovery | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Website/database/mail/DNS backup | Backup and recovery | Partial | Website ZIP plus separate SQL export | Local website restore | Ubuntu 24.04 / AL2023 | Mail, DNS and unified snapshot remain open |
| Scheduled backups | Backup and recovery | Partial | Daily or weekly website snapshots | Local scheduler and retention tests | Ubuntu 24.04 / AL2023 | No SQL, mail or DNS scheduling |
| Incremental backups | Backup and recovery | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| SFTP/S3 remote storage | Backup and recovery | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Encrypted backup | Backup and recovery | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Retention and integrity policies | Backup and recovery | Partial | Scheduled website retention and ZIP CRC validation | Local retention tests | Ubuntu 24.04 / AL2023 | No complete policy, encryption or remote verification |
| Individual-file restore | Backup and recovery | Partial | Trash restoration and ZIP restore to a new folder | Local conflict and restore tests | Ubuntu 24.04 / AL2023 | No selective restore UI from snapshots |
| Complete-account restore | Backup and recovery | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Migration between servers | Backup and recovery | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Ubuntu clean installer | Installer and release | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | 24.04 amd64/arm64 targets, not certified |
| Public one-command endpoint | Installer and release | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
| Preflight checks | Installer and release | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Ubuntu-only; source checks tested, live not run |
| Safe uninstall/disable | Installer and release | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Preserves customer resources |
| Repair command | Installer and release | Adapter implemented / partial | Real adapter; not live validated | VM acceptance pending | Ubuntu 24.04 target | Validation and restart only |
| Reproducible source artifact | Installer and release | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Deterministic source packaging; OS dependencies not frozen |
| Versioned upgrade and rollback | Installer and release | Partial | Application code updater | Local archive and rollback tests | Ubuntu 24.04 / AL2023 | Schema, OS and dependency upgrades remain manual |
| Signed releases | Installer and release | Partial | Ed25519 verification and build script | Local version/archive validation | Ubuntu 24.04 / AL2023 | Publisher key and release assets still required |
| GitHub Actions | Installer and release | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Workflow code present; remote execution not run |
| Dependency/secret scanning | Installer and release | Implemented locally / partial | Not applicable or control-plane only | Core tests where applicable; see TESTING | Ubuntu 24.04 target | Dependabot action configuration + basic local scanner; full dependency audit pending |
| Production acceptance | Installer and release | Not implemented | None | Not run | Ubuntu 24.04 target | Outstanding requested scope |
