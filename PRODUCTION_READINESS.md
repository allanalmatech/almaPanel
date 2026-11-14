# Production readiness report

**Alpha.3 status.** This document’s alpha.1 evidence is historical.
See [PROGRESS.md](PROGRESS.md) for current tests and
[FEATURE_MATRIX.md](FEATURE_MATRIX.md) for open release gates.

**Decision: NOT READY FOR PRODUCTION.**
Version: 0.1.0-alpha.1 · Date: 2026-11-14 · Alma Tech Labs Inc.

| Area | Evidence | Decision |
|---|---|---|
| Core API/auth/file security | 34 local unittest cases pass | Partial foundation validated |
| Linux provisioning | Actual useradd/Nginx/PHP-FPM adapters implemented | Not run on a VM |
| Installer | Ubuntu-only source installer and syntax checks | Not live installed |
| Browser | Runner implemented; Chromium launch blocked by local socket restriction | Not passed |
| Static analysis | No medium/high Bandit findings after documented socket exception | Useful check, not audit |
| Requested full feature set | Many service modules not implemented | Blocks release |
| Multi-tenant resources | POSIX boundaries implemented; no cgroup/disk quotas | Blocks hostile shared hosting |
| Backup/restore | Control database scripts only | Full disaster recovery missing |
| Supply chain | Deterministic source + checksum bootstrap; no signing identity | Public release blocked |
| Infrastructure | No EC2 access, DNS, GitHub remote or signing credentials | No deployment/publication performed |

External inputs needed: a disposable Ubuntu EC2 VM/SSH execution path; test DNS domains and certificate reachability; mail-delivery infrastructure for later mail work; owner GitHub remote and publication authorization; signing identity; approved licensing terms. These inputs alone do not finish the missing modules—substantial implementation work remains as tracked in TODO.md.

This package is suitable for source review and isolated evaluation. It is not suitable to market as a complete hosting platform, serve sensitive sites over its current HTTP-only site adapter, or host untrusted commercial tenants.
