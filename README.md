# almaPanel
### by Alma Tech Labs Inc.
**almaPanel — Powerful Hosting. Simple Management.**

Linux hosting control panel with an original, compact, grouped-tool interface inspired by familiar hosting workflows.

> **0.1.0-alpha.7 — evaluation.** Enrolled MariaDB and PostgreSQL databases can join encrypted off-site website snapshots. An administrator can recover a verified dump into a separate database. See [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) for live acceptance and release gates.

Amazon Linux 2023 is also an evaluation target. See [Amazon Linux 2023 EC2 evaluation](DEPLOYMENT.md#amazon-linux-2023-ec2-evaluation).

## Start on a clean Ubuntu EC2 instance
Target: **Ubuntu Server 24.04 LTS**, amd64 or arm64. Minimum approximately 1 GiB RAM and 5 GiB free disk; 2 GiB RAM recommended. Start with one small PHP/static site. The included CloudFormation example targets amd64. No claim of free AWS usage is made.

After uploading/extracting this repository on the instance:
```bash
cd almapanel
sudo bash installer/install.sh --preflight
sudo bash installer/install.sh --accept-alpha
```
The second command is the **current one-command source installation**. It installs Nginx, PHP 8.3 FPM, the API, worker, root agent, SQLite schema and local TLS, and runs health checks. It refuses existing hosting stacks. It requires Internet access to Ubuntu APT repositories. No Node build, Redis, Docker, database server, mail server or external PPA is needed by the core.

The panel binds to **127.0.0.1:8443 by default**. From your own computer:
```bash
ssh -L 8443:127.0.0.1:8443 ubuntu@YOUR_EC2_IP
```
Open `https://localhost:8443`. Verify the generated certificate fingerprint through SSH; the self-signed certificate is for evaluation and expires after 30 days. On the server retrieve the one-time setup token:
```bash
sudo cat /var/lib/almapanel/setup-token
```
Select “First installation? Set up administrator”. There is no default administrator password. Use a password of at least 14 characters.

## Included functionality
- Three role-aware interfaces: administrator, reseller and hosting user.
- Password hashing, one-time setup, expiring secure sessions, CSRF and origin checks, login throttling, audit history.
- Hosting packages with enforced domain counts; reseller account-count allocation and server-side ownership checks.
- Queued Linux user creation, per-account directories, POSIX isolation/ACLs and dedicated PHP-FPM pools.
- Nginx HTTP virtual hosts with pre-reload validation and configuration rollback.
- Web/panel suspension and unsuspension; existing PHP requests are not forcibly terminated.
- File browsing, binary upload/download, text editing, mkdir, non-overwriting rename, permanent delete; maximum file size 1 MiB. Directory traversal uses no-follow file descriptors, with operations executed under the tenant UID.
- Actual disk-size measurements and administrator system/service statistics. Unavailable metrics are explicitly unavailable.
- Fixed service restart allowlist, job history, failure reporting and restart-interruption handling.
- Installer/preflight, health checks, non-destructive disablement, control-database snapshot/restore, recovery scripts, deterministic source packaging and gated CI.

## Hosting tools
The [hosting guide](docs/HOSTING.md) covers upgrades, optional database and DNS
services, HTTPS, WordPress, backups, Git staging, PHP settings and account
security. Available services depend on the host configuration.

Chrooted SFTP and [Postfix/Dovecot email](docs/MAIL.md) are optional services.
The [backup guide](docs/BACKUPS.md) covers selective restore, scheduled SQL dumps
and encrypted local, SFTP and S3-compatible repositories.
Webmail, FTP/WebDAV, interactive tenant SSH, terminal, managed application runtimes,
enforced OS quotas and full-account backup and migration remain open.
See [FEATURE_MATRIX.md](FEATURE_MATRIX.md) for partial and completed scope.

## Development
```bash
make check
python3 scripts/package.py
python3 scripts/release_gate.py  # intentionally fails until release gates are satisfied
```
Python tests require only Python 3.12 standard library. Production HTTP serving uses Ubuntu's `python3-waitress`. The frontend is directly runnable HTML/CSS/JavaScript; source assets are production-servable without transpilation. Source tarballs are deterministic; APT package versions follow Ubuntu security updates and are recorded on installation, not frozen reproducibly.

## Source repository
The project is published at [allanalmatech/almaPanel](https://github.com/allanalmatech/almaPanel).
For existing installs, use the reviewed checkout and the steps in
[docs/HOSTING.md](docs/HOSTING.md). Signed release assets and their trust key
are configured separately.

## Future public installer
```bash
curl -fsSL https://install.almatechconsults.com/almapanel.sh | sudo bash
```
**Not live or claimed functional.** The bootstrap template is `installer/almapanel.sh`; deployment configuration is under `deployments/`. It refuses execution without an independently verified artifact digest. Public endpoint, signing trust, license approval and live acceptance gates must be completed before promotion. See [DEPLOYMENT.md](DEPLOYMENT.md) for explicit version selection and audit-first instructions.

## Documentation
[Architecture](ARCHITECTURE.md) · [Deployment & EC2](DEPLOYMENT.md) · [API](API.md) · [Database](DATABASE.md) · [Security](SECURITY.md) · [Tests](TESTING.md) · [User guide](USER_GUIDE.md) · [Admin guide](ADMIN_GUIDE.md) · [Reseller guide](RESELLER_GUIDE.md) · [TODO](TODO.md) · [Progress](PROGRESS.md) · [Release checklist](RELEASE_CHECKLIST.md)

## Ownership and support
Developed and owned by **Alma Tech Labs Inc.**
- Website: https://almatechconsults.com
- Email: almatechuganda@gmail.com
- Telephone: +256 700 868 939

© 2026 Alma Tech Labs Inc. All Rights Reserved.
Licensing terms are **pending owner approval**, not implicitly MIT/GPL or another open-source license. See [LICENSE](LICENSE) and [docs/LICENSING.md](docs/LICENSING.md). Original icons, branding and code; no proprietary cPanel assets. Not affiliated with cPanel.

Existing installations can apply the latest reviewed checkout with
`sudo bash installer/enable-updates.sh` from a trusted checkout.
See [Signed updates](docs/UPDATES.md) for enrolling a key and publishing releases.
