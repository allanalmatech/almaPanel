# Troubleshooting
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

The software has unit-tested errors below; VM remedies are operational guidance, not claims of verified live repairs.

| Symptom | Cause / action |
|---|---|
| Installer rejects OS | Use a clean Ubuntu 24.04 systemd VM; do not edit the check to force another OS. |
| Existing service/state detected | Installer intentionally avoids overwriting. Assess migration on a new VM; do not delete customer state. |
| Partial install | Keep `/var/log/almapanel/install.log`; inspect failed command and diagnostics. Restore the pre-install snapshot for a clean retry. |
| Browser cannot connect | Establish SSH tunnel, check local port collision, systemd services and Nginx; 8443 is loopback-only by default. |
| Browser certificate warning | Expected for the 30-day evaluation certificate. Verify SHA256 fingerprint via SSH before trust; replace with a trusted certificate for any public use. |
| POST returns Origin rejected | Access URL and ALMA_ORIGIN differ; align exact scheme, hostname and port in `/etc/almapanel/panel.env`, restart API. |
| Login returns 429 | Wait 15 minutes for persisted throttling window; nginx has additional rate limiting. Do not disable protection on a public host. |
| Account queued forever | Check worker service and its journal. |
| Failed/interrupted account | Inspect root registry and actual Linux user/pool/home. No automatic unsafe rollback or blind retry. Reconcile on disposable VM before any manual repair. |
| Agent unavailable | Check agent service, socket ownership (root:almapanel 0660), process UID and journal. Never chmod the socket 0666. |
| File rejected | Path traversal, symlink, hardlink, special file or >1 MiB may be involved. Use ordinary account-owned files within public_html. |
| Nginx 403 for static files | Check account ACLs and directory traversal as www-data; do not make all homes world-readable. |
| New site not reachable | Confirm job succeeded, DNS A record, instance address and security group port 80. No DNS server is provisioned by domain creation. |
| Site HTTPS not available | Automatic site certificate management is not implemented. |
| Update exits 3 | Intentional: tested migration/rollback is not yet available. No changes made. |
| Restore refuses registry mismatch | Panel snapshot no longer matches Linux resources. Use full VM recovery/reconciliation; do not bypass check. |

Installer health checks failing means installation is not successful. Do not advertise an active service from a green UI alone. Support: almatechuganda@gmail.com. Redact secrets before sharing logs.
