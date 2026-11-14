# Administrator guide
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

Complete DEPLOYMENT.md first, using a disposable EC2 VM. Claim the initial administrator with the generated setup token. No default credentials exist.

1. **Packages**: create a named package with a 1–100 domain limit. Only domain-count allocation is enforced; do not advertise disk, RAM, CPU or traffic quotas.
2. **Hosting Accounts**: choose username, initial panel password and package. Account remains `provisioning` and login disabled until the Linux job succeeds. Review Operation History. Successful creation installs ap_USERNAME, a root-owned account boundary, writable public_html/runtime, read-only Nginx ACL and private PHP-FPM pool. Share credentials through your own secure channel.
3. Select an account in the top account selector to manage its domains/files. No customer is selected by fabricated data. Accounts created by resellers are visible to administrators.
4. **Resellers**: create a login and maximum hosting-account count. No arbitrary admin privilege delegation is offered. Resellers cannot create other resellers or invoke system management APIs.
5. **Suspend** blocks generated HTTP vhosts and disables/revokes user panel sessions after successful completion. It does not kill running workloads or guarantee resource containment. Unsuspend restores the generated HTTP config and panel login. Confirmation is required.
6. **Server Information** shows real /proc memory, load averages, filesystem capacity and systemd service status. Fixed-allowlist restart requires typing RESTART and confirmation. Only Nginx and php8.3-fpm can be restarted through this interface.
7. Review audit and job logs. Browser audit is bounded to 200 recent rows, jobs to 100. Failed/interrupted jobs require system journal and root-registry reconciliation; never flip a failed row to active without checking Linux resources.
8. Back up and restore the control database using the explicit scripts in DEPLOYMENT.md. These do not back up websites or reconstruct Linux identities. Full VM snapshots are needed for current evaluation recovery.

9. For optional mail hosting, follow the [Postfix and Dovecot setup guide](docs/MAIL.md).
   Check relay denial, mailbox authentication and local delivery before opening
   external access. For the software update channel, see [Signed updates](docs/UPDATES.md).

The [feature matrix](FEATURE_MATRIX.md) and [release checklist](RELEASE_CHECKLIST.md)
track account termination, network management, administrator permissions,
resource enforcement and the remaining deployment tests.
