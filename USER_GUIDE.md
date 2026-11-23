# Hosting user guide
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

1. Open the HTTPS almaPanel address supplied by the administrator, verify its certificate, and sign in with your panel username/password. These are not Linux SSH credentials.
2. The sidebar holds **Dashboard**, **File Manager**, **Domains** and **Preferences**. Every other tool is in a group on the **Dashboard**: Files, Domains, Databases, Email, Software, Metrics, Advanced, Security, Account and Help. Type in **Search hosting tools** to filter by tool name, description or group name, for example `backup` or `email`. Press Escape or choose **Clear search** to show all tools again. The breadcrumb above each page shows its group.
   On a desktop, the menu button collapses the sidebar to icons; the browser remembers this choice. On a phone, the menu button opens the navigation drawer; close it with ×, the Escape key or a tap outside it. Use the top theme toggle for light/dark mode.
3. In **Domains**, enter a lowercase DNS name, for example `www.example.com`. The action queues a job. Review **Operation History** and wait for `succeeded`; a queued notification does not mean provisioning succeeded. Configure DNS separately with your provider.
4. **File Manager** opens in its own browser tab for the hosting account selected at the top of the panel. Choosing it again switches to that tab. Choosing **Edit**, **File** or a text file's name opens the editor in a separate tab, and choosing the same file again reuses its tab. Save with **Save Changes** or Ctrl+S, and close the tab with **Close**. File Manager refreshes the folder after you save. In File Manager, select files with the row checkboxes, a click, Ctrl-click or Shift-click, then use the toolbar: File, Folder, Copy, Move, Upload, Download, Delete, Rename, Edit, Permissions, View, Extract and Compress. Home, Up One Level, Back, Forward, Select All, View Trash and Empty Trash are in the bar above the list. Click a column heading to sort. See [Working with website files](docs/HOSTING.md#working-with-website-files) for limits and examples.
5. An `index.html` or `index.php` serves as your homepage through Nginx. All your account domains share the same document root in this release. Sites are HTTP-only until site TLS is implemented; do not deploy sensitive customer-facing applications here.
6. **Disk Usage** retrieves actual directory bytes. CPU/RAM/bandwidth are explicitly unavailable at account level; no invented bars or quotas are shown.
7. **Preferences** holds contact details and two-factor sign-in. Changing the password there requires the current password and a new 14–128-character password; all sessions are invalidated. Sign in again. Log out when done; sessions expire after one hour.

8. **Email Accounts** manages mailboxes and forwarders when the administrator
   has enabled Postfix and Dovecot. Create a mailbox for a verified domain
   and use its full address, password and the displayed connection settings
   in your email client. See the [mail guide](docs/MAIL.md).
9. In **Website Backups**, choose **Browse files** to search a backup and
   verify it. Choose **Restore file** to recover one file to an unused path.
   See [Website backup and recovery](docs/BACKUPS.md).

Suspended accounts cannot log in to the panel. Report failed jobs with the
job ID and keep credentials private. Use **Feature Availability** to check
which hosting tools are available. Support information is under **Support & About**.
