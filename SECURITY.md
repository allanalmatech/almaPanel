# Security policy and threat model
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

**Evaluation alpha. Do not use for untrusted multi-tenant production hosting.** Report vulnerabilities privately to almatechuganda@gmail.com (+256 700 868 939). Do not include live credentials, private keys or personal customer data. No response-time SLA is promised by this source delivery.

## Threats addressed in implemented code
- Unauthenticated access: server-side sessions, high-entropy cookie IDs, hashed session IDs, scrypt passwords, single-use setup token.
- Cross-tenant operations: ownership checks at every account API endpoint; administrator-only system endpoints; reseller allocation checks and scoped queries.
- CSRF/session theft: Secure + HttpOnly + SameSite=Strict cookies, synchronizer token, JSON request type and exact configured Origin for POST. No permissive CORS. Absolute one-hour expiry; password changes revoke all sessions.
- Login abuse: persistent per-IP counters and Nginx login/setup rate limiting. Forwarded client IP only trusted through a restricted Unix socket.
- XSS: CSP, no third-party scripts, escaped dynamic HTML, textContent/textarea values, no inline scripts. CSP disables frames and base injection. Browser acceptance remains pending due environment restrictions.
- SQL injection: parameterized SQLite statements; no arbitrary SQL endpoint.
- Shell injection: fixed command arrays, no shell=True, strict account/domain validation, closed service allowlist.
- File escapes: per-tenant UID subprocess; O_NOFOLLOW directory traversal; deny nonregular/hardlinked reads/writes; no root file serving; bounded sizes and no archive extraction feature exposed. Delete affects an entry only, never follows symlinks recursively.
- Service configuration corruption: atomic generated files, syntax validation before reload, restore original files on errors.
- Supply chain: no customer install scripts run as root; deterministic source archive and checksum enforcement; signed OS repository metadata; public release gate intentionally blocks.

## Secrets and access
API state is mode 0700; root agent registry and TLS key remain root-only. Runtime sockets restrict groups and agent checks peer UID. No agent API to retrieve keys or database root passwords. No password in argv, logs or queued payloads. Setup token is readable to root and panel UID until used. Root is a fully trusted administrator.

The API and worker run under the same dedicated UID and are in the broker trust boundary. A compromised API can request allowlisted privileged operations; additional signed short-lived capability tokens/independent policy verification would improve defense in depth. The root agent requires writable /etc to allow useradd account files/locks and service configuration; this broad allowance is documented, not presented as complete sandboxing.

## Known security release blockers
MFA, API tokens, password recovery, forced reauthentication, cgroups/disk quota enforcement, full PHP workload isolation, agent protocol schema caps, domain proof-of-control, ACME, fail2ban configuration, malware scanning, patch lifecycle, independent penetration review, comprehensive hostile-tenant live tests, log retention/tamper resistance and disaster recovery are unfinished. Suspension disables website HTTP and panel login but does not terminate already-running PHP/child processes. Customer sites are HTTP-only. Per-IP throttling can affect users behind the same NAT and is not distributed brute-force protection.

## Audit and verification
Audit API is administrator-only. Events include auth failures/success, setup, password changes, mutations, queued jobs and outcomes. Root agent logs operation names/failures to journal; it does not log request bodies. Audit retention and external immutable forwarding are not implemented.

Unit tests cover scope bypasses, CSRF, sessions, injection inputs, file links/traversal/FIFO, and rollback behavior. System adapters are not certified by mocked tests. Bandit at medium/high threshold reports zero remaining findings after one documented B103 exception for the intentionally group-connectable broker socket; subprocess imports/calls still produce low-level informational findings. Bandit is not a security certification. See TESTING.md for evidence and limitations.
