# Deployment — Ubuntu EC2 evaluation
Copyright © 2026 Alma Tech Labs Inc. · LicenseRef-AlmaTech-Pending

## Supported target versus verified environment
The installer targets Ubuntu Server **24.04 LTS** and Amazon Linux **2023** on x86_64 and aarch64. Live VM acceptance is pending. Other distributions and versions are rejected by preflight.

Minimum: approximately 1 GiB RAM, 5 GiB available disk, root access, systemd, working DNS and outbound HTTPS/APT access. Use a 12–20 GiB encrypted EBS volume and 2 GiB RAM if available in your budget. One small PHP site may fit 1 GiB; concurrency and workloads determine actual capacity. No automatic swap allocation or guaranteed account density.

## EC2 launch checklist
1. Select an official Canonical Ubuntu Server 24.04 AMI matching the instance architecture. Verify the AMI publisher in AWS.
2. Choose an eligible instance based on your own AWS account. `t3.micro` amd64 is a small evaluation target; avoid unlimited CPU-credit surprises by reviewing the credit setting. The template defaults to standard credits.
3. Use your own key pair and public subnet with Internet route. Require IMDSv2. Use encrypted gp3 storage. No access keys are required by almaPanel.
4. Allow SSH TCP 22 **only from your public IP /32**. Allow public TCP 80 for hosted HTTP sites. Reserve TCP 443 for future site TLS. Leave 8443 closed when using the default SSH tunnel. No database, agent, worker or backend port should be public.
5. Prefer the SSH-tunnel panel setup while evaluating. AWS security groups and existing host firewall configuration are never rewritten by this installer. If UFW is active, add needed rules explicitly after preserving your actual SSH port/source; the installer does not enable or reset UFW.
6. Review billing budgets, EBS storage, snapshots, public IPv4, CPU credits and egress. Stopping an instance does not remove all billable resources.

Optional infrastructure template: `deployments/ec2-evaluation.yaml`. Review before creating a stack; no AWS resources are provisioned by this delivery.

## Install from reviewed source
Upload the ZIP/Git checkout, inspect the scripts, then:
```bash
cd almapanel
sudo bash installer/install.sh --preflight
sudo bash installer/install.sh --accept-alpha
```
`--preflight` performs local read-only checks; it does not prove APT downloads or service readiness. The install command is noninteractive. Without `--accept-alpha`, it requires typing `INSTALL-ALPHA` through the controlling terminal. Existing services, panel state and occupied ports cause a refusal rather than overwrite. Existing hosting servers require a separate migration plan and fresh staging VM; migration is not implemented.

This alpha is fail-safe, **not fully rerunnable**: after a partial install, state remains for diagnostics. Do not delete state to force the installer to continue. Restore a pre-install VM snapshot or repair/reconcile manually.

APT downloads use Ubuntu signed repository metadata and normal security updates. Installed dependency versions are recorded in `/etc/almapanel/package-versions.txt`. Application source is versioned but whole-OS installs are not bit-for-bit reproducible; use a tested AMI/snapshot and package manifest for reproducibility.

## Access and administrator setup
From your PC:
```bash
ssh -L 8443:127.0.0.1:8443 ubuntu@YOUR_EC2_IP
```
Then open `https://localhost:8443`. Retrieve and verify server certificate fingerprint:
```bash
sudo openssl x509 -in /etc/almapanel/panel.crt -noout -fingerprint -sha256
sudo cat /var/lib/almapanel/setup-token
```
Confirm the fingerprint in your browser before trusting the generated local certificate. Select first-installation setup, enter the token and choose a strong administrator password. Token is removed after successful setup. No password is printed or embedded in source. All sessions expire after one hour.

For a public panel during isolated testing only:
```bash
sudo bash installer/install.sh --accept-alpha --public-panel --hostname panel.example.com
```
Point the panel DNS A record to your server. Permit 8443 only from your administrator IP. The installer still uses a temporary self-signed certificate, not ACME. Set `ALMA_ORIGIN=https://panel.example.com:8443` consistently if changing access mode; installer does this for the public option. A wrong origin produces 403 on POST.

## TLS and DNS
The evaluation certificate expires after 30 days. Public trusted TLS and automated renewal are outstanding release gates. To install an externally obtained panel certificate, securely place the full chain at `/etc/almapanel/panel.crt` and matching key at `/etc/almapanel/panel.key` (root:root, key 0600), validate with `nginx -t`, then reload Nginx. Maintain your own renewal until the ACME module is implemented.

Customer domains are HTTP-only in this alpha. Set an A record with your DNS provider to the instance public IPv4; using a stable address avoids breakage after stop/start but may cost money. Domain creation sets up a virtual host, not DNS records or ownership verification. All domains of one account share its public_html. Never serve credentials/payment/customer-sensitive applications over this HTTP-only site hosting.

## Service management and logs
```bash
sudo bash /opt/almapanel/installer/healthcheck.sh
sudo systemctl status almapanel-agent almapanel-api almapanel-worker nginx php8.3-fpm
sudo journalctl -u almapanel-agent -u almapanel-worker -u almapanel-api --since today
sudo bash /opt/almapanel/installer/diagnostics.sh
```
Root configuration: `/etc/almapanel`. Source: `/opt/almapanel`. Panel state: `/var/lib/almapanel`. Agent state: `/var/lib/almapanel-agent`. Customer homes: `/srv/almapanel/accounts`. Install log: `/var/log/almapanel/install.log`. Logs are not exposed as raw root-readable files in the browser. Do not publish setup tokens, sessions or private keys in support logs.

## Backup / restoration
`sudo bash /opt/almapanel/installer/backup.sh --control-plane` briefly stops panel services, backs up SQLite via its backup API, and snapshots configuration and root registry with checksums. Websites continue serving. Snapshots are root-only and unencrypted; encrypt before remote storage. They contain no customer website/database/mail data and do not reconstruct Linux identities.

`sudo bash /opt/almapanel/installer/restore.sh /var/backups/almapanel/control-ID --confirm-control-plane-restore` restores only panel database state on the same server/version after checksums and exact registry equality. It refuses changed OS resource ownership. Previous database files are saved; sessions are invalidated. It does not restore config certificates. Test this on a clone before use. Full-account and disaster recovery restoration are not implemented. For current evaluation recovery, use a quiesced whole-VM/EBS snapshot and test restoration separately.

## Upgrades / rollback
`update.sh` exits 3 without mutation: no tested upgrade exists from the initial alpha. Before evaluating any next version, snapshot the VM, deploy to a clone, test migrations and site health, then promote. Roll back the entire VM snapshot if a migration is not reversibly supported. Do not just replace source files over a newer schema. Future releases must include reviewed migrations, compatible agent protocol, pre-upgrade backup and tested rollback.

`repair.sh --restart-panel` validates Nginx/PHP and restarts panel services; it does not silently repair provisioning state. `uninstall.sh --disable-panel` disables the panel and removes its Nginx listener while preserving customers, identities, site services and backups. No delete-customer-data option is included.

## Future public endpoint and version selection
The target hostname is not deployed. Owner must configure DNS, HTTPS, release hosting, digest publication, signing trust and complete release gates. Read `deployments/README.md`.

Auditable flow after approved publication:
```bash
curl -fsSLo almapanel.sh https://install.almatechconsults.com/almapanel.sh
# Inspect this file. Verify its checksum/signature against an independently trusted publication.
# Then obtain the RELEASE ARCHIVE digest separately, not the script digest:
sudo env ALMAPANEL_VERSION=0.1.0-alpha.1 ALMAPANEL_SHA256=VERIFIED_ARCHIVE_DIGEST bash almapanel.sh --accept-alpha
```
The bootstrap refuses a missing/invalid archive digest and verifies downloaded bytes before safe extraction. It does not trust a checksum fetched alongside the payload as sufficient authentication. Signing remains unconfigured. The unqualified proposed curl-pipe command will not work yet; no claim is made otherwise.

## External documentation (checked 2026-11-14)
- Ubuntu lifecycle: https://ubuntu.com/about/release-cycle
- Ubuntu PHP-FPM package: https://packages.ubuntu.com/noble/php8.3-fpm
- AWS Free Tier eligibility: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html
- EC2 port 25 restrictions: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-resource-limits.html
- Waitress proxy trust: https://docs.pylonsproject.org/projects/waitress/en/stable/reverse-proxy.html

AWS Free Tier benefits depend on account creation date and usage. The optional
Postfix and Dovecot stack binds to loopback by default. Direct delivery from EC2
requires removal of the outbound port 25 restriction. Follow the
[mail setup guide](docs/MAIL.md) for certificate and DNS requirements.

## Amazon Linux 2023 EC2 evaluation

The installer automatically selects the Amazon Linux 2023 adapter on x86_64 and
aarch64. The adapter uses the configured DNF repositories, PHP 8.3, Nginx and
a dedicated Python 3.12 environment with a checksum-pinned Waitress wheel from
PyPI. It does not change the system Python or upgrade the host release.
Outbound package repository and PyPI access are required.

Run from a fresh or updated checkout on a clean EC2 instance:

```bash
sudo bash installer/install.sh --preflight
sudo bash installer/install.sh --accept-alpha
```

Use the EC2 account for the default loopback-only panel:

```bash
ssh -i /path/to/your-key.pem -L 8443:127.0.0.1:8443 ec2-user@YOUR_EC2_IP
```

Open https://localhost:8443 and follow the administrator setup instructions
above. This adapter is an evaluation target pending a full EC2 install and reboot
test. Enforcing SELinux requires a policy that is outside this adapter's scope.
The installer leaves host SELinux settings intact.
