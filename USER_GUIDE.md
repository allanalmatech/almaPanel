# Hosting user guide
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

1. Open the HTTPS almaPanel address supplied by the administrator, verify its certificate, and sign in with your panel username/password. These are not Linux SSH credentials.
2. Dashboard tools are grouped by function. Search filters the available tool names/help. Use the top theme toggle for light/dark mode; mobile navigation opens with the menu button.
3. In **Domains**, enter a lowercase DNS name, for example `www.example.com`. The action queues a job. Review **Operation History** and wait for `succeeded`; a queued notification does not mean provisioning succeeded. Configure DNS separately with your provider.
4. In **File Manager**, the root is your `public_html`. Create a text file, edit and save it; create directories, navigate Up, rename, upload multiple files or download an opened file. Binary files are download-only. File size limit is 1 MiB. Delete is permanent; directories must be empty. Hidden entries are visible. Symlinks cannot be traversed. No archives, trash, syntax highlighting or drag-and-drop are provided yet.
5. An `index.html` or `index.php` serves as your homepage through Nginx. All your account domains share the same document root in this release. Sites are HTTP-only until site TLS is implemented; do not deploy sensitive customer-facing applications here.
6. **Disk Usage** retrieves actual directory bytes. CPU/RAM/bandwidth are explicitly unavailable at account level; no invented bars or quotas are shown.
7. **Password & Security** requires the current password and a new 14–128-character password; all sessions are invalidated. Sign in again. Log out when done; sessions expire after one hour.

Suspended accounts cannot log in. Failed jobs should be reported to the administrator with job ID, not with credentials. Use **Feature Availability** for unavailable modules; there are no functioning email/database/Git/SSL tools in this alpha. Support: https://almatechconsults.com · almatechuganda@gmail.com · +256 700 868 939.
