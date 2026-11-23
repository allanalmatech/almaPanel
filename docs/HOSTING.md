# Hosting setup

almaPanel alpha.3 adds site management tools on top of the Amazon Linux 2023 and
Ubuntu 24.04 evaluation installs. On an existing server, back up panel state and
customer data before changing the running installation. Keep your SSH session
open while you run these commands from the almaPanel checkout.

```bash
git pull --ff-only origin main
sudo bash installer/enable-updates.sh
sudo bash installer/healthcheck.sh
```

The upgrade replaces application files and briefly restarts the panel services.
It keeps the existing hosting accounts, website files, panel SQLite database
and TLS certificate. New settings tables are additive. The installed updater
restores the previous code if startup or the panel check fails. Sign and publish
an update asset only after checking it on a VM. See [UPDATES.md](UPDATES.md).

## Start a website

1. Sign in as a panel administrator and create a hosting package and account.
2. Create a site folder in File Manager under `public_html`.
3. Select the account and add the hostname in Domains with that folder as its
   document root. Set the hostname’s A or AAAA record at your DNS provider.
4. Review Operation History and wait for the domain job to succeed. Test the
   site over HTTP before issuing HTTPS.
5. Administrators can add domains directly. Account users and resellers must
   verify a DNS TXT record before adding a new domain. Install the resolver
   command with `sudo bash installer/enable-domain-verification.sh` if needed.
   Existing unverified domains can be verified in the domain form before a
   tenant configures HTTPS or WordPress for them.

Alias targets must be websites in the same account. Redirects can point to HTTP
or HTTPS URLs. Removing a domain removes its managed web configuration and
releases the hostname. Website files stay in File Manager. Keep document roots
separate for unrelated sites.

## Enable optional Linux services

Run only the setup commands that the site needs. Each database or DNS setup
expects a clean instance of that service. Existing service adoption and
migration require review outside these scripts.

```bash
sudo bash installer/enable-databases.sh mariadb
sudo bash installer/enable-databases.sh postgresql
sudo bash installer/enable-site-tls.sh
```

Use **Databases** to create a database and its login. Store the generated
password when it is shown. MariaDB uses the local socket, and PostgreSQL
accepts its database’s login on loopback. Database import uses authenticated
customer credentials and accepts an SQL file for MariaDB or a custom
`.pgdump` file for PostgreSQL up to 1 MiB. Imports can modify existing data.
Export and download a copy first. PostgreSQL imports use a transaction.
MariaDB DDL can commit before an import error, so use a separate database when
testing a restore. Temporary export files are stored outside public web roots.

The SSL/TLS page can use a locally installed Certbot with HTTP validation.
The domain must resolve publicly to this EC2 instance, and inbound TCP 80
must reach Nginx. Allow 443 for site HTTPS. If Certbot is unavailable in your
configured Amazon Linux repositories, install a supported build at
`/usr/bin/certbot` before running the TLS setup script. Alternatively, upload
a matching PEM certificate chain and private key. The renewal timer handles
the managed Certbot certificates when it is installed. The panel on port
8443 uses its own certificate. Verify the renewed site from outside the VM.

### Managed DNS

Skip this setup when using an existing DNS provider. To let almaPanel
administer public forward zones using BIND, configure the authoritative
nameservers first. For example, replace the names below with yours.

```bash
sudo bash installer/enable-dns.sh ns1.example.com ns2.example.com
```

Zone Editor validates A, AAAA, CNAME, TXT, MX, SRV and CAA records and reloads
BIND after validation. It imports and exports the panel’s JSON format. Set
registrar delegation and any glue records, and configure the listed servers
to serve the same zone. Allow inbound UDP and TCP 53 on authoritative servers.
Recursion and external transfers are disabled. PTR delegation, automated
secondary synchronization and DNSSEC remain separate work.

## Use the account tools

- **WordPress** requires an HTTPS website and a dedicated empty MariaDB
  database. The installer verifies a pinned upstream archive, runs PHP as the
  hosting account, creates the administrator, and sets the domain’s document
  root after successful initialization. If the final Nginx change fails, the
  new files and database may still exist. Review Operation History or the
  agent log before trying again.
- **Git Deployment** stages a public provider branch into a new folder. Review
  the result, then change the domain’s document root. Keep the previous
  folder if you need to switch back. Private credentials, build scripts and
  automatic deploy hooks are outside this workflow.
- **Website Backups** stores local ZIPs outside the served root. RESTORE
  copies into a new folder. Browse an archive to search it, verify its files or
  restore one file. Daily and weekly schedules retain 1–10 website snapshots.
  See [Website backup and recovery](BACKUPS.md) for limits and setting up an
  encrypted off-site destination. Enrolled MariaDB and PostgreSQL databases
  can be included in the same off-site snapshots.
- **Cron Jobs** schedules existing PHP scripts inside the account at fixed
  intervals. The worker skips suspended accounts. Jobs have a runtime limit
  and run as the account’s Linux user.
- **Website Security** provides HTTPS directory passwords and site IP rules.
  Protect a dedicated document root to avoid alternate website paths to the
  same content. Test both an unauthenticated and authenticated request after
  making changes. IP rules affect the site and do not change the EC2 firewall.
- **Preferences** enables TOTP and shows single-use recovery codes once. Save
  them before signing in again. API Tokens provide read-only access to
  permitted hosting resources and expire after 90 days.
- **Metrics** shows recent managed Nginx log entries and process statistics.
  Saving a previously existing domain refreshes its configuration to enable
  website request logging. Configure log rotation when deploying.

## Working with website files

Select your hosting account and open **File Manager**. The screen has:

- a search bar: choose **All your files** or **Current folder**, enter part
  of a name after **for**, and press **Go**;
- an action toolbar: **File**, **Folder**, **Copy**, **Move**, **Upload**,
  **Download**, **Delete**, **Rename**, **Edit**, **Permissions**, **View**,
  **Extract** and **Compress**. Each action is enabled only when the selection
  supports it;
- a folder panel with a path box, a home button, **Collapse All** and the
  folder tree;
- a navigation bar: **Home**, **Up One Level**, **Back**, **Forward**,
  **Reload**, **Select All**, **Unselect All**, **View Trash** and
  **Empty Trash**;
- the file list with Name, Size, Last Modified, Type and Permissions. Click a
  column heading to sort; folders stay first, and sorting applies to the
  100-entry page shown.

Click a row to select it, Ctrl-click (Cmd-click on macOS) to add or remove
rows, and Shift-click to select a range. You can also tick the row
checkboxes. Double-click a row, or click its name, to open a folder or file.
In the list, Ctrl+A selects all and Delete moves the selection to Trash.
**Settings** controls **Show hidden files** and an owner and group column;
the browser remembers these choices.

- Choose **File** to open the source editor for a new file, or **Folder** to
  create a directory. Select a text file and choose **Edit**. Select a highlighting
  language and press **Save file** or use Ctrl+S (Cmd+S on macOS). A concurrent
  saved change causes a revision conflict. Copy your unsaved text before
  reopening the current file.
- Drop files on the upload area or choose up to 50 at once. Watch progress
  per file. A file appears at its destination after the full upload succeeds.
  **Download** reconstructs the requested file from chunks of the same revision.
- Select one or more entries for **Copy**, **Move**, **Delete**,
  **Permissions** or **Compress**. With one entry, the destination dialog
  can browse folders and set a new name. With several, choose the
  destination folder and each entry keeps its name. The panel reports how
  many succeeded and names any that failed. **Rename** and **Download** work
  on one entry. Copy, move, upload and restore require an unused path.
  Permission edits apply the ordinary owner/group/other bits. Check that
  Nginx can still enter the parent folders and read files you want to serve.
- Click a ZIP to list its files, or select it and choose **Extract** to unpack
  it to a new folder. **Compress** puts every selected file and folder into one
  ZIP. To compress a whole folder, select it in its parent folder, or open it and
  choose **Select All**.
- **Delete** moves entries to Trash. Use **View Trash** to restore an entry to its
  original or another unused path, or to delete one permanently. **Empty Trash**
  permanently deletes everything in Trash after a confirmation. Trash remains
  private to the hosting account.
- Click PNG, JPEG, GIF or WebP to preview it. Use the width, height and output
  format controls to save a resized copy as PNG, JPEG or WebP. Animated GIF
  conversion saves a still image. Supported audio and video files open with
  browser playback controls. HTML and SVG open as source text.

| Operation | Limit |
|---|---|
| Individual browser upload, download or file copy | 256 MiB |
| Text editor | 1 MiB of UTF-8; live syntax highlighting up to 180,000 characters |
| Media preview | 24 MiB and a codec supported by your browser |
| Resized image output | 16 megapixels, with each dimension up to 8192 pixels |
| ZIP and recursive copy | 64 MiB of content and 5,000 entries; ZIP32, single disk |
| Folder listing and search | 5,000 entries scanned, 100 entries per listing page and 250 search results |
| Upload staging | Four pending uploads and 512 MiB declared per account; stages expire after one hour of inactivity |

Account storage usage comes from Linux and includes the account's private files.
Upload completion requires space for both the private stage and the destination.
Symlinks and hardlinked regular files cannot be opened, copied or extracted
through the panel. The file controls work under the account's Linux UID.

## Acceptance on Amazon Linux 2023

For a disposable VM, run the repository acceptance script after enabling the
services being tested. It creates test tenants and uses the real agent and
Linux services. A live domain and working delegation are still needed for
public BIND and ACME checks. Keep the panel accessible through your SSH tunnel.
See [TESTING.md](../TESTING.md) and [FEATURE_MATRIX.md](../FEATURE_MATRIX.md).

## SFTP access

Enable a separate chrooted listener with `sudo bash installer/enable-sftp.sh`.
It listens on loopback port 2222 by default. The script prints the server
host key fingerprint. Compare that fingerprint in your SFTP client before
accepting it. Add an OpenSSH Ed25519 public key in **SFTP Access**. Keep the
corresponding private key on the client.

For a loopback install, forward port 2222 through your existing system SSH
connection. For example, run the tunnel on your own computer:

```bash
ssh -N -L 2222:127.0.0.1:2222 ec2-user@YOUR_EC2_IP
```

Then connect your SFTP client to `127.0.0.1:2222` as the username shown in
the panel, such as `ap_customer`. Your virtual home exposes only that
hosting account’s files. The service uses an independent config and host key.
The web server reads uploads through the account’s existing ACLs.

Use `--public` with the setup script on a first installation if you want
clients to connect directly. Configure your EC2 rules for that port. Password
and shell access are unavailable for this service. Removing a key or
suspending an account blocks new logins. Existing transfers can finish.

To validate end to end on a clean Amazon Linux VM, set
`ALMA_TEST_SFTP=YES` when running `tests/installation/amazon_vm.sh`. The
script checks upload, chroot isolation and revocation.

**DNS Track** shows public records via the server’s resolver.
**Notifications** shows completed and failed operations within your role’s scope.

## Email hosting

Administrators can set up Postfix and Dovecot where no mail server is already
configured. Users manage their own mailboxes and forwarders in **Email Accounts**.
The [mail setup guide](MAIL.md) covers TLS, DNS, loopback testing and external access.
