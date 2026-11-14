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
  copies into a new folder. Daily and weekly schedules retain 1–10 scheduled
  snapshots, independently of manual backups. ZIP operations normally cap
  unpacked content at 64 MiB, with a 128 MiB website snapshot limit. Keep independent copies off the server.
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
