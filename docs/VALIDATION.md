# Validation record
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

Date: 2026-11-14. Version: 0.1.0-alpha.1.

| Check | Result |
|---|---|
| 34 unittest cases | PASS |
| Python compileall | PASS |
| node --check frontend/app.js | PASS |
| bash -n installer scripts | PASS |
| Bandit medium/high threshold | PASS; one documented B103 socket-mode exception, three low subprocess findings |
| Basic secret patterns | PASS; not exhaustive provider scanning |
| Browser acceptance | BLOCKED: Chromium local socket creation refused at launch |
| Real Linux service/EC2 install | NOT RUN; no clean root/systemd VM connected |
| Public DNS / ACME / SMTP | NOT RUN; modules/infrastructure incomplete |
| Upgrade/full restoration | NOT RUN; implementation incomplete |
| Production gate | Expected BLOCK; all acceptance booleans false |

Commands: `make check`, `python3 -m bandit -r backend agent worker -ll -ii`,
`python3 scripts/secret_scan.py`, `python3 scripts/package.py` (twice),
`python3 scripts/release_gate.py`, `git diff --check`, `git fsck --full`.

Packaging: deterministic source archives are compared byte-for-byte by SHA256.
Git history: initial private-evaluation commit included as a Git bundle in the delivery.
No remote URL, push, public release, live DNS, AWS instance or paid resource was created.

The API and filesystem checks use actual SQLite/files, but worker/rollback service calls
are mocked in those tests. This evidence must not be promoted to Linux acceptance.
