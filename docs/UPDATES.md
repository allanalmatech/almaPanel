# Signed updates

From the trusted checkout on the server, run `sudo bash installer/enable-updates.sh`
once. It installs the dashboard controls under **Server information → Software
updates**. The upgrade keeps the existing database, TLS certificate and customer
files. It briefly stops the panel processes.

The release publisher generates an Ed25519 signing key once on a trusted
publishing machine. Keep the private key outside this repository and off the
hosting server.

```bash
openssl genpkey -algorithm ED25519 -out almapanel-release-private.pem
chmod 600 almapanel-release-private.pem
openssl pkey -in almapanel-release-private.pem -pubout -out almapanel-release-public.pem
```

Transfer the public key to the hosting server through a trusted channel. Then
enroll it and turn on the timer:

```bash
sudo install -o root -g root -m 644 almapanel-release-public.pem /etc/almapanel/update-public.pem
sudo systemctl enable --now almapanel-update.timer
```

For each compatible release, increment VERSION, review and test the checkout,
then build and sign it using the same signing key:

```bash
python3 scripts/build_update.py
openssl pkeyutl -sign -rawin -inkey /secure/path/almapanel-release-private.pem \
  -in dist/manifest.json -out dist/manifest.sig
```

Attach all three files to the GitHub Release set as the repository's latest
release: `almapanel-update.tar.gz`, `manifest.json` and `manifest.sig`. GitHub's
latest-download URL must resolve to that release. A commit, tag or draft alone
does not qualify. Installations check every 15 minutes with up to one minute of
jitter. Administrators can also request an immediate check.

This channel updates only application code with database schema version 1 and
the existing service layout. The alpha.3 settings tables are additive, and
installer scripts for optional services are available after upgrading from a
reviewed checkout. Updates to the OS, dependencies, installer, trust
key, or database schema require a separate reviewed upgrade. Sign only releases
that preserve these contracts. On startup or health check failure, the updater
restores the previous application files. After a power interruption, the next
check attempts recovery. Review failures with
`sudo journalctl -u almapanel-update.service -n 50 --no-pager`.

Changes to package setup, installer scripts or systemd should be deployed
from the reviewed checkout with `installer/enable-updates.sh`. Before rolling
back to alpha.2, restrict access to the panel. Alpha.2 does not enforce TOTP or
domain proof, and old site edits cannot preserve all alpha.3 settings.
Code rollback preserves the database and hosted files.

## Account provisioning fix for alpha.9

Run the reviewed checkout's `installer/enable-updates.sh` on the server to
apply the unit fix and upgrade the code. The script installs the
`20-almapanel-provisioning.conf` agent drop-in. The root agent requires a
writable `/etc` for Linux user and group provisioning. The system tool
reports `account_files_writable` after the update.

## Resume after a failed health check

On the EC2 instance, use the updated Git checkout to recover an upgrade
that stopped with a curl connection error or an `in-progress` marker.

```bash
cd /home/ec2-user/almaPanel
git pull --ff-only origin main
sudo bash installer/enable-updates.sh
sudo bash installer/healthcheck.sh
cat /opt/almapanel/VERSION
```

The upgrade runs the checkout's health check for both the saved version and
the new application. It waits for each local endpoint to accept connections.
If it fails again, capture the failing check and the named service journal.
Keep `/var/lib/almapanel-updater/rollback` and its transaction marker for
recovery.
