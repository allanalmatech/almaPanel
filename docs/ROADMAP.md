# Tool roadmap
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

The owner asked for the full tool set of a familiar hosting control panel. This
page lists every requested tool, where almaPanel stands, and what each remaining
tool needs. The dashboard shows planned tools with a **Planned** badge; they
open a status page, never a non-working form.

almaPanel uses original names, artwork and code. Commercial add-ons from other
vendors are not bundled; the original almaPanel tool that covers the same need
is listed instead.

Status keys: **Available** (working in this release), **Alias** (an existing
tool under a familiar name), **Planned** (phase in brackets), **Not applicable**.

## Email

| Tool | Status | What it needs |
|---|---|---|
| Email Accounts | Available | Optional Postfix and Dovecot setup |
| Forwarders | Alias → Email Accounts | — |
| Default Address | Available (alpha.17) | — |
| Autoresponders | Available (alpha.17) | Mail filter plugin from `enable-mail.sh` |
| Email Filters, Global Email Filters | Available (alpha.17) | Mail filter plugin from `enable-mail.sh` |
| Email Disk Usage | Available (alpha.17) | Cleanup actions planned |
| Track Delivery | Available (alpha.17) | — |
| Email Deliverability | Available (alpha.17) | DKIM signing service planned (A) |
| Spam Filters, Configure Greylisting | Planned (A) | A spam filter service (for example rspamd) with per-account settings |
| Email Routing | Planned (A) | Local or remote delivery per domain in Postfix transport maps |
| Address Importer | Planned (A) | CSV import that reuses mailbox and forwarder validation |
| Mailing Lists | Planned (C) | A list manager service and Postfix integration |
| Encryption | Planned (E) | GnuPG key management per mailbox |
| Challenge-Response Filter | Planned (E) | Sender confirmation queue; evaluate after spam filtering |

## Files

| Tool | Status | What it needs |
|---|---|---|
| File Manager, Images, Trash | Available | — |
| Directory Privacy | Alias → Website Security | — |
| Disk Usage, Website Backups, SFTP Access | Available | — |
| Git Deployment | Available | Public repositories only |
| FTP Accounts | Planned (B) | FTP server with virtual users chrooted to folders, TLS required |
| Web Disk | Planned (B) | WebDAV over HTTPS with per-account credentials |
| Backup Wizard | Planned (B) | Guided flow over existing website, database and off-site backups |
| Git Version Control | Planned (B) | Private repositories, deploy keys and branch deployment under the account UID |
| JetBackup 5 (third-party) | Not bundled | Covered by Website Backups and encrypted Off-site Backups |

## Databases

| Tool | Status | What it needs |
|---|---|---|
| Databases (MariaDB and PostgreSQL) | Available | Each engine enabled on the server |
| Database Wizard | Planned (B) | Guided flow over the existing database API |
| Remote Database Access | Planned (B) | Host-restricted grants and firewall rules |
| Database Manager (phpMyAdmin-style) | Planned (B) | A web database client behind panel sign-in, in its own PHP pool |

## Domains

| Tool | Status | What it needs |
|---|---|---|
| Domains | Available | — |
| Redirects | Alias → Domains | — |
| WordPress Management | Available | Install only; updates and plugins planned with App Installer |
| Zone Editor | Planned (D) for hosting users | Exists for administrators; needs per-account record limits |
| Dynamic DNS | Planned (D) | Token-protected update endpoint for managed zones |
| Site Publisher | Planned (D) | Starter page templates |
| Website Builder (SitePad and Sitejet are third-party) | Planned (D) | Original drag-and-drop page builder |

## Metrics

| Tool | Status | What it needs |
|---|---|---|
| Metrics | Available | Recent requests and processes |
| Visitors, Errors, Raw Access Logs | Planned (D) | Account-scoped views and downloads of Nginx logs |
| Bandwidth, Visitor Statistics | Planned (D) | Log aggregation into daily totals and charts |
| Resource Usage | Planned (D) | Per-account cgroup accounting and limits |

## Security

| Tool | Status | What it needs |
|---|---|---|
| SSL/TLS, API Tokens | Available | — |
| SSL/TLS Status | Alias → SSL/TLS | — |
| IP Blocker | Alias → Website Security | — |
| Two-Factor Authentication | Alias → Preferences | — |
| Hotlink Protection | Available (alpha.16) | — |
| SSH Access | Planned (C) | Jailed shell after an isolation review; SFTP keys exist |
| Leech Protection | Planned (E) | Sign-in counting for protected folders |
| ModSecurity | Planned (E) | ModSecurity for Nginx with the OWASP Core Rule Set, per distribution |
| Malware Scanner (cPGuard and Imunify360 are third-party) | Planned (E) | Scheduled scans, for example with ClamAV, under the account UID |

## Software

| Tool | Status | What it needs |
|---|---|---|
| PHP Settings (INI editor) | Available | — |
| Optimize Website | Available (alpha.16) | — |
| PHP Version Manager (MultiPHP, Select PHP Version) | Planned (C) | Several PHP-FPM versions per distribution and a version per website |
| Setup Node.js App, Setup Python App, Application Manager | Planned (C) | Services under the account UID behind Nginx, with port allocation and limits |
| App Installer (Softaculous and Site Software) | Planned (C) | Original scripted installers that build on the WordPress installer |
| PHP PEAR Packages, Perl Modules | Planned (C) | Per-account package directories |
| SitePad Website Builder (third-party) | Not bundled | See Website Builder |

## Advanced

| Tool | Status | What it needs |
|---|---|---|
| Cron Jobs | Available | Account PHP scripts |
| Track DNS | Available | — |
| Indexes, Error Pages, MIME Types | Available (alpha.16) | — |
| Apache Handlers | Not applicable | almaPanel serves websites with Nginx; PHP runs through PHP-FPM. MIME Types covers content types. |

## Preferences and support

| Tool | Status | What it needs |
|---|---|---|
| Preferences, Operation History, Notifications | Available | — |
| Change Language | Planned (E) | Translated interface text |
| Support & About, Feature Availability | Available | — |
| Billing | Planned (E) | Integration with a billing system |

## Phases

- **A – Email:** done in alpha.17: default address, autoresponders, filters, disk
  usage, delivery tracking, deliverability checks. Remaining: DKIM signing, spam
  filtering and greylisting, routing, importer.
- **B – Files and databases:** FTP accounts, Web Disk, backup and database wizards,
  private Git, remote database access and a web database manager.
- **C – Runtimes:** PHP versions, Node.js and Python apps, application manager,
  app installer, PEAR and Perl packages, SSH access, mailing lists.
- **D – Domains and metrics:** tenant zone editor, dynamic DNS, publisher and
  builder, visitor, error, bandwidth and resource views.
- **E – Security and account:** ModSecurity, malware scanning, leech protection,
  mail encryption, challenge-response filtering, languages and billing.

Each tool is finished only after validation in the agent, rollback on failed
service checks, unit or real-service tests, browser tests and installed Amazon
Linux acceptance.
