# Production readiness report
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

**0.1.0-alpha.8 · 2026-11-15 · Evaluation.** Production release gates remain open.

| Area | Verified evidence | Open acceptance |
| --- | --- | --- |
| Installation | Amazon Linux 2023 alpha.1 setup and alpha.4 upgrade recovery confirmed by the operator | Fresh alpha.8 Amazon Linux and Ubuntu runs, reboot and rollback |
| Website hosting | API and filesystem tests, local service checks, Chromium workflows | All roles on target VMs, accessibility, workload and performance checks |
| Database backups | Real MariaDB, PostgreSQL and restic round trip into empty tenant databases | Scheduled jobs on target VMs, remote recovery, broader MariaDB object support |
| Backup coverage | Selective website recovery and encrypted backup of enrolled databases and managed DNS | Mail, panel state and full-account disaster recovery |
| Isolation and quotas | Account scoping and UID-based filesystem operations tested locally | Hostile-tenant, network, process and operating-system quota tests |
| DNS, TLS and mail | Site TLS, BIND and optional Postfix/Dovecot adapters implemented | Public DNS delegation, certificate issuance and renewal, external mail delivery |
| Release and distribution | Source published on GitHub, signed-code updater implemented | License approval, signing identity, verified artifacts and public installer |
| Security review | Local scope, validation and permission tests plus static analysis | Independent review and production supply-chain verification |

The [release checklist](RELEASE_CHECKLIST.md) and [feature matrix](FEATURE_MATRIX.md)
track remaining requirements. See [PROGRESS.md](PROGRESS.md) for commands and
evidence by milestone.
